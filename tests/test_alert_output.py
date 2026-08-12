import json
from pathlib import Path

import pytest

import src.alert_output as alert_output
from src.alert_output import build_alert_output, write_alert_output
from src.processor import RollingKpProcessor
from src.replay_producer import load_replay


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def replay_results():
    processor = RollingKpProcessor()
    return [processor.process(event) for event in load_replay()]


def test_full_replay_builds_exactly_two_expected_alerts() -> None:
    expected = json.loads(
        (PROJECT_ROOT / "data/fixtures/replay_expected.json").read_text()
    )

    artifact = build_alert_output(replay_results())

    assert artifact["run_counts"] == expected["expected_counts"]
    assert [
        {
            "triggered_at": item["triggered_at"],
            "latest_kp": item["latest_kp"],
            "rolling_15m_max_kp": item["rolling_15m_max_kp"],
        }
        for item in artifact["alerts"]
    ] == expected["expected_alerts"]
    assert [item["alert_id"] for item in artifact["alerts"]] == [
        "kp-alert-20260811T001000Z",
        "kp-alert-20260811T002700Z",
    ]


def test_alerts_contain_required_rule_based_fields_and_no_ai_decision() -> None:
    artifact = build_alert_output(replay_results())
    expected_fields = {
        "alert_id",
        "triggered_at",
        "latest_kp",
        "rolling_15m_max_kp",
        "window_start_utc",
        "window_end_utc",
        "window_minutes",
        "threshold_kp",
        "risk_label",
        "source",
    }

    assert len(artifact["alerts"]) == 2
    assert set(artifact["alerts"][0]) == expected_fields
    assert artifact["alerts"][0] == {
        "alert_id": "kp-alert-20260811T001000Z",
        "triggered_at": "2026-08-11T00:10:00Z",
        "latest_kp": 6.3,
        "rolling_15m_max_kp": 6.3,
        "window_start_utc": "2026-08-10T23:55:00Z",
        "window_end_utc": "2026-08-11T00:10:00Z",
        "window_minutes": 15.0,
        "threshold_kp": 6.0,
        "risk_label": "elevated",
        "source": "synthetic://kp-threshold-fixture",
    }
    assert "ai" not in json.dumps(artifact).lower()


def test_writer_creates_parent_and_valid_json(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "alert.json"

    returned = write_alert_output(replay_results(), target)

    assert json.loads(target.read_text()) == returned
    assert target.read_text().endswith("\n")
    assert list(target.parent.glob(".alert.json.*.tmp")) == []


def test_atomic_replace_failure_preserves_existing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "alert.json"
    original = '{"previous":"complete"}\n'
    target.write_text(original)

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(alert_output.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        write_alert_output(replay_results(), target)

    assert target.read_text() == original
    assert list(tmp_path.glob(".alert.json.*.tmp")) == []


def test_no_crossing_writes_empty_alert_list_with_counts() -> None:
    first_two_results = replay_results()[:2]

    artifact = build_alert_output(first_two_results)

    assert artifact == {
        "run_counts": {
            "messages_consumed": 2,
            "unique_events": 2,
            "duplicates_skipped": 0,
            "late_events_skipped": 0,
            "alerts_emitted": 0,
        },
        "alerts": [],
    }
