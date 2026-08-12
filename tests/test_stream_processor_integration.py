import csv
import json
import os
import uuid
from pathlib import Path

import pytest
from confluent_kafka import Consumer, TopicPartition

from src.kafka_io import KP_TOPIC, consumer_config, ensure_kp_topic, new_producer
from src.replay_producer import load_replay, replay_events
from src.stream_processor import run_stream_processor


pytestmark = pytest.mark.integration
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    os.getenv("RUN_KAFKA_INTEGRATION") != "1",
    reason="set RUN_KAFKA_INTEGRATION=1 with the Docker broker running",
)
def test_real_kafka_replay_writes_exact_expected_artifacts(tmp_path: Path) -> None:
    expected = json.loads(
        (PROJECT_ROOT / "data/fixtures/replay_expected.json").read_text()
    )
    events = load_replay()
    ensure_kp_topic()
    consumer = Consumer(consumer_config(f"processor-integration-{uuid.uuid4()}"))
    partition = TopicPartition(KP_TOPIC, 0)
    _, starting_offset = consumer.get_watermark_offsets(partition, timeout=10)
    consumer.assign([TopicPartition(KP_TOPIC, 0, starting_offset)])

    published = replay_events(new_producer(), events)
    completed = run_stream_processor(
        consumer,
        expected_events=len(events),
        alert_path=tmp_path / "alert.json",
        metrics_path=tmp_path / "metrics.csv",
    )

    alert_artifact = json.loads(completed.alert_path.read_text())
    assert len(published) == completed.messages_processed == 9
    assert completed.malformed_messages_skipped == 0
    assert alert_artifact["run_counts"] == expected["expected_counts"]
    assert [
        {
            "triggered_at": alert["triggered_at"],
            "latest_kp": alert["latest_kp"],
            "rolling_15m_max_kp": alert["rolling_15m_max_kp"],
        }
        for alert in alert_artifact["alerts"]
    ] == expected["expected_alerts"]

    with completed.metrics_path.open(newline="", encoding="utf-8") as metrics_file:
        metrics = list(csv.DictReader(metrics_file))
    assert len(metrics) == len(expected["expected_metrics"]) == 9
    for actual, expected_row in zip(
        metrics, expected["expected_metrics"], strict=True
    ):
        assert actual == {
            "time_tag": expected_row["time_tag"],
            "kp_value": str(expected_row["kp_value"]),
            "rolling_15m_max_kp": str(expected_row["rolling_15m_max_kp"]),
            "risk_label": expected_row["risk_label"],
            "alert_emitted": str(expected_row["alert_emitted"]).lower(),
            "processing_status": expected_row["processing_status"],
        }
