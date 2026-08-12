import json
import os
import uuid
from pathlib import Path

import pytest

from src.contract import KpEvent
from src.kafka_io import (
    KP_MESSAGE_KEY,
    KP_TOPIC,
    ensure_kp_topic,
    new_consumer,
    new_producer,
    publish_event,
    consume_event,
)


pytestmark = pytest.mark.integration
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    os.getenv("RUN_KAFKA_INTEGRATION") != "1",
    reason="set RUN_KAFKA_INTEGRATION=1 with the Docker broker running",
)
def test_representative_event_round_trips_through_real_kafka() -> None:
    expected = KpEvent.model_validate_json(
        (PROJECT_ROOT / "data/fixtures/representative_event.json").read_text()
    )
    ensure_kp_topic()
    consumer = new_consumer(f"kafka-integration-{uuid.uuid4()}")

    try:
        published = publish_event(new_producer(), expected)
        consumed = consume_event(consumer, timeout_seconds=15)
    finally:
        consumer.close()

    assert published.topic == KP_TOPIC
    assert published.partition == 0
    assert published.key == KP_MESSAGE_KEY
    assert json.loads(published.value) == expected.model_dump(mode="json")
    assert consumed.topic == KP_TOPIC
    assert consumed.partition == 0
    assert consumed.key == KP_MESSAGE_KEY
    assert consumed.event == expected
