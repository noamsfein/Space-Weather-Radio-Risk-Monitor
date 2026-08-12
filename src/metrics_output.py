"""Build and atomically write row-level stream-processing metrics."""

from __future__ import annotations

import csv
import os
import tempfile
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from src.processor import ProcessingResult


DEFAULT_METRICS_PATH = Path("outputs/metrics.csv")
METRICS_FIELDS = (
    "time_tag",
    "kp_value",
    "rolling_15m_max_kp",
    "risk_label",
    "alert_emitted",
    "processing_status",
)


def _utc_text(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def build_metrics_rows(results: Iterable[ProcessingResult]) -> list[dict[str, Any]]:
    """Return one ordered metrics row for every consumed processing result."""

    return [
        {
            "time_tag": _utc_text(result.event.time_tag),
            "kp_value": result.event.kp_value,
            "rolling_15m_max_kp": result.rolling_15m_max_kp,
            "risk_label": result.risk_label.value,
            "alert_emitted": str(result.alert_emitted).lower(),
            "processing_status": result.status.value,
        }
        for result in results
    ]


def write_metrics_output(
    results: Iterable[ProcessingResult],
    output_path: str | Path = DEFAULT_METRICS_PATH,
) -> list[dict[str, Any]]:
    """Atomically replace ``output_path`` and return the written rows."""

    rows = build_metrics_rows(results)
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
        with os.fdopen(
            file_descriptor, "w", encoding="utf-8", newline=""
        ) as temporary_file:
            writer = csv.DictWriter(temporary_file, fieldnames=METRICS_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return rows
