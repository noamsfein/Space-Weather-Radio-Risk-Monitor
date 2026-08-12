import json
from pathlib import Path

import pytest

from src.briefing import (
    BriefingCheck,
    BriefingGeneration,
    BriefingValidation,
)
from src.demo_ui import (
    PAGE_HTML,
    RUN_DEMO_HINT,
    read_artifacts,
    run_live_briefing,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_minimal_artifacts(base: Path) -> dict[str, Path]:
    paths = {
        "alert": base / "alert.json",
        "metrics": base / "metrics.csv",
        "briefing": base / "briefing.txt",
        "evaluation": base / "evaluation.json",
    }
    paths["alert"].write_text(
        json.dumps(
            {
                "run_counts": {"messages_consumed": 9, "alerts_emitted": 2},
                "alerts": [{"alert_id": "kp-alert-20260811T001000Z"}],
            }
        )
    )
    paths["metrics"].write_text(
        "time_tag,kp_value\n2026-08-11T00:00:00Z,4.0\n2026-08-11T00:05:00Z,5.0\n"
    )
    paths["briefing"].write_text("Two deterministic sentences.\n")
    paths["evaluation"].write_text(
        json.dumps({"summary": {"overall_passed": True, "total_assertions": 7}})
    )
    return paths


def test_read_artifacts_assembles_every_artifact(tmp_path: Path) -> None:
    paths = write_minimal_artifacts(tmp_path)

    payload = read_artifacts(
        alert_path=paths["alert"],
        metrics_path=paths["metrics"],
        briefing_path=paths["briefing"],
        evaluation_path=paths["evaluation"],
    )

    assert payload["alert"]["run_counts"]["alerts_emitted"] == 2
    assert payload["metrics"] == [
        {"time_tag": "2026-08-11T00:00:00Z", "kp_value": "4.0"},
        {"time_tag": "2026-08-11T00:05:00Z", "kp_value": "5.0"},
    ]
    assert payload["briefing"] == "Two deterministic sentences."
    assert payload["evaluation_summary"]["overall_passed"] is True
    assert payload["hints"] == []


def test_read_artifacts_reports_missing_files_as_run_demo_hints(tmp_path: Path) -> None:
    payload = read_artifacts(
        alert_path=tmp_path / "alert.json",
        metrics_path=tmp_path / "metrics.csv",
        briefing_path=tmp_path / "briefing.txt",
        evaluation_path=tmp_path / "evaluation.json",
    )

    assert payload["alert"] is None
    assert payload["metrics"] is None
    assert payload["briefing"] is None
    assert payload["evaluation_summary"] is None
    assert len(payload["hints"]) == 4
    assert all(RUN_DEMO_HINT in hint for hint in payload["hints"])


def test_read_artifacts_defaults_point_at_committed_repository_artifacts() -> None:
    payload = read_artifacts(
        alert_path=PROJECT_ROOT / "outputs/alert.json",
        metrics_path=PROJECT_ROOT / "outputs/metrics.csv",
        briefing_path=PROJECT_ROOT / "outputs/briefing.txt",
        evaluation_path=PROJECT_ROOT / "evaluation/evaluation.json",
    )

    assert payload["alert"]["run_counts"]["alerts_emitted"] == 2
    assert len(payload["metrics"]) == 9
    assert payload["evaluation_summary"]["overall_passed"] is True


def accepted_generation() -> BriefingGeneration:
    validation = BriefingValidation(
        accepted=True,
        checks=(BriefingCheck("sentence_count", True, "exactly two sentences"),),
        rejection_reasons=(),
    )
    return BriefingGeneration(
        "A validated sentence. Another validated sentence.",
        "model",
        "gpt-5-nano",
        "A validated sentence. Another validated sentence.",
        None,
        validation,
    )


def test_run_live_briefing_serializes_generation_without_live_call() -> None:
    calls: list[dict] = []

    def fake_writer(alert_path, output_path, **kwargs):
        calls.append({"alert_path": alert_path, **kwargs})
        kwargs["generation_callback"](accepted_generation())
        return "written"

    payload = run_live_briefing(live_writer=fake_writer)

    assert calls[0]["use_live_ai"] is True
    assert payload["source"] == "model"
    assert payload["model"] == "gpt-5-nano"
    assert payload["fallback_reason"] is None
    assert payload["validation"]["accepted"] is True
    assert payload["validation"]["checks"][0]["name"] == "sentence_count"


def test_run_live_briefing_serializes_fallback_generation() -> None:
    def fake_writer(alert_path, output_path, **kwargs):
        kwargs["generation_callback"](
            BriefingGeneration(
                "Fallback text.", "fallback", "gpt-5-nano", None,
                "OPENAI_API_KEY is missing", None,
            )
        )
        return "written"

    payload = run_live_briefing(live_writer=fake_writer)

    assert payload["source"] == "fallback"
    assert payload["fallback_reason"] == "OPENAI_API_KEY is missing"
    assert payload["validation"] is None


def test_page_shell_documents_the_optional_boundary() -> None:
    assert "Generate Live AI Briefing" in PAGE_HTML
    assert "./run_demo.sh" in PAGE_HTML
    assert "Optional presentation layer" in PAGE_HTML
