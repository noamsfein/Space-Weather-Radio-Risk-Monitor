"""Create a deterministic two-sentence briefing from rule-based alert facts."""

from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    field_validator,
    model_validator,
)

from src.alert_output import DEFAULT_ALERT_PATH


DEFAULT_BRIEFING_PATH = Path("outputs/briefing.txt")


class BriefingError(RuntimeError):
    """Raised when an alert artifact cannot produce a trustworthy briefing."""


class BriefingFacts(BaseModel):
    """The complete and intentionally narrow input allowed for briefing wording."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    latest_kp: float
    rolling_15m_max_kp: float
    window_start_utc: str
    window_end_utc: str
    risk_label: Literal["elevated"]

    @field_validator("latest_kp", "rolling_15m_max_kp")
    @classmethod
    def validate_kp(cls, value: float) -> float:
        if not math.isfinite(value) or not 0 <= value <= 9:
            raise ValueError("Kp must be between 0 and 9")
        return value

    @field_validator("window_start_utc", "window_end_utc")
    @classmethod
    def validate_utc_text(cls, value: str) -> str:
        if not value.endswith("Z"):
            raise ValueError("briefing window timestamps must be UTC")
        try:
            datetime.fromisoformat(f"{value[:-1]}+00:00")
        except ValueError as exc:
            raise ValueError("briefing window timestamps must be valid") from exc
        return value

    @model_validator(mode="after")
    def validate_window_order(self) -> BriefingFacts:
        window_start = datetime.fromisoformat(
            f"{self.window_start_utc[:-1]}+00:00"
        )
        window_end = datetime.fromisoformat(f"{self.window_end_utc[:-1]}+00:00")
        if window_start > window_end:
            raise ValueError("briefing window start must not follow its end")
        return self


def load_briefing_facts(
    alert_path: str | Path = DEFAULT_ALERT_PATH,
) -> BriefingFacts | None:
    """Read the most recent alert's approved facts, or ``None`` if no alert exists."""

    path = Path(alert_path)
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BriefingError(f"Could not read valid alert output: {path}") from exc

    try:
        alerts = artifact["alerts"]
    except (KeyError, TypeError) as exc:
        raise BriefingError("alert output must contain an alerts list") from exc
    if not isinstance(alerts, list):
        raise BriefingError("alert output must contain an alerts list")
    if not alerts:
        return None

    latest = alerts[-1]
    try:
        return BriefingFacts.model_validate(
            {
                "latest_kp": latest["latest_kp"],
                "rolling_15m_max_kp": latest["rolling_15m_max_kp"],
                "window_start_utc": latest["window_start_utc"],
                "window_end_utc": latest["window_end_utc"],
                "risk_label": latest["risk_label"],
            }
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise BriefingError("latest alert has invalid briefing facts") from exc


def deterministic_briefing(facts: BriefingFacts | None) -> str:
    """Return the required no-key two-sentence briefing."""

    if facts is None:
        return (
            "No elevated radio-risk alert was emitted. "
            "The rolling Kp maximum did not cross the alert threshold."
        )

    return (
        f"Elevated radio-risk conditions were detected with a latest Kp of "
        f"{facts.latest_kp:g} and a rolling 15-minute maximum of "
        f"{facts.rolling_15m_max_kp:g}. "
        f"The UTC window ran from {facts.window_start_utc} to "
        f"{facts.window_end_utc}, and the rule-based risk label was "
        f"{facts.risk_label}."
    )


def write_briefing(
    alert_path: str | Path = DEFAULT_ALERT_PATH,
    output_path: str | Path = DEFAULT_BRIEFING_PATH,
) -> str:
    """Atomically write the deterministic briefing derived from ``alert.json``."""

    briefing = deterministic_briefing(load_briefing_facts(alert_path))
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: Path | None = None
    try:
        file_descriptor, raw_path = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(raw_path)
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(briefing + "\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return briefing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write a deterministic briefing from rule-based alert facts."
    )
    parser.add_argument("--alert-path", type=Path, default=DEFAULT_ALERT_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_BRIEFING_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        briefing = write_briefing(args.alert_path, args.output_path)
    except (BriefingError, OSError, ValueError) as exc:
        print(f"Briefing failed: {exc}")
        return 1

    print(briefing)
    print(f"Wrote {args.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
