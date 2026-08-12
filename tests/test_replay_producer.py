import json
from pathlib import Path

import pytest

from src.contract import KpEvent
from src.kafka_io import KP_MESSAGE_KEY, KP_TOPIC, PublishedEvent
from src.replay_producer import (
    DEFAULT_REPLAY_PATH,
    ReplayFileError,
    ReplayOrderError,
    ReplayValidationError,
    load_replay,
    main,
    replay_events,
)


ReplayInputError = (ReplayFileError, ReplayValidationError)


def write_jsonl(path: Path, records: list[object]) -> Path:
    path.write_text("\n".join(json.dumps(record) for record in records))
    return path


def canonical_record(time_tag: str, kp_value: float = 4.0) -> dict:
    return {
        "time_tag": time_tag,
        "kp_value": kp_value,
        "source": "synthetic://kp-threshold-fixture",
        "ingested_at": time_tag,
    }


def published_for(event: KpEvent, offset: int) -> PublishedEvent:
    return PublishedEvent(
        topic=KP_TOPIC,
        partition=0,
        offset=offset,
        key=KP_MESSAGE_KEY,
        value=event.model_dump_json(),
    )


def test_loads_all_fixture_events_in_nondecreasing_order() -> None:
    events = load_replay()

    assert DEFAULT_REPLAY_PATH.exists()
    assert len(events) == 9
    assert [event.time_tag for event in events] == sorted(
        event.time_tag for event in events
    )
    assert events[2].time_tag == events[3].time_tag
    assert events[2] == events[3]


@pytest.mark.parametrize(
    ("content", "expected_error"),
    [
        ("", "contains no events"),
        ("\n", "blank line"),
        ("{not-json}", "invalid JSON at line 1"),
        ("[]", "line 1 must be a JSON object"),
        (
            json.dumps({"time_tag": "2026-08-11T00:00:00Z"}),
            "line 1 is not a valid KpEvent",
        ),
    ],
)
def test_load_replay_rejects_bad_files(
    tmp_path: Path, content: str, expected_error: str
) -> None:
    replay_path = tmp_path / "bad.jsonl"
    replay_path.write_text(content)

    with pytest.raises(ReplayInputError, match=expected_error):
        load_replay(replay_path)


def test_load_replay_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ReplayFileError, match="Could not read replay file"):
        load_replay(tmp_path / "missing.jsonl")


def test_load_replay_rejects_decreasing_event_time(tmp_path: Path) -> None:
    path = write_jsonl(
        tmp_path / "out-of-order.jsonl",
        [
            canonical_record("2026-08-11T00:05:00Z"),
            canonical_record("2026-08-11T00:04:00Z"),
        ],
    )

    with pytest.raises(ReplayOrderError, match="decreased at line 2"):
        load_replay(path)


def test_replay_publishes_every_event_in_order_and_preserves_duplicate() -> None:
    events = load_replay()
    calls: list[KpEvent] = []

    def fake_publish(producer: object, event: KpEvent) -> PublishedEvent:
        assert producer == "fake-producer"
        calls.append(event)
        return published_for(event, len(calls) - 1)

    published = replay_events("fake-producer", events, publish=fake_publish)

    assert calls == events
    assert len(published) == 9
    assert [item.offset for item in published] == list(range(9))
    assert json.loads(published[2].value) == json.loads(published[3].value)


def test_replay_sleeps_only_between_events() -> None:
    events = load_replay()[:3]
    sleeps: list[float] = []

    replay_events(
        object(),
        events,
        delay_seconds=0.25,
        publish=lambda producer, event: published_for(event, 0),
        sleep=sleeps.append,
    )

    assert sleeps == [0.25, 0.25]


def test_replay_stops_and_propagates_delivery_failure() -> None:
    events = load_replay()[:3]
    calls = 0

    def failing_publish(producer: object, event: KpEvent) -> PublishedEvent:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("delivery failed")
        return published_for(event, calls - 1)

    with pytest.raises(RuntimeError, match="delivery failed"):
        replay_events(object(), events, publish=failing_publish)

    assert calls == 2


def test_replay_rejects_negative_delay_before_publishing() -> None:
    with pytest.raises(ValueError, match="delay_seconds must not be negative"):
        replay_events(object(), load_replay(), delay_seconds=-0.1)


def test_replay_rejects_empty_sequence() -> None:
    with pytest.raises(ReplayValidationError, match="at least one event"):
        replay_events(object(), [])


def test_replay_events_defensively_rejects_decreasing_order() -> None:
    events = [
        KpEvent.model_validate(canonical_record("2026-08-11T00:05:00Z")),
        KpEvent.model_validate(canonical_record("2026-08-11T00:04:00Z")),
    ]

    with pytest.raises(ReplayOrderError, match="position 2"):
        replay_events(
            object(),
            events,
            publish=lambda producer, event: published_for(event, 0),
        )


def test_cli_prints_success_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    events = load_replay()[:2]
    published = [published_for(event, offset) for offset, event in enumerate(events)]
    monkeypatch.setattr("src.replay_producer.run_replay", lambda *args, **kwargs: published)

    result = main(["--delay-seconds", "0.25"])

    output = capsys.readouterr().out
    assert result == 0
    assert "Published 2 event(s)" in output
    assert f"Topic={KP_TOPIC} key={KP_MESSAGE_KEY} partitions=[0]" in output


def test_cli_returns_nonzero_for_invalid_replay(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invalid = tmp_path / "invalid.jsonl"
    invalid.write_text("{not-json}")

    result = main(["--file", str(invalid)])

    assert result == 1
    assert "Replay failed:" in capsys.readouterr().out
