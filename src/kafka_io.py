"""Small, shared Kafka boundary for the project producer and consumer."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from src.contract import KpEvent


DEFAULT_BOOTSTRAP_SERVERS = "localhost:9092"
KP_TOPIC = "kp_observations"
KP_MESSAGE_KEY = "planetary_kp"
KP_TOPIC_PARTITIONS = 1


class KafkaIOError(RuntimeError):
    """Base error for a failed bounded Kafka operation."""


class KafkaUnavailableError(KafkaIOError):
    """Raised when broker metadata cannot be obtained in time."""


class KafkaConfigurationError(KafkaIOError):
    """Raised when the existing topic does not match the project contract."""


class KafkaDeliveryError(KafkaIOError):
    """Raised when a producer cannot confirm event delivery."""


class KafkaConsumeTimeout(KafkaIOError):
    """Raised when no Kafka event arrives before the requested deadline."""


@dataclass(frozen=True)
class PublishedEvent:
    topic: str
    partition: int
    offset: int
    key: str
    value: str


@dataclass(frozen=True)
class ConsumedEvent:
    topic: str
    partition: int
    offset: int
    key: str
    event: KpEvent


def producer_config(
    bootstrap_servers: str = DEFAULT_BOOTSTRAP_SERVERS,
) -> dict[str, Any]:
    """Return deterministic settings shared by all project producers."""

    return {
        "bootstrap.servers": bootstrap_servers,
        "client.id": "space-weather-producer",
        "enable.idempotence": True,
        "acks": "all",
    }


def consumer_config(
    group_id: str,
    bootstrap_servers: str = DEFAULT_BOOTSTRAP_SERVERS,
) -> dict[str, Any]:
    """Return finite-replay-safe settings shared by project consumers."""

    if not group_id.strip():
        raise ValueError("group_id must not be blank")
    return {
        "bootstrap.servers": bootstrap_servers,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    }


def ensure_kp_topic(
    bootstrap_servers: str = DEFAULT_BOOTSTRAP_SERVERS,
    *,
    timeout_seconds: float = 10,
    admin_client: AdminClient | None = None,
) -> None:
    """Create the project topic if absent and enforce its one-partition contract."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    admin = admin_client or AdminClient({"bootstrap.servers": bootstrap_servers})
    try:
        metadata = admin.list_topics(timeout=timeout_seconds)
    except KafkaException as exc:
        raise KafkaUnavailableError(
            f"Could not reach Kafka at {bootstrap_servers}"
        ) from exc

    topic_metadata = metadata.topics.get(KP_TOPIC)
    if topic_metadata is None:
        future = admin.create_topics(
            [
                NewTopic(
                    KP_TOPIC,
                    num_partitions=KP_TOPIC_PARTITIONS,
                    replication_factor=1,
                )
            ]
        )[KP_TOPIC]
        try:
            future.result(timeout=timeout_seconds)
        except KafkaException as exc:
            error_code = (
                getattr(exc.args[0], "code", lambda: None)() if exc.args else None
            )
            if error_code != KafkaError.TOPIC_ALREADY_EXISTS:
                raise KafkaIOError(f"Could not create Kafka topic {KP_TOPIC}") from exc

        try:
            topic_metadata = admin.list_topics(
                topic=KP_TOPIC, timeout=timeout_seconds
            ).topics[KP_TOPIC]
        except (KafkaException, KeyError) as exc:
            raise KafkaIOError(f"Could not verify Kafka topic {KP_TOPIC}") from exc

    if topic_metadata.error is not None:
        raise KafkaIOError(f"Kafka topic metadata error: {topic_metadata.error}")
    if len(topic_metadata.partitions) != KP_TOPIC_PARTITIONS:
        raise KafkaConfigurationError(
            f"{KP_TOPIC} must have exactly {KP_TOPIC_PARTITIONS} partition"
        )


def publish_event(
    producer: Producer,
    event: KpEvent,
    *,
    timeout_seconds: float = 10,
) -> PublishedEvent:
    """Publish one canonical event and require delivery confirmation."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    value = event.model_dump_json()
    delivery: list[tuple[Any, Any]] = []

    try:
        producer.produce(
            KP_TOPIC,
            key=KP_MESSAGE_KEY,
            value=value,
            on_delivery=lambda error, message: delivery.append((error, message)),
        )
        remaining = producer.flush(timeout_seconds)
    except (BufferError, KafkaException) as exc:
        raise KafkaDeliveryError("Kafka rejected the event before delivery") from exc

    if remaining != 0:
        raise KafkaDeliveryError(
            f"Kafka delivery timed out with {remaining} event(s) still queued"
        )
    if len(delivery) != 1:
        raise KafkaDeliveryError("Kafka did not return one delivery confirmation")

    error, message = delivery[0]
    if error is not None:
        raise KafkaDeliveryError(f"Kafka delivery failed: {error}")

    return PublishedEvent(
        topic=message.topic(),
        partition=message.partition(),
        offset=message.offset(),
        key=KP_MESSAGE_KEY,
        value=value,
    )


def consume_event(
    consumer: Consumer,
    *,
    timeout_seconds: float = 10,
) -> ConsumedEvent:
    """Consume and validate one canonical project event before a fixed deadline."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise KafkaConsumeTimeout(
                f"No event arrived from {KP_TOPIC} within {timeout_seconds:g} seconds"
            )

        message = consumer.poll(min(1.0, remaining))
        if message is None:
            continue
        if message.error() is not None:
            raise KafkaIOError(f"Kafka consume failed: {message.error()}")

        raw_key = message.key()
        try:
            key = raw_key.decode("utf-8")
        except (AttributeError, UnicodeDecodeError) as exc:
            raise KafkaIOError("Kafka message key must be UTF-8 bytes") from exc
        if key != KP_MESSAGE_KEY:
            raise KafkaIOError(
                f"Kafka message key must be {KP_MESSAGE_KEY!r}, received {key!r}"
            )

        raw_value = message.value()
        try:
            value = raw_value.decode("utf-8")
            event = KpEvent.model_validate_json(value)
        except (AttributeError, UnicodeDecodeError, ValueError) as exc:
            raise KafkaIOError("Kafka message value is not a valid KpEvent") from exc

        return ConsumedEvent(
            topic=message.topic(),
            partition=message.partition(),
            offset=message.offset(),
            key=key,
            event=event,
        )


def new_producer(
    bootstrap_servers: str = DEFAULT_BOOTSTRAP_SERVERS,
) -> Producer:
    return Producer(producer_config(bootstrap_servers))


def new_consumer(
    group_id: str,
    bootstrap_servers: str = DEFAULT_BOOTSTRAP_SERVERS,
) -> Consumer:
    consumer = Consumer(consumer_config(group_id, bootstrap_servers))
    consumer.subscribe([KP_TOPIC])
    return consumer
