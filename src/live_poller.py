"""Optionally poll NOAA's current Kp feed and publish new events to Kafka."""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from pydantic import ValidationError

from src.contract import KpEvent, NOAA_KP_SOURCE, normalize_noaa_record
from src.kafka_io import (
    DEFAULT_BOOTSTRAP_SERVERS,
    PublishedEvent,
    ensure_kp_topic,
    new_producer,
    publish_event,
)


DEFAULT_POLL_INTERVAL_SECONDS = 60.0
DEFAULT_HTTP_TIMEOUT_SECONDS = 15.0
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = PROJECT_ROOT / ".state/live_poller.json"


class LivePollerError(RuntimeError):
    """Raised when one NOAA poll cannot provide a usable response."""


@dataclass(frozen=True)
class PollResult:
    received_records: int
    valid_events: int
    invalid_records: int
    published: tuple[PublishedEvent, ...]
    newest_time_tag: datetime | None


def fetch_noaa_records(
    *,
    timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
    get: Callable[..., Any] = requests.get,
) -> list[Mapping[str, Any]]:
    """Fetch one bounded NOAA response and require its documented array shape."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    try:
        response = get(
            NOAA_KP_SOURCE,
            timeout=timeout_seconds,
            headers={"Accept": "application/json", "Accept-Encoding": "identity"},
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise LivePollerError(f"NOAA request failed: {exc}") from exc

    if not isinstance(payload, list):
        raise LivePollerError("NOAA response must be a JSON array")
    if not payload:
        raise LivePollerError("NOAA response contained no records")
    if not all(isinstance(record, Mapping) for record in payload):
        raise LivePollerError("NOAA response records must be JSON objects")
    return payload


def normalize_response(
    records: Sequence[Mapping[str, Any]],
    *,
    ingested_at: datetime,
    logger: logging.Logger,
) -> tuple[list[KpEvent], int]:
    """Normalize valid records, logging and counting unusable source rows."""

    by_time: dict[datetime, KpEvent] = {}
    invalid = 0
    for position, record in enumerate(records):
        try:
            event = normalize_noaa_record(record, ingested_at=ingested_at)
        except (ValidationError, ValueError) as exc:
            invalid += 1
            logger.warning("Skipping invalid NOAA record %s: %s", position, exc)
            continue
        by_time[event.time_tag] = event
    return [by_time[tag] for tag in sorted(by_time)], invalid


def poll_once(
    producer: Any,
    seen_time_tags: set[datetime],
    *,
    timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
    fetch: Callable[..., list[Mapping[str, Any]]] = fetch_noaa_records,
    publish: Callable[..., PublishedEvent] = publish_event,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    logger: logging.Logger | None = None,
) -> PollResult:
    """Fetch NOAA once and publish timestamps not already seen in this process.

    The first successful poll publishes only the newest valid observation. This
    avoids treating NOAA's approximately six-hour response as a new live backlog.
    Later polls publish every valid timestamp that appeared after that baseline.
    """

    log = logger or logging.getLogger(__name__)
    records = fetch(timeout_seconds=timeout_seconds)
    events, invalid = normalize_response(records, ingested_at=now(), logger=log)
    if not events:
        raise LivePollerError("NOAA response contained no valid records")

    startup_baseline: set[datetime] = set()
    if seen_time_tags:
        newest_seen = max(seen_time_tags)
        candidates = [event for event in events if event.time_tag > newest_seen]
    else:
        candidates = [events[-1]]
        # Treat the complete first response as the startup baseline even though
        # only its newest event is published. Otherwise the next poll would
        # incorrectly publish the older records as newly arrived observations.
        startup_baseline = {event.time_tag for event in events}
    published: list[PublishedEvent] = []
    for event in candidates:
        published.append(publish(producer, event))
        seen_time_tags.add(event.time_tag)
    if startup_baseline:
        seen_time_tags.update(startup_baseline)

    return PollResult(
        received_records=len(records),
        valid_events=len(events),
        invalid_records=invalid,
        published=tuple(published),
        newest_time_tag=events[-1].time_tag,
    )


def load_checkpoint(path: Path | str = DEFAULT_STATE_PATH) -> set[datetime]:
    """Load the newest successfully handled timestamp from local runtime state."""

    state_path = Path(path)
    if not state_path.exists():
        return set()
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        raw_timestamp = payload["newest_time_tag"]
        checkpoint = KpEvent.model_validate(
            {
                "time_tag": raw_timestamp,
                "kp_value": 0,
                "source": NOAA_KP_SOURCE,
                "ingested_at": raw_timestamp,
            }
        ).time_tag
    except (OSError, KeyError, TypeError, ValueError, ValidationError) as exc:
        raise LivePollerError(f"Could not read poller checkpoint {state_path}") from exc
    return {checkpoint}


def save_checkpoint(
    seen_time_tags: set[datetime], path: Path | str = DEFAULT_STATE_PATH
) -> None:
    """Atomically save the newest handled timestamp without committing runtime state."""

    if not seen_time_tags:
        return
    state_path = Path(path)
    temporary = state_path.with_suffix(state_path.suffix + ".tmp")
    serialized = max(seen_time_tags).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps({"newest_time_tag": serialized}, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(state_path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise LivePollerError(f"Could not save poller checkpoint {state_path}") from exc


def run_poller(
    *,
    bootstrap_servers: str = DEFAULT_BOOTSTRAP_SERVERS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
    once: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    logger: logging.Logger | None = None,
    state_path: Path | str = DEFAULT_STATE_PATH,
    ensure_topic: Callable[[str], None] = ensure_kp_topic,
    make_producer: Callable[[str], Any] = new_producer,
    poll: Callable[..., PollResult] = poll_once,
) -> int:
    """Run one poll or continue at a safe interval, retrying after failures."""

    if poll_interval_seconds < DEFAULT_POLL_INTERVAL_SECONDS:
        raise ValueError("poll_interval_seconds must be at least 60")
    log = logger or logging.getLogger(__name__)
    ensure_topic(bootstrap_servers)
    producer = make_producer(bootstrap_servers)
    seen = load_checkpoint(state_path)

    while True:
        try:
            result = poll(
                producer,
                seen,
                timeout_seconds=timeout_seconds,
                logger=log,
            )
            if result.published:
                latest = result.published[-1]
                log.info(
                    "Published %s new NOAA event(s) to %s at offsets through %s",
                    len(result.published),
                    latest.topic,
                    latest.offset,
                )
            else:
                newest = (
                    result.newest_time_tag.isoformat()
                    if result.newest_time_tag
                    else "none"
                )
                log.info("No new NOAA timestamp; newest source record is %s", newest)
            save_checkpoint(seen, state_path)
        except (LivePollerError, RuntimeError, ValueError) as exc:
            log.error("Live NOAA poll failed; will retry on the next interval: %s", exc)
            if once:
                return 1
        if once:
            return 0
        sleep(poll_interval_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Poll live NOAA Kp estimates and publish new timestamps to Kafka."
    )
    parser.add_argument(
        "--bootstrap-servers",
        default=DEFAULT_BOOTSTRAP_SERVERS,
        help="Kafka bootstrap address (default: localhost:9092)",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help="Polling interval; must be at least 60 seconds",
    )
    parser.add_argument(
        "--http-timeout-seconds",
        type=float,
        default=DEFAULT_HTTP_TIMEOUT_SECONDS,
        help="Positive timeout for each NOAA request",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Fetch once, publish the newest observation, and exit",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help="Local checkpoint file used to suppress timestamps across restarts",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    try:
        return run_poller(
            bootstrap_servers=args.bootstrap_servers,
            poll_interval_seconds=args.poll_interval_seconds,
            timeout_seconds=args.http_timeout_seconds,
            once=args.once,
            state_path=args.state_file,
        )
    except (RuntimeError, ValueError) as exc:
        logging.error("Live poller could not start: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
