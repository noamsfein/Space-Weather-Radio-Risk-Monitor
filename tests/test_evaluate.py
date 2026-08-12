import json
from pathlib import Path

import pytest

import src.evaluate as evaluate_module
from src.evaluate import EvaluationCase, build_evaluation, main, write_evaluation


def test_default_evaluation_contains_complete_passing_evidence() -> None:
    artifact = build_evaluation()

    assert artifact["deterministic"] is True
    assert artifact["network_used"] is False
    assert artifact["candidate_provenance"].startswith("Fixed project-authored")
    assert artifact["runtime_ai"]["provider"] == "OpenAI"
    assert artifact["runtime_ai"]["model"] == "gpt-5-nano"
    assert artifact["runtime_ai"]["input_boundary"] == [
        "latest_kp",
        "rolling_15m_max_kp",
        "window_start_utc",
        "window_end_utc",
        "risk_label",
    ]
    assert artifact["alert_evaluation"]["passed"] is True
    assert artifact["summary"] == {
        "ai_cases_total": 6,
        "ai_cases_passed": 6,
        "ai_case_pass_rate": 1.0,
        "total_assertions": 7,
        "assertions_passed": 7,
        "overall_pass_rate": 1.0,
        "overall_passed": True,
    }


def test_cases_cover_required_decisions_checks_reasons_and_fallback() -> None:
    artifact = build_evaluation()
    cases = {case["case_id"]: case for case in artifact["ai_cases"]}

    assert set(cases) == {
        "correct",
        "wrong_number",
        "wrong_label",
        "unsupported_detail",
        "too_long",
        "api_unavailable",
    }
    assert cases["correct"]["actual_decision"] == "accepted"
    assert cases["correct"]["fallback_used"] is False
    assert all(check["passed"] for check in cases["correct"]["checks"])

    expected_failed_check = {
        "wrong_number": "approved_numbers",
        "wrong_label": "risk_label",
        "unsupported_detail": "unsupported_details",
        "too_long": "sentence_limit",
    }
    for case_id, check_name in expected_failed_check.items():
        case = cases[case_id]
        assert case["actual_decision"] == "rejected"
        assert case["fallback_used"] is True
        assert case["rejection_reasons"]
        assert any(
            check["name"] == check_name and check["passed"] is False
            for check in case["checks"]
        )

    unavailable = cases["api_unavailable"]
    assert unavailable["candidate_output"] is None
    assert unavailable["actual_decision"] == "unavailable"
    assert unavailable["checks"] == []
    assert unavailable["fallback_used"] is True
    assert unavailable["fallback_reason"] == "model request failed: TimeoutError"


def test_evaluation_is_byte_for_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    write_evaluation(build_evaluation(), first)
    write_evaluation(build_evaluation(), second)

    assert first.read_bytes() == second.read_bytes()


def test_evaluation_does_not_load_env_or_construct_openai_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_call(*args, **kwargs):
        raise AssertionError("deterministic evaluation attempted a live AI call")

    monkeypatch.setenv("OPENAI_API_KEY", "ignored-test-value")
    monkeypatch.setattr("src.briefing.load_dotenv", unexpected_call)
    monkeypatch.setattr("src.briefing.OpenAI", unexpected_call)

    artifact = build_evaluation()

    assert artifact["network_used"] is False
    assert artifact["summary"]["overall_passed"] is True


def test_main_writes_json_and_returns_zero(tmp_path: Path) -> None:
    target = tmp_path / "evaluation.json"

    exit_code = main(["--output-path", str(target)])

    assert exit_code == 0
    assert json.loads(target.read_text())["summary"]["overall_passed"] is True


def test_main_returns_nonzero_when_expected_decision_does_not_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_build = evaluate_module.build_evaluation

    def build_with_failed_expectation(**kwargs):
        artifact = original_build(
            cases=(
                EvaluationCase(
                    "deliberate_mismatch",
                    "Proves the command fails an incorrect expectation.",
                    "The latest Kp is 8 and the risk label is elevated.",
                    "accepted",
                    False,
                ),
            ),
            **kwargs,
        )
        return artifact

    monkeypatch.setattr(evaluate_module, "build_evaluation", build_with_failed_expectation)
    target = tmp_path / "failed.json"

    exit_code = main(["--output-path", str(target)])

    assert exit_code == 1
    artifact = json.loads(target.read_text())
    assert artifact["summary"]["overall_passed"] is False
    assert artifact["ai_cases"][0]["expected_matches_actual"] is False


def test_atomic_replace_failure_preserves_previous_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "evaluation.json"
    target.write_text('{"previous":"complete"}\n')

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(evaluate_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        write_evaluation(build_evaluation(), target)

    assert target.read_text() == '{"previous":"complete"}\n'
    assert list(tmp_path.glob(".evaluation.json.*.tmp")) == []
