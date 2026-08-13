import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

from src.contract import NOAA_KP_SOURCE
from src.kafka_io import KP_MESSAGE_KEY, KP_TOPIC, PublishedEvent
from src.live_poller import (
    LivePollerError,
    PollResult,
    fetch_noaa_records,
    load_checkpoint,
    poll_once,
    run_poller,
    save_checkpoint,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, payload: object, *, json_error: ValueError | None = None):
        self.payload = payload
        self.json_error = json_error

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        if self.json_error:
            raise self.json_error
        return self.payload


def record(minute: int, kp: float = 2.0) -> dict:
    return {
        "time_tag": f"2026-08-12T23:{minute:02d}:00",
        "kp_index": round(kp),
        "estimated_kp": kp,
        "kp": "2Z",
    }


def published(event, offset: int) -> PublishedEvent:
    return PublishedEvent(
        topic=KP_TOPIC,
        partition=0,
        offset=offset,
        key=KP_MESSAGE_KEY,
        value=event.model_dump_json(),
    )


def test_fetch_uses_documented_url_and_timeout() -> None:
    calls = []

    def fake_get(url: str, *, timeout: float, headers: dict):
        calls.append((url, timeout, headers))
        return FakeResponse([record(1)])

    result = fetch_noaa_records(timeout_seconds=7, get=fake_get)

    assert result == [record(1)]
    assert calls == [
        (
            NOAA_KP_SOURCE,
            7,
            {"Accept": "application/json", "Accept-Encoding": "identity"},
        )
    ]


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (FakeResponse([]), "contained no records"),
        (FakeResponse({"time_tag": "wrong-shape"}), "must be a JSON array"),
        (FakeResponse([record(1), "wrong-row"]), "must be JSON objects"),
        (FakeResponse(None, json_error=ValueError("bad json")), "request failed"),
    ],
)
def test_fetch_rejects_empty_invalid_json_and_wrong_shapes(response, message) -> None:
    with pytest.raises(LivePollerError, match=message):
        fetch_noaa_records(get=lambda *args, **kwargs: response)


def test_fetch_wraps_network_timeout() -> None:
    def timeout(*args, **kwargs):
        raise requests.Timeout("slow NOAA")

    with pytest.raises(LivePollerError, match="request failed"):
        fetch_noaa_records(get=timeout)


def test_first_poll_publishes_only_newest_valid_record() -> None:
    seen = set()
    events = []

    result = poll_once(
        object(),
        seen,
        fetch=lambda **kwargs: [record(1), record(2), record(3)],
        publish=lambda producer, event: events.append(event) or published(event, 0),
        now=lambda: datetime(2026, 8, 12, 23, 4, tzinfo=timezone.utc),
    )

    assert result.received_records == 3
    assert result.valid_events == 3
    assert result.invalid_records == 0
    assert len(result.published) == 1
    assert events[0].time_tag.minute == 3
    assert events[0].source == NOAA_KP_SOURCE
    assert len(seen) == 3
    assert events[0].time_tag in seen


def test_second_poll_does_not_publish_the_initial_backlog() -> None:
    seen = set()
    events = []
    publish = (
        lambda producer, event: events.append(event)
        or published(event, len(events) - 1)
    )

    first = poll_once(
        object(),
        seen,
        fetch=lambda **kwargs: [record(1), record(2), record(3)],
        publish=publish,
    )
    second = poll_once(
        object(),
        seen,
        fetch=lambda **kwargs: [record(1), record(2), record(3), record(4)],
        publish=publish,
    )

    assert len(first.published) == 1
    assert len(second.published) == 1
    assert [event.time_tag.minute for event in events] == [3, 4]


def test_failed_startup_delivery_does_not_advance_seen_state() -> None:
    seen = set()

    def fail(producer, event):
        raise RuntimeError("Kafka delivery failed")

    with pytest.raises(RuntimeError, match="delivery failed"):
        poll_once(
            object(),
            seen,
            fetch=lambda **kwargs: [record(1), record(2), record(3)],
            publish=fail,
        )

    assert seen == set()


def test_later_poll_publishes_each_unseen_timestamp_once() -> None:
    seen = {datetime(2026, 8, 12, 23, 3, tzinfo=timezone.utc)}
    events = []
    fetch = lambda **kwargs: [record(3), record(4), record(5)]
    publish = (
        lambda producer, event: events.append(event)
        or published(event, len(events) - 1)
    )

    first = poll_once(object(), seen, fetch=fetch, publish=publish)
    second = poll_once(object(), seen, fetch=fetch, publish=publish)

    assert [event.time_tag.minute for event in events] == [4, 5]
    assert len(first.published) == 2
    assert len(second.published) == 0


def test_late_older_timestamp_is_not_published_after_watermark() -> None:
    seen = {datetime(2026, 8, 12, 23, 4, tzinfo=timezone.utc)}
    captured = []

    result = poll_once(
        object(),
        seen,
        fetch=lambda **kwargs: [record(2), record(4), record(5)],
        publish=lambda producer, event: captured.append(event)
        or published(event, 0),
    )

    assert [event.time_tag.minute for event in captured] == [5]
    assert len(result.published) == 1


def test_invalid_record_is_logged_and_does_not_block_valid_latest(caplog) -> None:
    bad = record(2)
    bad["estimated_kp"] = "not-numeric"

    with caplog.at_level(logging.WARNING):
        result = poll_once(
            object(),
            set(),
            fetch=lambda **kwargs: [record(1), bad, record(3)],
            publish=lambda producer, event: published(event, 0),
        )

    assert result.valid_events == 2
    assert result.invalid_records == 1
    assert len(result.published) == 1
    assert "Skipping invalid NOAA record" in caplog.text


def test_mocked_full_noaa_response_shape_and_count() -> None:
    start = datetime(2026, 8, 12, 17, 12)
    records = []
    for i in range(358):
        tag = start + timedelta(minutes=i)
        records.append(
            {
                "time_tag": tag.isoformat(timespec="minutes") + ":00",
                "kp_index": 1,
                "estimated_kp": 1.0 + (i % 4) / 3,
                "kp": "1Z",
            }
        )

    result = poll_once(
        object(),
        set(),
        fetch=lambda **kwargs: records,
        publish=lambda producer, event: published(event, 0),
    )

    assert result.received_records == 358
    assert result.valid_events == 358
    assert len(result.published) == 1


def test_committed_raw_sample_can_drive_first_poll() -> None:
    records = json.loads(
        (PROJECT_ROOT / "data/sample_or_replay_data/noaa_raw_sample.json").read_text()
    )
    captured = []

    result = poll_once(
        object(),
        set(),
        fetch=lambda **kwargs: records,
        publish=lambda producer, event: captured.append(event)
        or published(event, 0),
    )

    assert result.received_records == 12
    assert len(captured) == 1
    assert captured[0].kp_value == records[-1]["estimated_kp"]


def test_continuous_loop_waits_60_seconds_and_retries_after_failure() -> None:
    calls = 0
    sleeps = []

    def poll(producer, seen, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise LivePollerError("temporary timeout")
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_poller(
            state_path="/does/not/exist/checkpoint.json",
            ensure_topic=lambda address: None,
            make_producer=lambda address: object(),
            poll=poll,
            sleep=sleeps.append,
        )

    assert calls == 2
    assert sleeps == [60.0]


def test_once_returns_success_for_no_new_timestamp(tmp_path: Path) -> None:
    result = PollResult(358, 358, 0, (), datetime(2026, 8, 12, tzinfo=timezone.utc))

    exit_code = run_poller(
        once=True,
        state_path=tmp_path / "checkpoint.json",
        ensure_topic=lambda address: None,
        make_producer=lambda address: object(),
        poll=lambda producer, seen, **kwargs: result,
    )

    assert exit_code == 0


def test_once_returns_nonzero_for_source_failure(tmp_path: Path) -> None:
    def fail(producer, seen, **kwargs):
        raise LivePollerError("NOAA unavailable")

    exit_code = run_poller(
        once=True,
        state_path=tmp_path / "checkpoint.json",
        ensure_topic=lambda address: None,
        make_producer=lambda address: object(),
        poll=fail,
    )

    assert exit_code == 1


def test_rejects_polling_faster_than_60_seconds_before_kafka_setup() -> None:
    setup_calls = []

    with pytest.raises(ValueError, match="at least 60"):
        run_poller(
            poll_interval_seconds=59.9,
            ensure_topic=setup_calls.append,
            make_producer=lambda address: object(),
        )

    assert setup_calls == []


def test_checkpoint_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state" / "poller.json"
    expected = {
        datetime(2026, 8, 12, 23, 4, tzinfo=timezone.utc),
        datetime(2026, 8, 12, 23, 5, tzinfo=timezone.utc),
    }

    save_checkpoint(expected, path)

    assert load_checkpoint(path) == {
        datetime(2026, 8, 12, 23, 5, tzinfo=timezone.utc)
    }
    assert json.loads(path.read_text()) == {
        "newest_time_tag": "2026-08-12T23:05:00Z"
    }


def test_checkpoint_rejects_invalid_file(tmp_path: Path) -> None:
    path = tmp_path / "poller.json"
    path.write_text("{not-json}")

    with pytest.raises(LivePollerError, match="Could not read poller checkpoint"):
        load_checkpoint(path)
