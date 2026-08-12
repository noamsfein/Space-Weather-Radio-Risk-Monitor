from dataclasses import dataclass
from pathlib import Path

import pytest

import src.stream_processor as stream_processor
from src.kafka_io import (
    ConsumedEvent,
    KafkaConsumeTimeout,
    KafkaIOError,
    KafkaMessageError,
)
from src.replay_producer import load_replay
from src.stream_processor import main, run_stream_processor


@dataclass
class FakeConsumer:
    closed: bool = False

    def close(self) -> None:
        self.closed = True


def consumed(position: int) -> ConsumedEvent:
    return ConsumedEvent(
        topic="kp_observations",
        partition=0,
        offset=position,
        key="planetary_kp",
        event=load_replay()[position],
    )


def test_finite_run_processes_expected_events_writes_outputs_and_closes(
    tmp_path: Path,
) -> None:
    consumer = FakeConsumer()
    messages = iter(consumed(position) for position in range(9))
    consumed_timeouts: list[float] = []

    def consume_next(fake_consumer: FakeConsumer, *, timeout_seconds: float):
        assert fake_consumer is consumer
        consumed_timeouts.append(timeout_seconds)
        return next(messages)

    completed = run_stream_processor(
        consumer,
        consume=consume_next,
        alert_path=tmp_path / "alert.json",
        metrics_path=tmp_path / "metrics.csv",
    )

    assert completed.messages_processed == 9
    assert completed.malformed_messages_skipped == 0
    assert sum(result.alert_emitted for result in completed.results) == 2
    assert consumed_timeouts == [15.0] * 9
    assert completed.alert_path.is_file()
    assert completed.metrics_path.is_file()
    assert consumer.closed is True


def test_malformed_message_is_reported_and_does_not_count_as_valid(
    tmp_path: Path,
) -> None:
    consumer = FakeConsumer()
    calls = iter([KafkaMessageError("bad JSON"), consumed(0)])
    messages: list[str] = []

    def consume_next(*args, **kwargs):
        outcome = next(calls)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    completed = run_stream_processor(
        consumer,
        expected_events=1,
        consume=consume_next,
        alert_path=tmp_path / "alert.json",
        metrics_path=tmp_path / "metrics.csv",
        report=messages.append,
    )

    assert completed.messages_processed == 1
    assert completed.malformed_messages_skipped == 1
    assert messages == ["Skipped malformed Kafka message: bad JSON"]
    assert consumer.closed is True


@pytest.mark.parametrize(
    "failure",
    [KafkaConsumeTimeout("idle timeout"), RuntimeError("broker failure")],
)
def test_consume_failure_propagates_without_writing_and_closes(
    tmp_path: Path, failure: Exception
) -> None:
    consumer = FakeConsumer()

    def fail_consume(*args, **kwargs):
        raise failure

    with pytest.raises(type(failure), match=str(failure)):
        run_stream_processor(
            consumer,
            expected_events=1,
            consume=fail_consume,
            alert_path=tmp_path / "alert.json",
            metrics_path=tmp_path / "metrics.csv",
        )

    assert not (tmp_path / "alert.json").exists()
    assert not (tmp_path / "metrics.csv").exists()
    assert consumer.closed is True


def test_output_failure_propagates_and_closes_consumer(tmp_path: Path) -> None:
    consumer = FakeConsumer()

    def fail_alert_writer(*args, **kwargs):
        raise OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        run_stream_processor(
            consumer,
            expected_events=1,
            consume=lambda *args, **kwargs: consumed(0),
            alert_writer=fail_alert_writer,
            metrics_writer=lambda *args, **kwargs: pytest.fail(
                "metrics writer must not run after alert failure"
            ),
            alert_path=tmp_path / "alert.json",
            metrics_path=tmp_path / "metrics.csv",
        )

    assert consumer.closed is True


@pytest.mark.parametrize(
    ("expected_events", "timeout", "message"),
    [(0, 1, "expected_events must be positive"), (1, 0, "idle_timeout")],
)
def test_invalid_limits_still_close_consumer(
    expected_events: int, timeout: float, message: str
) -> None:
    consumer = FakeConsumer()

    with pytest.raises(ValueError, match=message):
        run_stream_processor(
            consumer,
            expected_events=expected_events,
            idle_timeout_seconds=timeout,
        )

    assert consumer.closed is True


def test_main_returns_nonzero_when_kafka_setup_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        stream_processor,
        "ensure_kp_topic",
        lambda *args, **kwargs: (_ for _ in ()).throw(KafkaIOError("offline")),
    )

    exit_code = main([])

    assert exit_code == 1
    assert "Stream processing failed: offline" in capsys.readouterr().out
