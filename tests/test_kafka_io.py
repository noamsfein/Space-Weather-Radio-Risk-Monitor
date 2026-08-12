import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.contract import KpEvent
from src.kafka_io import (
    DEFAULT_BOOTSTRAP_SERVERS,
    KP_MESSAGE_KEY,
    KP_TOPIC,
    KafkaConfigurationError,
    KafkaConsumeTimeout,
    KafkaDeliveryError,
    KafkaIOError,
    consume_event,
    consumer_config,
    ensure_kp_topic,
    producer_config,
    publish_event,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def representative_event() -> KpEvent:
    return KpEvent.model_validate_json(
        (PROJECT_ROOT / "data/fixtures/representative_event.json").read_text()
    )


@dataclass
class FakeMessage:
    key_value: bytes | None = KP_MESSAGE_KEY.encode()
    value_value: bytes | None = None
    error_value: object | None = None

    def topic(self) -> str:
        return KP_TOPIC

    def partition(self) -> int:
        return 0

    def offset(self) -> int:
        return 4

    def key(self) -> bytes | None:
        return self.key_value

    def value(self) -> bytes | None:
        return self.value_value

    def error(self) -> object | None:
        return self.error_value


class FakeProducer:
    def __init__(self, *, remaining: int = 0, delivery_error: object | None = None):
        self.remaining = remaining
        self.delivery_error = delivery_error
        self.produced: list[dict] = []

    def produce(self, topic: str, **kwargs: object) -> None:
        self.produced.append({"topic": topic, **kwargs})
        callback = kwargs["on_delivery"]
        callback(self.delivery_error, FakeMessage(value_value=kwargs["value"].encode()))

    def flush(self, timeout: float) -> int:
        assert timeout > 0
        return self.remaining


class FakeConsumer:
    def __init__(self, messages: list[FakeMessage | None]):
        self.messages = iter(messages)

    def poll(self, timeout: float) -> FakeMessage | None:
        assert timeout > 0
        return next(self.messages, None)


class FakeTopicMetadata:
    def __init__(self, partition_count: int):
        self.partitions = {number: object() for number in range(partition_count)}
        self.error = None


class FakeClusterMetadata:
    def __init__(self, topics: dict[str, FakeTopicMetadata]):
        self.topics = topics


class FakeFuture:
    def __init__(self):
        self.result_calls: list[float] = []

    def result(self, timeout: float) -> None:
        self.result_calls.append(timeout)


class FakeAdmin:
    def __init__(self, *, topic_exists: bool, partition_count: int = 1):
        self.topic_exists = topic_exists
        self.partition_count = partition_count
        self.create_calls: list[list] = []
        self.future = FakeFuture()

    def list_topics(self, topic: str | None = None, timeout: float = 10):
        topics = {}
        if self.topic_exists or topic == KP_TOPIC:
            topics[KP_TOPIC] = FakeTopicMetadata(self.partition_count)
        return FakeClusterMetadata(topics)

    def create_topics(self, topics: list) -> dict[str, FakeFuture]:
        self.create_calls.append(topics)
        self.topic_exists = True
        return {KP_TOPIC: self.future}


def test_kafka_constants_and_configs_are_deterministic() -> None:
    assert DEFAULT_BOOTSTRAP_SERVERS == "localhost:9092"
    assert KP_TOPIC == "kp_observations"
    assert KP_MESSAGE_KEY == "planetary_kp"
    assert producer_config() == {
        "bootstrap.servers": "localhost:9092",
        "client.id": "space-weather-producer",
        "enable.idempotence": True,
        "acks": "all",
    }
    assert consumer_config("test-group") == {
        "bootstrap.servers": "localhost:9092",
        "group.id": "test-group",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    }


def test_consumer_config_rejects_blank_group() -> None:
    with pytest.raises(ValueError, match="group_id must not be blank"):
        consumer_config("  ")


def test_ensure_topic_is_idempotent_when_contract_matches() -> None:
    admin = FakeAdmin(topic_exists=True)

    ensure_kp_topic(admin_client=admin)

    assert admin.create_calls == []


def test_ensure_topic_creates_missing_one_partition_topic() -> None:
    admin = FakeAdmin(topic_exists=False)

    ensure_kp_topic(admin_client=admin, timeout_seconds=3)

    assert len(admin.create_calls) == 1
    requested = admin.create_calls[0][0]
    assert requested.topic == KP_TOPIC
    assert requested.num_partitions == 1
    assert requested.replication_factor == 1
    assert admin.future.result_calls == [3]


def test_ensure_topic_rejects_wrong_partition_count() -> None:
    admin = FakeAdmin(topic_exists=True, partition_count=2)

    with pytest.raises(KafkaConfigurationError, match="exactly 1 partition"):
        ensure_kp_topic(admin_client=admin)


def test_publish_event_sends_exact_key_and_canonical_json() -> None:
    producer = FakeProducer()
    event = representative_event()

    result = publish_event(producer, event)

    assert len(producer.produced) == 1
    produced = producer.produced[0]
    assert produced["topic"] == KP_TOPIC
    assert produced["key"] == KP_MESSAGE_KEY
    assert json.loads(produced["value"]) == event.model_dump(mode="json")
    assert result.topic == KP_TOPIC
    assert result.key == KP_MESSAGE_KEY
    assert result.value == event.model_dump_json()


@pytest.mark.parametrize(
    ("producer", "expected_error"),
    [
        (FakeProducer(remaining=1), "still queued"),
        (FakeProducer(delivery_error="broker failure"), "delivery failed"),
    ],
)
def test_publish_event_rejects_unconfirmed_delivery(
    producer: FakeProducer, expected_error: str
) -> None:
    with pytest.raises(KafkaDeliveryError, match=expected_error):
        publish_event(producer, representative_event())


def test_consume_event_returns_validated_event() -> None:
    expected = representative_event()
    consumer = FakeConsumer(
        [None, FakeMessage(value_value=expected.model_dump_json().encode())]
    )

    result = consume_event(consumer, timeout_seconds=1)

    assert result.topic == KP_TOPIC
    assert result.partition == 0
    assert result.offset == 4
    assert result.key == KP_MESSAGE_KEY
    assert result.event == expected


@pytest.mark.parametrize(
    ("message", "expected_error"),
    [
        (
            FakeMessage(key_value=b"wrong", value_value=b"{}"),
            "message key must be",
        ),
        (
            FakeMessage(value_value=b"not-json"),
            "not a valid KpEvent",
        ),
        (
            FakeMessage(value_value=b"{}", error_value="consume failure"),
            "consume failed",
        ),
    ],
)
def test_consume_event_rejects_bad_messages(
    message: FakeMessage, expected_error: str
) -> None:
    with pytest.raises(KafkaIOError, match=expected_error):
        consume_event(FakeConsumer([message]), timeout_seconds=1)


def test_consume_event_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = iter([10.0, 10.0, 10.2])
    monkeypatch.setattr("src.kafka_io.time.monotonic", lambda: next(clock))

    with pytest.raises(KafkaConsumeTimeout, match="within 0.1 seconds"):
        consume_event(FakeConsumer([None]), timeout_seconds=0.1)


@pytest.mark.parametrize("timeout", [0, -1])
def test_operations_reject_nonpositive_timeout(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        publish_event(FakeProducer(), representative_event(), timeout_seconds=timeout)
    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        consume_event(FakeConsumer([]), timeout_seconds=timeout)
