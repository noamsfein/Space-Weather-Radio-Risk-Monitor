"""Build deterministic alert and briefing evaluation evidence."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from src.alert_output import build_alert_output
from src.briefing import (
    DEFAULT_OPENAI_MODEL,
    MODEL_INSTRUCTIONS,
    BriefingFacts,
    BriefingGeneration,
    deterministic_briefing,
    generate_briefing,
)
from src.processor import RollingKpProcessor
from src.replay_producer import DEFAULT_REPLAY_PATH, ReplayError, load_replay


DEFAULT_EXPECTED_PATH = Path("data/fixtures/replay_expected.json")
DEFAULT_EVALUATION_PATH = Path("evaluation/evaluation.json")
Decision = Literal["accepted", "rejected", "unavailable"]


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    description: str
    candidate: str | None
    expected_decision: Decision
    expected_fallback_used: bool
    request_error: Exception | None = None


class SavedResponses:
    """Deterministic Responses API stand-in backed by a saved candidate."""

    def __init__(self, candidate: str | None, error: Exception | None = None):
        self._candidate = candidate
        self._error = error

    def create(self, **_: Any) -> SimpleNamespace:
        if self._error is not None:
            raise self._error
        return SimpleNamespace(output_text=self._candidate)


class SavedClient:
    def __init__(self, candidate: str | None, error: Exception | None = None):
        self.responses = SavedResponses(candidate, error)


def default_cases(facts: BriefingFacts) -> tuple[EvaluationCase, ...]:
    """Return the fixed representative acceptance and failure cases."""

    return (
        EvaluationCase(
            "correct",
            "Uses only supplied values, UTC window, and risk label.",
            deterministic_briefing(facts),
            "accepted",
            False,
        ),
        EvaluationCase(
            "wrong_number",
            "Invents a Kp value that is not in the approved facts.",
            "The latest Kp is 8 and the risk label is elevated.",
            "rejected",
            True,
        ),
        EvaluationCase(
            "wrong_label",
            "Changes the deterministic risk label.",
            "The latest Kp is 7 and the risk label is normal.",
            "rejected",
            True,
        ),
        EvaluationCase(
            "unsupported_detail",
            "Adds a cause that was not supplied by the deterministic pipeline.",
            "The elevated conditions were caused by a solar flare.",
            "rejected",
            True,
        ),
        EvaluationCase(
            "too_long",
            "Exceeds the two-sentence output boundary.",
            (
                "Kp is 7 and the risk is elevated. "
                "The rolling 15-minute maximum is 7. "
                "This is a third sentence."
            ),
            "rejected",
            True,
        ),
        EvaluationCase(
            "api_unavailable",
            "Simulates an unavailable model request without network access.",
            None,
            "unavailable",
            True,
            TimeoutError("simulated API timeout"),
        ),
    )


def _actual_decision(generation: BriefingGeneration) -> Decision:
    if generation.validation is None:
        return "unavailable"
    return "accepted" if generation.validation.accepted else "rejected"


def _case_result(
    case: EvaluationCase, facts: BriefingFacts
) -> dict[str, Any]:
    generation = generate_briefing(
        facts,
        use_live_ai=True,
        client=SavedClient(case.candidate, case.request_error),
        model=DEFAULT_OPENAI_MODEL,
    )
    actual_decision = _actual_decision(generation)
    actual_fallback_used = generation.source == "fallback"
    decision_matches = actual_decision == case.expected_decision
    fallback_matches = actual_fallback_used == case.expected_fallback_used
    checks = []
    rejection_reasons: list[str] = []
    if generation.validation is not None:
        checks = [
            {"name": check.name, "passed": check.passed, "detail": check.detail}
            for check in generation.validation.checks
        ]
        rejection_reasons = list(generation.validation.rejection_reasons)

    return {
        "case_id": case.case_id,
        "description": case.description,
        "ai_input": facts.model_dump(),
        "candidate_output": case.candidate,
        "expected_decision": case.expected_decision,
        "actual_decision": actual_decision,
        "decision_matches": decision_matches,
        "checks": checks,
        "rejection_reasons": rejection_reasons,
        "expected_fallback_used": case.expected_fallback_used,
        "fallback_used": actual_fallback_used,
        "fallback_matches": fallback_matches,
        "fallback_reason": generation.fallback_reason,
        "final_briefing": generation.text,
        "expected_matches_actual": decision_matches and fallback_matches,
    }


def _alert_evaluation(
    replay_path: str | Path, expected_path: str | Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    processor = RollingKpProcessor()
    results = [processor.process(event) for event in load_replay(replay_path)]
    actual_artifact = build_alert_output(results)
    expected_artifact = json.loads(Path(expected_path).read_text(encoding="utf-8"))

    actual_alerts = [
        {
            "triggered_at": item["triggered_at"],
            "latest_kp": item["latest_kp"],
            "rolling_15m_max_kp": item["rolling_15m_max_kp"],
        }
        for item in actual_artifact["alerts"]
    ]
    expected = {
        "run_counts": expected_artifact["expected_counts"],
        "alerts": expected_artifact["expected_alerts"],
    }
    actual = {
        "run_counts": actual_artifact["run_counts"],
        "alerts": actual_alerts,
    }
    comparison = {
        "expected": expected,
        "actual": actual,
        "counts_match": actual["run_counts"] == expected["run_counts"],
        "alerts_match": actual["alerts"] == expected["alerts"],
    }
    comparison["passed"] = comparison["counts_match"] and comparison["alerts_match"]
    return actual_artifact, comparison


def build_evaluation(
    *,
    replay_path: str | Path = DEFAULT_REPLAY_PATH,
    expected_path: str | Path = DEFAULT_EXPECTED_PATH,
    cases: Sequence[EvaluationCase] | None = None,
) -> dict[str, Any]:
    """Evaluate replay alerts and saved AI candidates without network access."""

    alert_artifact, alert_comparison = _alert_evaluation(replay_path, expected_path)
    if not alert_artifact["alerts"]:
        raise ValueError("evaluation replay produced no alert facts")
    latest_alert = alert_artifact["alerts"][-1]
    facts = BriefingFacts.model_validate(
        {
            "latest_kp": latest_alert["latest_kp"],
            "rolling_15m_max_kp": latest_alert["rolling_15m_max_kp"],
            "window_start_utc": latest_alert["window_start_utc"],
            "window_end_utc": latest_alert["window_end_utc"],
            "risk_label": latest_alert["risk_label"],
        }
    )

    selected_cases = tuple(cases) if cases is not None else default_cases(facts)
    case_results = [_case_result(case, facts) for case in selected_cases]
    cases_passed = sum(case["expected_matches_actual"] for case in case_results)
    case_total = len(case_results)
    total_assertions = case_total + 1
    assertions_passed = cases_passed + int(alert_comparison["passed"])

    return {
        "evaluation_version": 1,
        "deterministic": True,
        "network_used": False,
        "candidate_provenance": (
            "Fixed project-authored candidates exercise acceptance and failure "
            "boundaries; no case claims to be a fresh live model response."
        ),
        "runtime_ai": {
            "provider": "OpenAI",
            "model": DEFAULT_OPENAI_MODEL,
            "prompt": MODEL_INSTRUCTIONS,
            "input_boundary": list(BriefingFacts.model_fields),
        },
        "alert_evaluation": alert_comparison,
        "ai_cases": case_results,
        "summary": {
            "ai_cases_total": case_total,
            "ai_cases_passed": cases_passed,
            "ai_case_pass_rate": round(cases_passed / case_total, 4) if case_total else 0.0,
            "total_assertions": total_assertions,
            "assertions_passed": assertions_passed,
            "overall_pass_rate": round(assertions_passed / total_assertions, 4),
            "overall_passed": assertions_passed == total_assertions,
        },
    }


def write_evaluation(
    artifact: dict[str, Any], output_path: str | Path = DEFAULT_EVALUATION_PATH
) -> None:
    """Atomically write stable, human-readable evaluation JSON."""

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"
    temporary_path: Path | None = None
    try:
        descriptor, raw_path = tempfile.mkstemp(
            dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
        )
        temporary_path = Path(raw_path)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write deterministic alert and briefing evaluation evidence."
    )
    parser.add_argument("--replay-path", type=Path, default=DEFAULT_REPLAY_PATH)
    parser.add_argument("--expected-path", type=Path, default=DEFAULT_EXPECTED_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_EVALUATION_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        artifact = build_evaluation(
            replay_path=args.replay_path,
            expected_path=args.expected_path,
        )
        write_evaluation(artifact, args.output_path)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, ReplayError) as exc:
        print(f"Evaluation failed: {exc}")
        return 1

    summary = artifact["summary"]
    print(
        f"Evaluation: {summary['assertions_passed']}/"
        f"{summary['total_assertions']} assertions passed"
    )
    print(f"Wrote {args.output_path}")
    return 0 if summary["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
