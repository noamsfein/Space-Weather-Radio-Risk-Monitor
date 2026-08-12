import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.contract import (
    NOAA_KP_SOURCE,
    SYNTHETIC_REPLAY_SOURCE,
    KpEvent,
    normalize_noaa_record,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def jsonl_records(relative_path: str) -> list[dict]:
    path = PROJECT_ROOT / relative_path
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def canonical_record(**overrides: object) -> dict:
    record = {
        "time_tag": "2026-08-11T00:10:00Z",
        "kp_value": 6.3,
        "source": SYNTHETIC_REPLAY_SOURCE,
        "ingested_at": "2026-08-11T00:10:05Z",
    }
    record.update(overrides)
    return record


def validation_message(record: dict) -> str:
    try:
        if "estimated_kp" in record or "source" not in record:
            normalize_noaa_record(
                record, ingested_at="2026-08-11T00:00:05Z"
            )
        else:
            KpEvent.model_validate(record)
    except (ValidationError, ValueError) as exc:
        return str(exc)
    pytest.fail(f"Record unexpectedly passed validation: {record}")


def test_normalizes_representative_noaa_record() -> None:
    raw_records = json.loads(
        (PROJECT_ROOT / "data/sample_or_replay_data/noaa_raw_sample.json").read_text()
    )

    event = normalize_noaa_record(
        raw_records[0], ingested_at="2026-08-11T15:36:05Z"
    )

    assert event.model_dump(mode="json") == {
        "time_tag": "2026-08-11T15:35:00Z",
        "kp_value": 1.33,
        "source": NOAA_KP_SOURCE,
        "ingested_at": "2026-08-11T15:36:05Z",
    }


def test_accepts_every_committed_noaa_sample_record() -> None:
    records = json.loads(
        (PROJECT_ROOT / "data/sample_or_replay_data/noaa_raw_sample.json").read_text()
    )
    events = [
        normalize_noaa_record(record, ingested_at="2026-08-11T21:37:37Z")
        for record in records
    ]

    assert len(events) == 12
    assert all(event.source == NOAA_KP_SOURCE for event in events)


def test_accepts_every_replay_record() -> None:
    records = jsonl_records("data/sample_or_replay_data/kp_replay.jsonl")
    events = [KpEvent.model_validate(record) for record in records]

    assert len(events) == 9
    assert all(event.source == SYNTHETIC_REPLAY_SOURCE for event in events)


def test_serializes_exact_four_field_contract_with_z_suffix() -> None:
    event = KpEvent.model_validate(
        canonical_record(
            time_tag="2026-08-10T17:10:00-07:00",
            ingested_at=datetime(2026, 8, 11, 0, 10, 5, tzinfo=timezone.utc),
        )
    )

    serialized = json.loads(event.model_dump_json())

    assert list(serialized) == ["time_tag", "kp_value", "source", "ingested_at"]
    assert serialized["time_tag"] == "2026-08-11T00:10:00Z"
    assert serialized["ingested_at"] == "2026-08-11T00:10:05Z"


@pytest.mark.parametrize(
    ("record", "expected_error"),
    [
        (canonical_record(time_tag="not-a-time"), "time_tag must be a valid timestamp"),
        (canonical_record(ingested_at=""), "ingested_at must be a valid timestamp"),
        (canonical_record(kp_value="6.3"), "Kp must be numeric"),
        (canonical_record(kp_value=True), "Kp must be numeric"),
        (canonical_record(kp_value=-0.01), "Kp must be between 0 and 9"),
        (canonical_record(kp_value=9.01), "Kp must be between 0 and 9"),
        (canonical_record(kp_value=math.nan), "Kp must be finite"),
        (canonical_record(kp_value=math.inf), "Kp must be finite"),
        (
            canonical_record(source="https://example.com/not-noaa"),
            "source must be documented NOAA or synthetic replay provenance",
        ),
    ],
)
def test_rejects_invalid_canonical_values(record: dict, expected_error: str) -> None:
    with pytest.raises(ValidationError, match=expected_error):
        KpEvent.model_validate(record)


@pytest.mark.parametrize("missing_field", ["time_tag", "kp_value", "source", "ingested_at"])
def test_rejects_missing_canonical_fields(missing_field: str) -> None:
    record = canonical_record()
    record.pop(missing_field)

    with pytest.raises(ValidationError) as error:
        KpEvent.model_validate(record)

    assert missing_field in str(error.value)
    assert "Field required" in str(error.value)


def test_rejects_extra_canonical_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        KpEvent.model_validate(canonical_record(kp_index=6))


@pytest.mark.parametrize("kp_value", [0, 0.0, 9, 9.0])
def test_accepts_inclusive_kp_boundaries(kp_value: int | float) -> None:
    assert KpEvent.model_validate(canonical_record(kp_value=kp_value)).kp_value == kp_value


def test_model_is_immutable() -> None:
    event = KpEvent.model_validate(canonical_record())

    with pytest.raises(ValidationError, match="Instance is frozen"):
        event.kp_value = 7.0  # type: ignore[misc]


def test_every_committed_invalid_fixture_fails_as_expected() -> None:
    cases = jsonl_records("data/fixtures/invalid_records.jsonl")

    for case in cases:
        assert case["expected_error"] in validation_message(case["record"]), case[
            "case_id"
        ]
