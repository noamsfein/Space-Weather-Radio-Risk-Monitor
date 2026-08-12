"""Build and atomically write deterministic rule-based alert output."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.processor import (
    RISK_THRESHOLD_KP,
    WINDOW_DURATION,
    ProcessingResult,
    ProcessingStatus,
)


DEFAULT_ALERT_PATH = Path("outputs/alert.json")


def _utc_text(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _alert_id(triggered_at: datetime) -> str:
    return f"kp-alert-{triggered_at.strftime('%Y%m%dT%H%M%SZ')}"


def build_alert_output(
    results: Iterable[ProcessingResult],
    *,
    window: timedelta = WINDOW_DURATION,
    threshold_kp: float = RISK_THRESHOLD_KP,
) -> dict[str, Any]:
    """Return the complete alert artifact for one finite processing run."""

    processed = list(results)
    alerts: list[dict[str, Any]] = []

    for result in processed:
        if not result.alert_emitted:
            continue
        if result.status is not ProcessingStatus.ACCEPTED:
            raise ValueError("only an accepted event can emit an alert")
        if result.rolling_15m_max_kp is None:
            raise ValueError("an alert must have a rolling maximum")

        triggered_at = result.event.time_tag
        alerts.append(
            {
                "alert_id": _alert_id(triggered_at),
                "triggered_at": _utc_text(triggered_at),
                "latest_kp": result.event.kp_value,
                "rolling_15m_max_kp": result.rolling_15m_max_kp,
                "window_start_utc": _utc_text(triggered_at - window),
                "window_end_utc": _utc_text(triggered_at),
                "window_minutes": window.total_seconds() / 60,
                "threshold_kp": threshold_kp,
                "risk_label": result.risk_label.value,
                "source": result.event.source,
            }
        )

    run_counts = {
        "messages_consumed": len(processed),
        "unique_events": sum(result.accepted for result in processed),
        "duplicates_skipped": sum(
            result.status is ProcessingStatus.DUPLICATE_SKIPPED
            for result in processed
        ),
        "late_events_skipped": sum(
            result.status is ProcessingStatus.LATE_EVENT_SKIPPED
            for result in processed
        ),
        "alerts_emitted": len(alerts),
    }
    return {"run_counts": run_counts, "alerts": alerts}


def write_alert_output(
    results: Iterable[ProcessingResult],
    output_path: str | Path = DEFAULT_ALERT_PATH,
) -> dict[str, Any]:
    """Atomically replace ``output_path`` and return the written artifact."""

    artifact = build_alert_output(results)
    serialized = json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"
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
            temporary_file.write(serialized)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return artifact
