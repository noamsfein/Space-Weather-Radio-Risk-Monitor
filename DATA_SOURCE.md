# Data Source

This file documents the source used by the Space Weather Radio-Risk Monitor as implemented and verified.

## Source inventory

| Item | Value |
|---|---|
| Dataset | Planetary K-index one-minute estimated values |
| Owner | NOAA/NWS Space Weather Prediction Center (SWPC) |
| Endpoint | `https://services.swpc.noaa.gov/json/planetary_k_index_1m.json` |
| Access | Public HTTPS JSON; no API key or account required |
| Cost | None observed |
| Runtime access | None. The required demo replays a committed, labeled fixture; live polling was deliberately omitted (see below) |
| Project classification | Cached deterministic replay of a validated realtime source |
| Authentication | None |
| Rights | NWS public-domain terms unless specifically noted; attribution and no implied endorsement |
| Personal data | None |

## Decision to omit the live poller

The optional 60-second live poller (checklist task `INGEST-2`) was not implemented. The project checklist keeps it off the critical path, and quiet live data cannot demonstrate the Kp 6 alert anyway (both dated source checks observed a maximum Kp under 3.5). The source's viability is instead proven by the committed raw sample and the dated `source_profile.json`, and `src/contract.py::normalize_noaa_record` converts a raw NOAA record into the same canonical event the replay uses. Tests against the committed sample verify this, so a poller could be added later without changing the contract, topic, or consumer. If one is added, it must poll no faster than every 60 seconds, use a short HTTP timeout, publish only unseen `time_tag` values, log failures rather than fabricate data, and retry on the next interval.

## Observed raw schema

Source checks on August 11 and August 12, 2026 returned records with these fields:

| Raw field | Observed type | Project use |
|---|---|---|
| `time_tag` | string timestamp | Event time and deduplication identifier |
| `kp_index` | integer | Preserved only if useful for source debugging; not used for the alert |
| `estimated_kp` | number | Normalized to canonical `kp_value` and used by the rolling rule |
| `kp` | string | Source display code; not used by the alert |

Representative raw record:

```json
{
  "time_tag": "2026-08-11T15:24:00",
  "kp_index": 1,
  "estimated_kp": 1.0,
  "kp": "1Z"
}
```

The source timestamp omits a trailing `Z`; the application parses it as UTC (the documented source convention) and serializes the canonical timestamp with `Z`. This behavior is unit-tested.

## Canonical event contract

NOAA normalization (`normalize_noaa_record`) and the replay producer emit the same structure:

```json
{
  "time_tag": "2026-08-11T15:24:00Z",
  "kp_value": 1.0,
  "source": "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",
  "ingested_at": "2026-08-11T15:25:03Z"
}
```

| Canonical field | Type | Required | Validation |
|---|---|---:|---|
| `time_tag` | UTC datetime string | Yes | Parseable, normalized to UTC |
| `kp_value` | float | Yes | `0 <= kp_value <= 9` |
| `source` | string | Yes | NOAA endpoint for observed data, or `synthetic://kp-threshold-fixture` for the labeled replay |
| `ingested_at` | UTC datetime string | Yes | Parseable, normalized to UTC |

Kafka topic: `kp_observations`
Kafka key: `planetary_kp`
Deduplication identity: `time_tag`

## Access rules, rights, and attribution

The endpoint is publicly accessible and does not require credentials. The [National Weather Service disclaimer](https://www.weather.gov/disclaimer) states that information on NWS web pages is in the public domain unless specifically noted otherwise and may be used without charge for lawful purposes. It must not be claimed as the user's own, presented as an NOAA/NWS endorsement, or modified and then presented as official government material.

The project credits “NOAA/NWS Space Weather Prediction Center” and preserves the endpoint and retrieval date with every cached sample. Project-created threshold fixtures are labeled synthetic (`synthetic://kp-threshold-fixture`), and the contract validator rejects any other provenance value. The project does not describe the feed as independent one-minute measurements, an official NOAA alert, or a forecast.

The current committed source evidence is under `data/sample_or_replay_data/`. `noaa_raw_sample.json` contains unmodified observed records, `source_profile.json` records the dated viability check, and `kp_replay.jsonl` uses a synthetic provenance identifier so its threshold values cannot be confused with observed NOAA history.

## Rate limits and failure handling

No explicit endpoint-specific rate limit has been identified in the supplied project materials. Because the live poller was omitted, the implemented system contacts NOAA only during manual, one-time source checks (a single `curl`-style fetch with a 15-second timeout, no parallel calls); the runtime demo makes no NOAA request at all.

Failure handling that is implemented and tested:

- missing required fields, malformed timestamps, nonnumeric or out-of-range `estimated_kp`, and NaN/infinity are rejected by the contract validator (`tests/test_contract.py`, plus the committed negative fixture `data/fixtures/invalid_records.jsonl`);
- duplicate `time_tag` values are skipped by the consumer without changing window state, and appear in `metrics.csv` as `duplicate_skipped`;
- out-of-order (late) events are skipped and counted without corrupting the rolling window;
- malformed Kafka messages are skipped with a visible warning instead of crashing the consumer; and
- a quiet feed with no Kp 6 crossing is expected; this is exactly why the labeled synthetic fixture is the required alert demonstration.

Timeout and retry settings that exist in the implemented code: the Kafka clients use bounded operation timeouts in `src/kafka_io.py`, the finite consumer fails if no valid event arrives within 15 seconds (`--idle-timeout-seconds`), and the optional live briefing uses a 10-second OpenAI request timeout with automatic deterministic fallback.

## Limitations

- NOAA describes these values as preliminary estimates rather than independent one-minute measurements.
- Values may be missing or revised.
- Planetary Kp is global; it does not predict the exact impact for a station or location.
- The project's Kp 6 rule indicates a possible higher-latitude HF propagation risk, not a guaranteed outage.
- The 15-minute window is a course-sized streaming rule, not an official NOAA alerting algorithm.
- Live conditions may remain below the threshold throughout a demonstration.

## Cache and deterministic replay

The required reviewer path uses `data/sample_or_replay_data/kp_replay.jsonl`, a nine-record labeled synthetic JSONL fixture. It contains:

- valid observations below Kp 6;
- a first transition that makes the rolling maximum reach or exceed Kp 6;
- additional elevated observations that must not duplicate the alert;
- enough later observations for the 15-minute window to return below Kp 6;
- a second threshold crossing;
- one duplicate `time_tag`; and
- separate invalid records in a labeled negative-test fixture.

Replay behavior, all implemented and tested:

- the replay uses the same canonical schema and validator as NOAA normalization;
- the whole file is validated, including nondecreasing `time_tag` order, before anything is published;
- `--delay-seconds` provides a configurable short delay instead of sleeping for real minutes;
- the cached samples record the source URL and retrieval date (`data/sample_or_replay_data/README.md`, `source_profile.json`);
- no fixture contains credentials or private information; and
- everything is committed, so the demo never depends on NOAA availability.

## Data-source completion checklist

- [x] Save a small raw NOAA sample with retrieval date and source URL.
- [x] Add labeled threshold and invalid fixtures without misrepresenting synthetic records as raw NOAA observations.
- [x] Confirm field names and types again before the final report. Rechecked 2026-08-12: same four raw fields, 358 unique ordered records, one-minute cadence, Kp 0.00 to 2.67, no Kp 6 crossing; `source_profile.json` updated.
- [x] Record the official NWS public-domain, attribution, and disclaimer terms.
- [x] Document actual timeout, retry, and polling settings (see “Rate limits and failure handling”; there is no runtime polling).
- [x] Demonstrate duplicate suppression and invalid-record handling. The demo's `metrics.csv` contains the `duplicate_skipped` row, and `tests/test_contract.py` exercises every committed invalid record.
- [x] Confirm the required replay works without NOAA or an API key. `env -u OPENAI_API_KEY ./run_demo.sh` passes; the demo path opens no connection beyond `localhost` (Kafka) and reads only committed files.
