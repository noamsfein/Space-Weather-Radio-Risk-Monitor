"""Consume a finite Kafka stream, process it, and write project artifacts."""

from __future__ import annotations

import argparse
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.alert_output import DEFAULT_ALERT_PATH, write_alert_output
from src.kafka_io import (
    DEFAULT_BOOTSTRAP_SERVERS,
    KafkaIOError,
    KafkaMessageError,
    consume_event,
    ensure_kp_topic,
    new_consumer,
)
from src.metrics_output import DEFAULT_METRICS_PATH, write_metrics_output
from src.processor import ProcessingResult, RollingKpProcessor


DEFAULT_EXPECTED_EVENTS = 9
DEFAULT_IDLE_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class StreamRunResult:
    results: tuple[ProcessingResult, ...]
    malformed_messages_skipped: int
    alert_path: Path
    metrics_path: Path

    @property
    def messages_processed(self) -> int:
        return len(self.results)


def run_stream_processor(
    consumer: Any,
    *,
    expected_events: int = DEFAULT_EXPECTED_EVENTS,
    idle_timeout_seconds: float = DEFAULT_IDLE_TIMEOUT_SECONDS,
    alert_path: str | Path = DEFAULT_ALERT_PATH,
    metrics_path: str | Path = DEFAULT_METRICS_PATH,
    consume: Callable[..., Any] = consume_event,
    alert_writer: Callable[..., Any] = write_alert_output,
    metrics_writer: Callable[..., Any] = write_metrics_output,
    report: Callable[[str], None] = print,
) -> StreamRunResult:
    """Process exactly ``expected_events`` valid events and always close consumer."""

    alert_target = Path(alert_path)
    metrics_target = Path(metrics_path)
    results: list[ProcessingResult] = []
    malformed_messages_skipped = 0

    try:
        if expected_events <= 0:
            raise ValueError("expected_events must be positive")
        if idle_timeout_seconds <= 0:
            raise ValueError("idle_timeout_seconds must be positive")

        processor = RollingKpProcessor()
        while len(results) < expected_events:
            try:
                consumed = consume(consumer, timeout_seconds=idle_timeout_seconds)
            except KafkaMessageError as exc:
                malformed_messages_skipped += 1
                report(f"Skipped malformed Kafka message: {exc}")
                continue
            results.append(processor.process(consumed.event))

        alert_writer(results, alert_target)
        metrics_writer(results, metrics_target)
    finally:
        consumer.close()

    return StreamRunResult(
        results=tuple(results),
        malformed_messages_skipped=malformed_messages_skipped,
        alert_path=alert_target,
        metrics_path=metrics_target,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Consume Kp events and write deterministic project outputs."
    )
    parser.add_argument(
        "--bootstrap-servers",
        default=DEFAULT_BOOTSTRAP_SERVERS,
        help="Kafka bootstrap address (default: localhost:9092)",
    )
    parser.add_argument(
        "--group-id",
        default=None,
        help="Kafka consumer group (default: unique project run group)",
    )
    parser.add_argument(
        "--expected-events",
        type=int,
        default=DEFAULT_EXPECTED_EVENTS,
        help="Number of valid events required before writing outputs",
    )
    parser.add_argument(
        "--idle-timeout-seconds",
        type=float,
        default=DEFAULT_IDLE_TIMEOUT_SECONDS,
        help="Fail if the next valid Kafka event does not arrive in this time",
    )
    parser.add_argument("--alert-path", type=Path, default=DEFAULT_ALERT_PATH)
    parser.add_argument("--metrics-path", type=Path, default=DEFAULT_METRICS_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    group_id = args.group_id or f"space-weather-processor-{uuid.uuid4()}"

    try:
        ensure_kp_topic(args.bootstrap_servers)
        consumer = new_consumer(group_id, args.bootstrap_servers)
        completed = run_stream_processor(
            consumer,
            expected_events=args.expected_events,
            idle_timeout_seconds=args.idle_timeout_seconds,
            alert_path=args.alert_path,
            metrics_path=args.metrics_path,
        )
    except (KafkaIOError, OSError, ValueError) as exc:
        print(f"Stream processing failed: {exc}")
        return 1

    alerts_emitted = sum(result.alert_emitted for result in completed.results)
    print(
        f"Processed {completed.messages_processed} valid event(s); "
        f"skipped {completed.malformed_messages_skipped} malformed; "
        f"emitted {alerts_emitted} alert(s)"
    )
    print(f"Wrote {completed.alert_path} and {completed.metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
