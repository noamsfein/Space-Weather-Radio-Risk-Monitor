"""Validate and publish a deterministic JSONL replay through Kafka."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.contract import KpEvent
from src.kafka_io import (
    DEFAULT_BOOTSTRAP_SERVERS,
    PublishedEvent,
    ensure_kp_topic,
    new_producer,
    publish_event,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPLAY_PATH = PROJECT_ROOT / "data/sample_or_replay_data/kp_replay.jsonl"


class ReplayError(RuntimeError):
    """Base error for invalid or incomplete replay work."""


class ReplayFileError(ReplayError):
    """Raised when the replay file cannot be read or contains invalid JSONL."""


class ReplayValidationError(ReplayError):
    """Raised when a replay record violates the canonical event contract."""


class ReplayOrderError(ReplayError):
    """Raised when event time decreases between consecutive replay records."""


def load_replay(path: Path | str = DEFAULT_REPLAY_PATH) -> list[KpEvent]:
    """Read and fully validate a replay before any event is published."""

    replay_path = Path(path)
    try:
        lines = replay_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ReplayFileError(f"Could not read replay file: {replay_path}") from exc

    events: list[KpEvent] = []
    previous: KpEvent | None = None
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise ReplayFileError(
                f"Replay file contains a blank line at line {line_number}"
            )
        try:
            raw: Any = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReplayFileError(
                f"Replay file has invalid JSON at line {line_number}"
            ) from exc
        if not isinstance(raw, dict):
            raise ReplayValidationError(
                f"Replay record at line {line_number} must be a JSON object"
            )
        try:
            event = KpEvent.model_validate(raw)
        except ValidationError as exc:
            raise ReplayValidationError(
                f"Replay record at line {line_number} is not a valid KpEvent: {exc}"
            ) from exc

        if previous is not None and event.time_tag < previous.time_tag:
            raise ReplayOrderError(
                "Replay event time decreased at line "
                f"{line_number}: {event.time_tag.isoformat()} < "
                f"{previous.time_tag.isoformat()}"
            )
        events.append(event)
        previous = event

    if not events:
        raise ReplayFileError(f"Replay file contains no events: {replay_path}")
    return events


def replay_events(
    producer: Any,
    events: Sequence[KpEvent],
    *,
    delay_seconds: float = 0,
    publish: Callable[..., PublishedEvent] = publish_event,
    sleep: Callable[[float], None] = time.sleep,
) -> list[PublishedEvent]:
    """Publish validated events in sequence, preserving duplicate timestamps."""

    if delay_seconds < 0:
        raise ValueError("delay_seconds must not be negative")
    if not events:
        raise ReplayValidationError("Replay requires at least one event")

    published: list[PublishedEvent] = []
    previous: KpEvent | None = None
    for position, event in enumerate(events):
        if previous is not None and event.time_tag < previous.time_tag:
            raise ReplayOrderError(
                f"Replay event time decreased at position {position + 1}"
            )
        if position and delay_seconds:
            sleep(delay_seconds)
        published.append(publish(producer, event))
        previous = event
    return published


def run_replay(
    path: Path | str = DEFAULT_REPLAY_PATH,
    *,
    bootstrap_servers: str = DEFAULT_BOOTSTRAP_SERVERS,
    delay_seconds: float = 0,
) -> list[PublishedEvent]:
    """Validate the full file, prepare Kafka, and publish the finite replay."""

    events = load_replay(path)
    ensure_kp_topic(bootstrap_servers)
    return replay_events(
        new_producer(bootstrap_servers), events, delay_seconds=delay_seconds
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish the deterministic Kp JSONL replay through Kafka."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_REPLAY_PATH,
        help="JSONL replay file (default: project fixture)",
    )
    parser.add_argument(
        "--bootstrap-servers",
        default=DEFAULT_BOOTSTRAP_SERVERS,
        help="Kafka bootstrap address (default: localhost:9092)",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0,
        help="Nonnegative pause between events for a visible demo",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        published = run_replay(
            args.file,
            bootstrap_servers=args.bootstrap_servers,
            delay_seconds=args.delay_seconds,
        )
    except (ReplayError, RuntimeError, ValueError) as exc:
        print(f"Replay failed: {exc}")
        return 1

    print(f"Published {len(published)} event(s) from {args.file}")
    print(
        f"Topic={published[0].topic} key={published[0].key} "
        f"partitions={sorted({item.partition for item in published})}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
