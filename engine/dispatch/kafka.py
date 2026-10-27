"""Optional Kafka adapters. No connection is established until explicitly constructed."""

import json
import os
from collections.abc import Callable, Mapping
from typing import Any

from engine.dispatch.contracts import ExecutionRequest


def kafka_config_from_env() -> dict[str, Any]:
	"""Allow TLS/SASL configuration through an injected secret, not source code."""
	config = json.loads(os.environ.get("KAFKA_CONFIG_JSON", "{}"))
	if not isinstance(config, dict):
		raise ValueError("KAFKA_CONFIG_JSON must be an object")
	servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
	if servers:
		config["bootstrap.servers"] = servers
	if not config.get("bootstrap.servers"):
		raise ValueError("Kafka bootstrap.servers is required")
	return config


class KafkaPublisher:
	def __init__(self, config: Mapping[str, Any], topic: str, *, producer: Any = None) -> None:
		if not topic or not config.get("bootstrap.servers"):
			raise ValueError("Kafka topic and bootstrap.servers are required")
		if producer is None:
			from confluent_kafka import Producer
			producer = Producer({**config, "enable.idempotence": True, "acks": "all"})
		self.producer, self.topic = producer, topic

	def publish(self, key: str, value: Mapping[str, Any], timeout: float = 30) -> None:
		errors = []
		delivered = []

		def on_delivery(error, _message):
			if error is not None:
				errors.append(error)
			else:
				delivered.append(True)

		payload = json.dumps(dict(value), allow_nan=False).encode("utf-8")
		self.producer.produce(self.topic, key=key.encode("utf-8"), value=payload, on_delivery=on_delivery)
		remaining = self.producer.flush(timeout)
		if errors:
			raise RuntimeError(f"Kafka delivery failed: {errors[0]}")
		if remaining or not delivered:
			raise TimeoutError("Kafka delivery was not confirmed")

	def publish_request(self, request: ExecutionRequest) -> None:
		self.publish(request.execution_id, request.to_dict())


class KafkaExecutionConsumer:
	def __init__(
		self, config: Mapping[str, Any], topic: str, group_id: str,
		handler: Callable[[ExecutionRequest], Any], *, consumer: Any = None,
	) -> None:
		if not topic or not group_id or not config.get("bootstrap.servers"):
			raise ValueError("Kafka topic, group_id and bootstrap.servers are required")
		if consumer is None:
			from confluent_kafka import Consumer
			consumer = Consumer({
				**config, "group.id": group_id, "enable.auto.commit": False,
				"enable.auto.offset.store": False, "auto.offset.reset": "earliest",
			})
		self.consumer, self.handler = consumer, handler
		self.failed = False
		self.consumer.subscribe([topic])

	def poll_once(self, timeout: float = 1) -> bool:
		if self.failed:
			raise RuntimeError("Consumer failed; close and recreate it before retrying uncommitted messages")
		message = self.consumer.poll(timeout)
		if message is None:
			return False
		acknowledged = False
		try:
			if message.error():
				raise RuntimeError(f"Kafka consumption failed: {message.error()}")
			request = ExecutionRequest.from_dict(json.loads(message.value()))
			if message.key() != request.execution_id.encode("utf-8"):
				raise ValueError("Kafka message key must match execution_id")
			self.handler(request)
			self.consumer.commit(message=message, asynchronous=False)
			acknowledged = True
		finally:
			# Do not let a later offset acknowledge this failed message implicitly.
			if not acknowledged:
				self.failed = True
		return True

	def close(self) -> None:
		self.consumer.close()
