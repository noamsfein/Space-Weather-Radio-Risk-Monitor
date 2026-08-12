import json
from datetime import timedelta
from pathlib import Path

import pytest

from src.contract import KpEvent, SYNTHETIC_REPLAY_SOURCE
from src.processor import (
    RISK_THRESHOLD_KP,
    WINDOW_DURATION,
    ProcessingStatus,
    RiskLabel,
    RollingKpProcessor,
)
from src.replay_producer import load_replay


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def event(time_tag: str, kp_value: float) -> KpEvent:
    return KpEvent(
        time_tag=time_tag,
        kp_value=kp_value,
        source=SYNTHETIC_REPLAY_SOURCE,
        ingested_at=time_tag,
    )


def snapshot(processor: RollingKpProcessor) -> tuple:
    return (
        processor.window_events,
        processor.latest_time_tag,
        processor.rolling_max,
        processor.messages_seen,
        processor.accepted_count,
        processor.duplicate_count,
        processor.late_count,
        processor.alert_armed,
        processor.alerts_emitted,
    )


def test_window_is_fifteen_minutes_and_must_be_positive() -> None:
    assert WINDOW_DURATION == timedelta(minutes=15)
    assert RollingKpProcessor().window == WINDOW_DURATION
    with pytest.raises(ValueError, match="window must be positive"):
        RollingKpProcessor(window=timedelta(0))


def test_initial_state_is_empty() -> None:
    processor = RollingKpProcessor()

    assert processor.window_events == ()
    assert processor.latest_time_tag is None
    assert processor.rolling_max is None
    assert processor.messages_seen == 0
    assert processor.accepted_count == 0
    assert processor.duplicate_count == 0
    assert processor.late_count == 0
    assert processor.alert_armed is True
    assert processor.alerts_emitted == 0


def test_exact_fifteen_minute_boundary_is_inclusive_then_expires() -> None:
    processor = RollingKpProcessor()
    high = event("2026-08-11T00:10:00Z", 6.3)

    processor.process(high)
    at_boundary = processor.process(event("2026-08-11T00:25:00Z", 5.2))
    boundary_window = processor.window_events
    after_boundary = processor.process(event("2026-08-11T00:25:01Z", 5.0))

    assert at_boundary.rolling_15m_max_kp == 6.3
    assert high in boundary_window
    assert after_boundary.rolling_15m_max_kp == 5.2
    assert high not in processor.window_events


def test_duplicate_is_reported_without_changing_window_state() -> None:
    processor = RollingKpProcessor()
    first = event("2026-08-11T00:10:00Z", 6.3)
    duplicate_with_different_payload = event("2026-08-11T00:10:00Z", 8.5)

    accepted = processor.process(first)
    before_duplicate = snapshot(processor)
    duplicate = processor.process(duplicate_with_different_payload)
    after_duplicate = snapshot(processor)

    assert accepted.status is ProcessingStatus.ACCEPTED
    assert duplicate.status is ProcessingStatus.DUPLICATE_SKIPPED
    assert duplicate.rolling_15m_max_kp == 6.3
    assert before_duplicate[:3] == after_duplicate[:3]
    assert duplicate.risk_label is RiskLabel.ELEVATED
    assert duplicate.alert_emitted is False
    assert after_duplicate[3:] == (2, 1, 1, 0, False, 1)


def test_late_event_is_reported_without_changing_window_state() -> None:
    processor = RollingKpProcessor()
    processor.process(event("2026-08-11T00:10:00Z", 4.0))
    processor.process(event("2026-08-11T00:20:00Z", 5.0))
    before_late = snapshot(processor)

    late = processor.process(event("2026-08-11T00:15:00Z", 9.0))
    after_late = snapshot(processor)

    assert late.status is ProcessingStatus.LATE_EVENT_SKIPPED
    assert late.rolling_15m_max_kp == 5.0
    assert before_late[:3] == after_late[:3]
    assert late.risk_label is RiskLabel.NORMAL
    assert late.alert_emitted is False
    assert after_late[3:] == (3, 2, 0, 1, True, 0)


def test_skipped_late_timestamp_is_not_reserved_as_duplicate() -> None:
    processor = RollingKpProcessor()
    processor.process(event("2026-08-11T00:20:00Z", 5.0))

    first = processor.process(event("2026-08-11T00:15:00Z", 4.0))
    second = processor.process(event("2026-08-11T00:15:00Z", 4.0))

    assert first.status is ProcessingStatus.LATE_EVENT_SKIPPED
    assert second.status is ProcessingStatus.LATE_EVENT_SKIPPED
    assert processor.duplicate_count == 0
    assert processor.late_count == 2


def test_accepted_timestamp_remains_duplicate_after_window_expiry() -> None:
    processor = RollingKpProcessor()
    original = event("2026-08-11T00:00:00Z", 8.0)
    processor.process(original)
    processor.process(event("2026-08-11T00:16:00Z", 4.0))

    assert original not in processor.window_events
    duplicate = processor.process(event("2026-08-11T00:00:00Z", 1.0))

    assert duplicate.status is ProcessingStatus.DUPLICATE_SKIPPED
    assert duplicate.rolling_15m_max_kp == 4.0
    assert processor.duplicate_count == 1
    assert processor.late_count == 0


def test_full_fixture_matches_expected_rolling_maxima_and_statuses() -> None:
    expected = json.loads(
        (PROJECT_ROOT / "data/fixtures/replay_expected.json").read_text()
    )
    processor = RollingKpProcessor()

    results = [processor.process(item) for item in load_replay()]

    assert len(results) == len(expected["expected_metrics"]) == 9
    for result, expected_row in zip(results, expected["expected_metrics"], strict=True):
        assert result.event.model_dump(mode="json")["time_tag"] == expected_row[
            "time_tag"
        ]
        assert result.event.kp_value == expected_row["kp_value"]
        assert result.rolling_15m_max_kp == expected_row["rolling_15m_max_kp"]
        assert result.risk_label.value == expected_row["risk_label"]
        assert result.alert_emitted is expected_row["alert_emitted"]
        assert result.status.value == expected_row["processing_status"]

    assert processor.messages_seen == expected["expected_counts"]["messages_consumed"]
    assert processor.accepted_count == expected["expected_counts"]["unique_events"]
    assert processor.duplicate_count == expected["expected_counts"][
        "duplicates_skipped"
    ]
    assert processor.late_count == expected["expected_counts"][
        "late_events_skipped"
    ]
    assert processor.alerts_emitted == expected["expected_counts"]["alerts_emitted"]

    triggered_at = [
        result.event.model_dump(mode="json")["time_tag"]
        for result in results
        if result.alert_emitted
    ]
    assert triggered_at == [
        item["triggered_at"] for item in expected["expected_alerts"]
    ]


def test_rolling_max_can_decrease_when_prior_maximum_expires() -> None:
    processor = RollingKpProcessor()

    assert processor.process(event("2026-08-11T00:00:00Z", 8.0)).rolling_15m_max_kp == 8.0
    assert processor.process(event("2026-08-11T00:15:00Z", 4.0)).rolling_15m_max_kp == 8.0
    assert processor.process(event("2026-08-11T00:16:00Z", 3.0)).rolling_15m_max_kp == 4.0


def test_direct_jump_above_threshold_emits_one_alert() -> None:
    processor = RollingKpProcessor()

    below = processor.process(event("2026-08-11T00:00:00Z", 5.0))
    crossing = processor.process(event("2026-08-11T00:01:00Z", 7.0))
    sustained = processor.process(event("2026-08-11T00:02:00Z", 8.0))

    assert RISK_THRESHOLD_KP == 6.0
    assert below.risk_label is RiskLabel.NORMAL
    assert below.alert_emitted is False
    assert crossing.risk_label is RiskLabel.ELEVATED
    assert crossing.alert_emitted is True
    assert sustained.risk_label is RiskLabel.ELEVATED
    assert sustained.alert_emitted is False
    assert processor.alerts_emitted == 1
    assert processor.alert_armed is False


def test_first_event_at_exact_threshold_emits_alert() -> None:
    result = RollingKpProcessor().process(event("2026-08-11T00:00:00Z", 6.0))

    assert result.risk_label is RiskLabel.ELEVATED
    assert result.alert_emitted is True


def test_window_must_fall_below_threshold_before_second_crossing() -> None:
    processor = RollingKpProcessor()

    first = processor.process(event("2026-08-11T00:00:00Z", 6.5))
    at_boundary = processor.process(event("2026-08-11T00:15:00Z", 5.0))
    rearmed = processor.process(event("2026-08-11T00:16:00Z", 5.5))
    second = processor.process(event("2026-08-11T00:17:00Z", 7.0))

    assert first.alert_emitted is True
    assert at_boundary.risk_label is RiskLabel.ELEVATED
    assert at_boundary.alert_emitted is False
    assert rearmed.risk_label is RiskLabel.NORMAL
    assert rearmed.alert_emitted is False
    assert second.risk_label is RiskLabel.ELEVATED
    assert second.alert_emitted is True
    assert processor.alerts_emitted == 2


def test_skipped_events_cannot_rearm_or_emit_alerts() -> None:
    processor = RollingKpProcessor()
    processor.process(event("2026-08-11T00:10:00Z", 7.0))
    state_before_duplicate = snapshot(processor)

    duplicate = processor.process(event("2026-08-11T00:10:00Z", 7.0))
    state_after_duplicate = snapshot(processor)
    late_low = processor.process(event("2026-08-11T00:05:00Z", 1.0))
    state_after_late = snapshot(processor)
    sustained = processor.process(event("2026-08-11T00:11:00Z", 8.0))

    assert duplicate.status is ProcessingStatus.DUPLICATE_SKIPPED
    assert duplicate.risk_label is RiskLabel.ELEVATED
    assert duplicate.alert_emitted is False
    assert late_low.status is ProcessingStatus.LATE_EVENT_SKIPPED
    assert late_low.risk_label is RiskLabel.ELEVATED
    assert late_low.alert_emitted is False
    assert state_after_duplicate[:3] == state_before_duplicate[:3]
    assert state_after_duplicate[-2:] == state_before_duplicate[-2:]
    assert state_after_late[:3] == state_before_duplicate[:3]
    assert state_after_late[-2:] == state_before_duplicate[-2:]
    assert sustained.alert_emitted is False
    assert processor.alerts_emitted == 1
    assert processor.alert_armed is False
