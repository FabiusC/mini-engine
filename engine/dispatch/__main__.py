"""Prepare requests and Kubernetes Jobs locally, or explicitly publish to Kafka."""

import argparse
import hashlib
import json
from pathlib import Path

from engine.dispatch.artifacts import LocalArtifactStore
from engine.dispatch.contracts import ExecutionRequest
from engine.dispatch.dispatcher import Dispatcher, RuntimeProfile


def main() -> None:
	parser = argparse.ArgumentParser(description="Prepare pipeline execution messages and Job specifications")
	commands = parser.add_subparsers(dest="command", required=True)
	request = commands.add_parser("request")
	request.add_argument("--artifact-dir", type=Path, required=True)
	request.add_argument("--execution-id", required=True)
	request.add_argument("--params-file", type=Path)
	request.add_argument("--datasources-file", type=Path)
	request.add_argument("--output", type=Path, required=True)
	job = commands.add_parser("prepare")
	job.add_argument("--request", type=Path, required=True)
	job.add_argument("--artifact-root", type=Path, required=True)
	job.add_argument("--profiles", type=Path, required=True)
	job.add_argument("--output", type=Path, required=True)
	publish = commands.add_parser("publish")
	publish.add_argument("--request", type=Path, required=True)
	publish.add_argument("--topic", required=True)
	args = parser.parse_args()
	if args.command == "request":
		manifest_path = (args.artifact_dir / "manifest.json").resolve(strict=True)
		value = ExecutionRequest(
			args.execution_id, manifest_path.as_uri(), hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
			json.loads(args.params_file.read_text()) if args.params_file else {},
			json.loads(args.datasources_file.read_text()) if args.datasources_file else {},
		).to_dict()
	elif args.command == "prepare":
		request_value = ExecutionRequest.from_dict(json.loads(args.request.read_text()))
		profiles = {
			name: RuntimeProfile(**{**profile, "command": tuple(profile.get("command", ["python"]))})
			for name, profile in json.loads(args.profiles.read_text()).items()
		}
		dispatcher = Dispatcher(LocalArtifactStore(args.artifact_root), profiles, artifact_root=str(args.artifact_root.resolve()))
		value = dispatcher.prepare(request_value)
	else:
		from engine.dispatch.kafka import KafkaPublisher, kafka_config_from_env
		KafkaPublisher(kafka_config_from_env(), args.topic).publish_request(
			ExecutionRequest.from_dict(json.loads(args.request.read_text()))
		)
		return
	with args.output.open("x", encoding="utf-8") as handle:
		json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
		handle.write("\n")


if __name__ == "__main__":
	main()
