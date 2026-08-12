import os
import uuid

import pytest
from confluent_kafka import Consumer, TopicPartition

from src.kafka_io import (
    KP_MESSAGE_KEY,
    KP_TOPIC,
    consume_event,
    consumer_config,
    ensure_kp_topic,
    new_producer,
)
from src.replay_producer import load_replay, replay_events


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("RUN_KAFKA_INTEGRATION") != "1",
    reason="set RUN_KAFKA_INTEGRATION=1 with a clean Docker broker running",
)
def test_all_replay_events_arrive_in_exact_order_through_real_kafka() -> None:
    expected = load_replay()
    ensure_kp_topic()
    consumer = Consumer(consumer_config(f"replay-integration-{uuid.uuid4()}"))
    partition = TopicPartition(KP_TOPIC, 0)
    _, starting_offset = consumer.get_watermark_offsets(partition, timeout=10)
    consumer.assign([TopicPartition(KP_TOPIC, 0, starting_offset)])

    try:
        published = replay_events(new_producer(), expected)
        consumed = [consume_event(consumer, timeout_seconds=15) for _ in expected]
    finally:
        consumer.close()

    assert len(published) == len(consumed) == 9
    assert all(item.key == KP_MESSAGE_KEY for item in published)
    assert all(item.key == KP_MESSAGE_KEY for item in consumed)
    assert [item.partition for item in published] == [0] * 9
    assert [item.partition for item in consumed] == [0] * 9
    assert [item.event for item in consumed] == expected
    assert consumed[2].event == consumed[3].event
