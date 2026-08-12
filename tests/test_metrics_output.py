import csv
import json
from pathlib import Path

import pytest

import src.metrics_output as metrics_output
from src.metrics_output import METRICS_FIELDS, build_metrics_rows, write_metrics_output
from src.processor import RollingKpProcessor
from src.replay_producer import load_replay


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def replay_results():
    processor = RollingKpProcessor()
    return [processor.process(event) for event in load_replay()]


def expected_csv_rows() -> list[dict[str, str]]:
    expected = json.loads(
        (PROJECT_ROOT / "data/fixtures/replay_expected.json").read_text()
    )
    return [
        {
            "time_tag": row["time_tag"],
            "kp_value": str(row["kp_value"]),
            "rolling_15m_max_kp": str(row["rolling_15m_max_kp"]),
            "risk_label": row["risk_label"],
            "alert_emitted": str(row["alert_emitted"]).lower(),
            "processing_status": row["processing_status"],
        }
        for row in expected["expected_metrics"]
    ]


def test_full_replay_rows_match_expected_values_and_order() -> None:
    rows = build_metrics_rows(replay_results())

    assert len(rows) == 9
    assert [{key: str(row[key]) for key in METRICS_FIELDS} for row in rows] == (
        expected_csv_rows()
    )


def test_duplicate_has_own_row_and_cannot_emit_alert() -> None:
    rows = build_metrics_rows(replay_results())

    assert rows[2]["time_tag"] == rows[3]["time_tag"]
    assert rows[2]["processing_status"] == "accepted"
    assert rows[2]["alert_emitted"] == "true"
    assert rows[3]["processing_status"] == "duplicate_skipped"
    assert rows[3]["alert_emitted"] == "false"


def test_writer_creates_standard_csv_with_exact_header(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "metrics.csv"

    returned = write_metrics_output(replay_results(), target)

    with target.open(newline="", encoding="utf-8") as metrics_file:
        reader = csv.DictReader(metrics_file)
        parsed = list(reader)
        assert reader.fieldnames == list(METRICS_FIELDS)

    assert parsed == expected_csv_rows()
    assert len(returned) == len(parsed) == 9
    assert "Unnamed: 0" not in target.read_text()
    assert list(target.parent.glob(".metrics.csv.*.tmp")) == []


def test_empty_run_writes_header_only(tmp_path: Path) -> None:
    target = tmp_path / "metrics.csv"

    rows = write_metrics_output([], target)

    assert rows == []
    with target.open(newline="", encoding="utf-8") as metrics_file:
        assert list(csv.reader(metrics_file)) == [list(METRICS_FIELDS)]


def test_atomic_replace_failure_preserves_existing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "metrics.csv"
    original = "previous,complete\n"
    target.write_text(original)

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(metrics_output.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        write_metrics_output(replay_results(), target)

    assert target.read_text() == original
    assert list(tmp_path.glob(".metrics.csv.*.tmp")) == []
