"""Validated event contract shared by live ingestion and deterministic replay."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime, timezone
from numbers import Real
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


NOAA_KP_SOURCE = (
    "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
)
SYNTHETIC_REPLAY_SOURCE = "synthetic://kp-threshold-fixture"
DOCUMENTED_SOURCES = frozenset({NOAA_KP_SOURCE, SYNTHETIC_REPLAY_SOURCE})


def _utc_datetime(value: Any, field_name: str) -> datetime:
    """Parse a timestamp and return an aware UTC datetime.

    NOAA currently omits a timezone suffix. That source is documented as UTC, so a
    naive ISO-8601 timestamp is interpreted as UTC. Aware timestamps are converted
    to UTC so the serialized Kafka contract is consistent.
    """

    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a valid timestamp")

    parsed: datetime
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            raise ValueError(f"{field_name} must be a valid timestamp")
        if candidate.endswith(("Z", "z")):
            candidate = f"{candidate[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a valid timestamp") from exc
    else:
        raise ValueError(f"{field_name} must be a valid timestamp")

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class KpEvent(BaseModel):
    """Canonical four-field event published to ``kp_observations``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    time_tag: datetime
    kp_value: float
    source: str
    ingested_at: datetime

    @field_validator("time_tag", mode="before")
    @classmethod
    def validate_time_tag(cls, value: Any) -> datetime:
        return _utc_datetime(value, "time_tag")

    @field_validator("ingested_at", mode="before")
    @classmethod
    def validate_ingested_at(cls, value: Any) -> datetime:
        return _utc_datetime(value, "ingested_at")

    @field_validator("kp_value", mode="before")
    @classmethod
    def validate_kp_value(cls, value: Any) -> float:
        if isinstance(value, str):
            try:
                string_number = float(value)
            except ValueError:
                raise ValueError("Kp must be numeric") from None
            if not math.isfinite(string_number):
                raise ValueError("Kp must be finite")
            raise ValueError("Kp must be numeric")
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("Kp must be numeric")
        kp_value = float(value)
        if not math.isfinite(kp_value):
            raise ValueError("Kp must be finite")
        if not 0 <= kp_value <= 9:
            raise ValueError("Kp must be between 0 and 9")
        return kp_value

    @field_validator("source", mode="before")
    @classmethod
    def validate_source(cls, value: Any) -> str:
        if not isinstance(value, str) or value not in DOCUMENTED_SOURCES:
            raise ValueError(
                "source must be documented NOAA or synthetic replay provenance"
            )
        return str(value)

    @field_serializer("time_tag", "ingested_at", when_used="json")
    def serialize_utc_datetime(self, value: datetime) -> str:
        return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_noaa_record(
    record: Mapping[str, Any], *, ingested_at: datetime | str
) -> KpEvent:
    """Convert one raw NOAA record into the canonical Kafka event contract."""

    if "time_tag" not in record:
        raise ValueError("time_tag is required")
    if "estimated_kp" not in record:
        raise ValueError("estimated_kp or kp_value is required")

    return KpEvent(
        time_tag=record["time_tag"],
        kp_value=record["estimated_kp"],
        source=NOAA_KP_SOURCE,
        ingested_at=ingested_at,
    )
