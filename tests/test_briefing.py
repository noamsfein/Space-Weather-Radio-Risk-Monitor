import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import src.briefing as briefing_module
from src.alert_output import write_alert_output
from src.briefing import (
    BriefingError,
    BriefingFacts,
    deterministic_briefing,
    load_briefing_facts,
    main,
    write_briefing,
)
from src.processor import RollingKpProcessor
from src.replay_producer import load_replay


def replay_alert_file(tmp_path: Path) -> Path:
    processor = RollingKpProcessor()
    results = [processor.process(event) for event in load_replay()]
    alert_path = tmp_path / "alert.json"
    write_alert_output(results, alert_path)
    return alert_path


def test_structured_input_contains_only_five_approved_alert_facts(
    tmp_path: Path,
) -> None:
    alert_path = replay_alert_file(tmp_path)

    facts = load_briefing_facts(alert_path)

    assert facts is not None
    assert facts.model_dump() == {
        "latest_kp": 7.0,
        "rolling_15m_max_kp": 7.0,
        "window_start_utc": "2026-08-11T00:12:00Z",
        "window_end_utc": "2026-08-11T00:27:00Z",
        "risk_label": "elevated",
    }


def test_alert_fallback_is_exactly_two_sentences_from_approved_facts(
    tmp_path: Path,
) -> None:
    alert_path = replay_alert_file(tmp_path)
    facts = load_briefing_facts(alert_path)

    briefing = deterministic_briefing(facts)

    assert briefing == (
        "Elevated radio-risk conditions were detected with a latest Kp of 7 "
        "and a rolling 15-minute maximum of 7. The UTC window ran from "
        "2026-08-11T00:12:00Z to 2026-08-11T00:27:00Z, and the rule-based "
        "risk label was elevated."
    )
    assert briefing.count(".") == 2


def test_no_alert_fallback_has_no_invented_kp_or_timestamp(tmp_path: Path) -> None:
    alert_path = tmp_path / "alert.json"
    alert_path.write_text(json.dumps({"run_counts": {}, "alerts": []}))

    facts = load_briefing_facts(alert_path)
    briefing = deterministic_briefing(facts)

    assert facts is None
    assert briefing == (
        "No elevated radio-risk alert was emitted. "
        "The rolling Kp maximum did not cross the alert threshold."
    )
    assert not any(character.isdigit() for character in briefing)


def test_writer_creates_briefing_without_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    target = tmp_path / "nested" / "briefing.txt"

    returned = write_briefing(replay_alert_file(tmp_path), target)

    assert target.read_text() == returned + "\n"
    assert list(target.parent.glob(".briefing.txt.*.tmp")) == []


@pytest.mark.parametrize(
    "artifact",
    [
        {},
        {"alerts": "not-a-list"},
        {"alerts": [{}]},
        {
            "alerts": [
                {
                    "latest_kp": 7,
                    "rolling_15m_max_kp": 7,
                    "window_start_utc": "2026-08-11T00:12:00Z",
                    "window_end_utc": "2026-08-11T00:27:00Z",
                    "risk_label": "normal",
                }
            ]
        },
    ],
)
def test_invalid_alert_artifact_is_rejected(
    tmp_path: Path, artifact: dict[str, object]
) -> None:
    alert_path = tmp_path / "alert.json"
    alert_path.write_text(json.dumps(artifact))

    with pytest.raises(BriefingError):
        load_briefing_facts(alert_path)


def test_briefing_facts_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BriefingFacts.model_validate(
            {
                "latest_kp": 7,
                "rolling_15m_max_kp": 7,
                "window_start_utc": "2026-08-11T00:12:00Z",
                "window_end_utc": "2026-08-11T00:27:00Z",
                "risk_label": "elevated",
                "recommendation": "change frequencies",
            }
        )


def test_atomic_replace_failure_preserves_existing_briefing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "briefing.txt"
    original = "Previous complete briefing.\n"
    target.write_text(original)

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(briefing_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        write_briefing(replay_alert_file(tmp_path), target)

    assert target.read_text() == original
    assert list(tmp_path.glob(".briefing.txt.*.tmp")) == []


def test_cli_writes_briefing_and_reports_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    alert_path = replay_alert_file(tmp_path)
    target = tmp_path / "briefing.txt"

    exit_code = main(
        ["--alert-path", str(alert_path), "--output-path", str(target)]
    )

    assert exit_code == 0
    assert target.is_file()
    assert "Wrote" in capsys.readouterr().out


def test_cli_returns_nonzero_for_missing_alert_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["--alert-path", str(tmp_path / "missing.json")])

    assert exit_code == 1
    assert "Briefing failed" in capsys.readouterr().out
