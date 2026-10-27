"""Transport-independent execution tests plus explicit Kafka delivery semantics."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from engine.codegen import build_artifact
from engine.dispatch.artifacts import LocalArtifactStore, load_manifest
from engine.dispatch.contracts import ExecutionRequest
from engine.dispatch.dispatcher import Dispatcher, RuntimeProfile
from engine.dispatch.kafka import KafkaExecutionConsumer, KafkaPublisher, kafka_config_from_env
from engine.dispatch.worker import execute


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def execution(tmp_path):
	dag = {
		"nodes": [{
			"id": "read", "operation": {"name": "read_csv"}, "input_ports": [], "output_ports": [],
			"parameters": {"filepath": {"$param": "source"}},
		}], "edges": [],
	}
	directory = tmp_path / "artifact"
	build_artifact(dag, directory, pipeline_id="orders", pipeline_version="1")
	pd.DataFrame({"id": [1, 2]}).to_csv(tmp_path / "input.csv", index=False)
	manifest = directory / "manifest.json"
	request = ExecutionRequest(
		"exec-1", manifest.as_uri(), hashlib.sha256(manifest.read_bytes()).hexdigest(),
		{"source": str(tmp_path / "input.csv")}, {},
	)
	return request, LocalArtifactStore(tmp_path), directory


def test_request_validation_and_roundtrip(execution):
	request, _, _ = execution
	assert ExecutionRequest.from_dict(request.to_dict()) == request
	assert request.job_name == ExecutionRequest.from_dict(request.to_dict()).job_name
	for updates in [
		{"execution_id": "../../escape"}, {"manifest_uri": "http://untrusted"},
		{"manifest_sha256": "bad"}, {"message_version": "2"},
		{"parameters": {"x": float("inf")}}, {"datasources": {"port": 1}},
	]:
		with pytest.raises(ValueError):
			ExecutionRequest.from_dict({**request.to_dict(), **updates})
	with pytest.raises(ValueError):
		ExecutionRequest.from_dict({**request.to_dict(), "command": ["arbitrary"]})


def test_dispatcher_prepares_job_and_uses_approved_image(execution):
	request, store, _ = execution
	jobs = []
	dispatcher = Dispatcher(store, {"python-pandas-v1": RuntimeProfile("registry/worker@sha256:approved", "pandas")}, submit=jobs.append)
	job = dispatcher.dispatch(request)
	assert jobs == [job]
	assert job["metadata"]["name"] == request.job_name
	container = job["spec"]["template"]["spec"]["containers"][0]
	assert container["image"] == "registry/worker@sha256:approved"
	assert container["command"] == ["python", "-m", "engine.dispatch.worker"]
	assert job["spec"]["backoffLimit"] == 0
	with pytest.raises(RuntimeError, match="submit adapter"):
		Dispatcher(store, dispatcher.profiles).dispatch(request)
	with pytest.raises(ValueError, match="approved"):
		Dispatcher(store, {}).prepare(request)
	with pytest.raises(ValueError, match="approved"):
		Dispatcher(store, {"python-pandas-v1": RuntimeProfile("image", "polars")}).prepare(request)


def test_worker_executes_verified_artifact_and_reports_events(execution):
	request, store, _ = execution
	events = []
	assert execute(request, store, "python-pandas-v1", publish_event=events.append, timeout=30) == 0
	assert [event["status"] for event in events] == ["started", "succeeded"]
	assert events[-1]["exit_code"] == 0
	assert all("parameters" not in event for event in events)


def test_worker_runtime_failure_is_nonzero(execution):
	request, store, _ = execution
	request = ExecutionRequest.from_dict({**request.to_dict(), "parameters": {"source": "/missing-input-file.csv"}})
	events = []
	code = execute(request, store, "python-pandas-v1", publish_event=events.append, timeout=30)
	assert code != 0
	assert [event["status"] for event in events] == ["started", "failed"]
	assert events[-1]["exit_code"] == code


def test_worker_timeout_reports_failure_and_propagates(execution, monkeypatch):
	request, store, _ = execution
	events = []
	def timeout(*args, **kwargs):
		raise subprocess.TimeoutExpired("python", 1)
	monkeypatch.setattr(subprocess, "run", timeout)
	with pytest.raises(subprocess.TimeoutExpired):
		execute(request, store, "python-pandas-v1", publish_event=events.append, timeout=1)
	assert [event["status"] for event in events] == ["started", "failed"]


@pytest.mark.parametrize("tamper", ["manifest", "script", "profile"])
def test_worker_rejects_tampering_before_execution(execution, tamper, monkeypatch):
	request, store, directory = execution
	if tamper == "manifest":
		(directory / "manifest.json").write_text("{}")
	elif tamper == "script":
		(directory / "main.py").write_text("raise AssertionError('must never execute')")
	events = []
	monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: pytest.fail("Unverified code was executed"))
	with pytest.raises(ValueError):
		execute(request, store, "python-polars-v1" if tamper == "profile" else "python-pandas-v1", publish_event=events.append)
	assert [event["status"] for event in events] == ["failed"]


def test_manifest_command_is_not_executed_and_paths_are_allowlisted(execution, monkeypatch):
	request, store, directory = execution
	path = directory / "manifest.json"
	manifest = json.loads(path.read_text())
	manifest["execution"]["command"] = ["malicious-shell", "payload"]
	path.write_text(json.dumps(manifest))
	request = ExecutionRequest.from_dict({**request.to_dict(), "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
	commands = []
	def run(command, **kwargs):
		commands.append(command)
		return subprocess.CompletedProcess(command, 0)
	monkeypatch.setattr(subprocess, "run", run)
	assert execute(request, store, "python-pandas-v1", publish_event=lambda event: None) == 0
	assert commands[0][0] == "python"
	assert "malicious-shell" not in commands[0]
	manifest["files"][0]["path"] = "../main.py"
	path.write_text(json.dumps(manifest))
	request = ExecutionRequest.from_dict({**request.to_dict(), "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
	with pytest.raises(ValueError, match="Unexpected"):
		load_manifest(store, request)


def test_manifest_checks_parameters_and_external_ports(execution):
	request, store, _ = execution
	for parameters in [{}, {"source": 1}, {"source": "x", "extra": 1}]:
		with pytest.raises(ValueError):
			load_manifest(store, ExecutionRequest.from_dict({**request.to_dict(), "parameters": parameters}))
	with pytest.raises(ValueError, match="datasource"):
		load_manifest(store, ExecutionRequest.from_dict({**request.to_dict(), "datasources": {"port": "x"}}))


def test_store_blocks_outside_root_and_symlinks(tmp_path):
	root = tmp_path / "allowed"
	root.mkdir()
	outside = tmp_path / "outside"
	outside.write_text("not-an-artifact")
	(root / "link").symlink_to(outside)
	store = LocalArtifactStore(root)
	for uri in [outside.as_uri(), (root / "link").as_uri(), "https://example.invalid/manifest"]:
		with pytest.raises(ValueError):
			store.read(uri)


class FakeProducer:
	def __init__(self, *, error=None, pending=0):
		self.error, self.pending, self.messages = error, pending, []

	def produce(self, topic, key, value, on_delivery):
		self.messages.append((topic, key, json.loads(value)))
		self.callback = on_delivery

	def flush(self, timeout):
		if not self.pending:
			self.callback(self.error, None)
		return self.pending


def test_kafka_publisher_waits_for_confirmed_delivery(execution):
	request, _, _ = execution
	producer = FakeProducer()
	publisher = KafkaPublisher({"bootstrap.servers": "unused:9092"}, "executions", producer=producer)
	publisher.publish_request(request)
	assert producer.messages == [("executions", b"exec-1", request.to_dict())]
	for failed, exception in [(FakeProducer(error="failed"), RuntimeError), (FakeProducer(pending=1), TimeoutError)]:
		with pytest.raises(exception):
			KafkaPublisher({"bootstrap.servers": "unused"}, "executions", producer=failed).publish_request(request)


class FakeMessage:
	def __init__(self, request):
		self.request = request

	def value(self):
		return json.dumps(self.request.to_dict()).encode()

	def key(self):
		return self.request.execution_id.encode()

	def error(self):
		return None


class FakeConsumer:
	def __init__(self, message):
		self.message, self.commits, self.closed = message, [], False

	def subscribe(self, topics):
		self.topics = topics

	def poll(self, timeout):
		return self.message

	def commit(self, **kwargs):
		self.commits.append(kwargs)

	def close(self):
		self.closed = True


def test_kafka_commits_only_after_dispatch_acceptance(execution):
	request, store, _ = execution
	fake = FakeConsumer(FakeMessage(request))
	jobs = []
	dispatcher = Dispatcher(store, {"python-pandas-v1": RuntimeProfile("approved-image", "pandas")}, submit=jobs.append)
	consumer = KafkaExecutionConsumer({"bootstrap.servers": "unused"}, "executions", "dispatchers", dispatcher.dispatch, consumer=fake)
	assert consumer.poll_once()
	assert len(jobs) == 1
	assert fake.commits == [{"message": fake.message, "asynchronous": False}]
	consumer.close()
	assert fake.closed
	fake = FakeConsumer(FakeMessage(request))
	def reject(request):
		raise RuntimeError("Submission unavailable")
	consumer = KafkaExecutionConsumer({"bootstrap.servers": "unused"}, "executions", "dispatchers", reject, consumer=fake)
	with pytest.raises(RuntimeError, match="unavailable"):
		consumer.poll_once()
	assert fake.commits == []
	with pytest.raises(RuntimeError, match="close and recreate"):
		consumer.poll_once()
	assert fake.commits == []


def test_kafka_idle_and_invalid_messages_are_not_committed(execution):
	request, _, _ = execution
	fake = FakeConsumer(None)
	consumer = KafkaExecutionConsumer({"bootstrap.servers": "unused"}, "executions", "dispatchers", lambda req: None, consumer=fake)
	assert not consumer.poll_once()
	fake.message = FakeMessage(request)
	fake.message.key = lambda: b"other-execution"
	with pytest.raises(ValueError, match="key"):
		consumer.poll_once()
	assert fake.commits == []


def test_kafka_configuration_is_explicit(monkeypatch):
	monkeypatch.delenv("KAFKA_BOOTSTRAP_SERVERS", raising=False)
	monkeypatch.delenv("KAFKA_CONFIG_JSON", raising=False)
	with pytest.raises(ValueError, match="bootstrap"):
		kafka_config_from_env()
	monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker:9093")
	monkeypatch.setenv("KAFKA_CONFIG_JSON", '{"security.protocol":"SASL_SSL"}')
	assert kafka_config_from_env() == {"bootstrap.servers": "broker:9093", "security.protocol": "SASL_SSL"}


def test_kafka_adapters_enforce_delivery_and_offset_configuration(execution, monkeypatch):
	kafka = pytest.importorskip("confluent_kafka")
	request, _, _ = execution
	producer_configs, consumer_configs = [], []
	def producer(config):
		producer_configs.append(config)
		return FakeProducer()
	def consumer(config):
		consumer_configs.append(config)
		return FakeConsumer(FakeMessage(request))
	monkeypatch.setattr(kafka, "Producer", producer)
	monkeypatch.setattr(kafka, "Consumer", consumer)
	KafkaPublisher({"bootstrap.servers": "unused", "acks": "0"}, "executions").publish_request(request)
	KafkaExecutionConsumer({
		"bootstrap.servers": "unused", "enable.auto.commit": True, "enable.auto.offset.store": True,
	}, "executions", "dispatchers", lambda req: None).poll_once()
	assert producer_configs[0]["enable.idempotence"] is True
	assert producer_configs[0]["acks"] == "all"
	assert consumer_configs[0]["enable.auto.commit"] is False
	assert consumer_configs[0]["enable.auto.offset.store"] is False


def test_launcher_imports_no_backend_or_operation_catalog():
	subprocess.run([
		sys.executable, "-c",
		"import sys; import engine.dispatch.worker; "
		"assert not any(x in sys.modules for x in "
		"('pandas', 'polars', 'pyspark', 'engine.ir.catalog', 'engine.codegen', 'confluent_kafka'))",
	], cwd=ROOT, check=True)


def test_isolated_request_and_job_cli(execution, tmp_path):
	_, _, directory = execution
	params = tmp_path / "params.json"
	params.write_text(json.dumps({"source": "input.csv"}))
	request_path = tmp_path / "request.json"
	profiles_path = tmp_path / "profiles.json"
	profiles_path.write_text(json.dumps({"python-pandas-v1": {"image": "approved-image", "framework": "pandas"}}))
	job_path = tmp_path / "job.json"
	subprocess.run([
		sys.executable, "-m", "engine.dispatch", "request", "--artifact-dir", str(directory),
		"--execution-id", "exec-2", "--params-file", str(params), "--output", str(request_path),
	], cwd=ROOT, check=True)
	subprocess.run([
		sys.executable, "-m", "engine.dispatch", "prepare", "--request", str(request_path),
		"--artifact-root", str(tmp_path), "--profiles", str(profiles_path), "--output", str(job_path),
	], cwd=ROOT, check=True)
	assert json.loads(job_path.read_text())["kind"] == "Job"
