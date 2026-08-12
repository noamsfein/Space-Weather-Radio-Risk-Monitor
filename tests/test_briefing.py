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
    validate_briefing,
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


def representative_facts() -> BriefingFacts:
    return BriefingFacts(
        latest_kp=7,
        rolling_15m_max_kp=7,
        window_start_utc="2026-08-11T00:12:00Z",
        window_end_utc="2026-08-11T00:27:00Z",
        risk_label="elevated",
    )


def test_validator_accepts_correct_candidate_and_exposes_all_checks() -> None:
    candidate = deterministic_briefing(representative_facts())

    validation = validate_briefing(candidate, representative_facts())

    assert validation.accepted is True
    assert validation.rejection_reasons == ()
    assert {check.name for check in validation.checks} == {
        "nonempty",
        "sentence_limit",
        "risk_label",
        "approved_numbers",
        "approved_timestamps",
        "unsupported_details",
    }
    assert all(check.passed for check in validation.checks)


@pytest.mark.parametrize(
    ("candidate", "failed_check", "reason_text"),
    [
        ("   ", "nonempty", "empty"),
        (
            "Kp is 7 and risk is elevated. Conditions remain elevated. "
            "This is a third sentence.",
            "sentence_limit",
            "3 sentence",
        ),
        (
            "The latest Kp is 8 and the risk label is elevated.",
            "approved_numbers",
            "8.0",
        ),
        (
            "The latest Kp is 7 and the risk label is normal.",
            "risk_label",
            "normal",
        ),
        (
            "The latest Kp is 7, but the risk is not elevated.",
            "risk_label",
            "unnegated",
        ),
        (
            "The elevated alert affects 15 operators.",
            "approved_numbers",
            "15.0",
        ),
        (
            "The elevated conditions were caused by a solar flare.",
            "unsupported_details",
            "cause",
        ),
        (
            "Elevated risk is expected in high latitudes.",
            "unsupported_details",
            "location",
        ),
        (
            "Elevated conditions will cause radio interference.",
            "unsupported_details",
            "impact",
        ),
        (
            "Risk is elevated, so operators should switch frequencies.",
            "unsupported_details",
            "recommendation",
        ),
        (
            "Risk was elevated at 2026-08-11T00:28:00Z.",
            "approved_timestamps",
            "00:28:00Z",
        ),
    ],
)
def test_validator_rejects_fixed_bad_candidates_with_explicit_reason(
    candidate: str, failed_check: str, reason_text: str
) -> None:
    validation = validate_briefing(candidate, representative_facts())

    failed = {check.name: check for check in validation.checks if not check.passed}
    assert validation.accepted is False
    assert failed_check in failed
    assert reason_text in failed[failed_check].detail
    assert failed[failed_check].detail in validation.rejection_reasons


def test_validator_accepts_equivalent_kp_format_and_one_sentence() -> None:
    candidate = (
        "The elevated risk label reflects a latest Kp of 7.0 and a rolling "
        "15-minute maximum of 7."
    )

    validation = validate_briefing(candidate, representative_facts())

    assert validation.accepted is True


def test_validator_does_not_repair_rejected_candidate() -> None:
    candidate = "The latest Kp is 9 and the label is normal."

    validation = validate_briefing(candidate, representative_facts())

    assert validation.accepted is False
    assert candidate == "The latest Kp is 9 and the label is normal."
