# Data Source

This file documents the source used by the Space Weather Radio-Risk Monitor. It is written before implementation so the team has one agreed contract; update observed details and evidence as the data is collected.

## Source inventory

| Item | Value |
|---|---|
| Dataset | Planetary K-index one-minute estimated values |
| Owner | NOAA/NWS Space Weather Prediction Center (SWPC) |
| Endpoint | `https://services.swpc.noaa.gov/json/planetary_k_index_1m.json` |
| Access | Public HTTPS JSON; no API key or account required |
| Cost | None observed |
| Planned cadence | Poll every 60 seconds; publish only unseen `time_tag` values |
| Project classification | Realtime input with deterministic cached replay |
| Authentication | None |
| Rights | NWS public-domain terms unless specifically noted; attribution and no implied endorsement |
| Personal data | None |

## Observed raw schema

A source check on August 11, 2026 returned records with these fields:

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

The source timestamp currently omits a trailing `Z`; the application will parse it as UTC and serialize the canonical timestamp with `Z`.

## Canonical event contract

The poller and replay producer emit the same structure:

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

The project will credit “NOAA/NWS Space Weather Prediction Center” and preserve the endpoint and retrieval date with every cached sample. Project-created threshold fixtures will be labeled synthetic. The project will not describe the feed as independent one-minute measurements, an official NOAA alert, or a forecast.

The current committed source evidence is under `data/sample_or_replay_data/`. `noaa_raw_sample.json` contains unmodified observed records, `source_profile.json` records the dated viability check, and `kp_replay.jsonl` uses a synthetic provenance identifier so its threshold values cannot be confused with observed NOAA history.

## Rate limits and source behavior

No explicit endpoint-specific rate limit has been identified in the supplied project materials. The project therefore uses a conservative 60-second poll interval, a short request timeout, and no parallel calls. The poller publishes only records whose `time_tag` has not already been seen.

The project must handle:

- HTTP timeouts and non-200 responses;
- invalid JSON or an unexpected top-level shape;
- missing required fields;
- `estimated_kp` outside 0–9;
- duplicate timestamps;
- empty or quiet feeds; and
- later source revisions.

The live poller should log failures and retry on the next scheduled interval. It should not fabricate a Kp value or reuse an old value as though it were new.

## Limitations

- NOAA describes these values as preliminary estimates rather than independent one-minute measurements.
- Values may be missing or revised.
- Planetary Kp is global; it does not predict the exact impact for a station or location.
- The project's Kp 6 rule indicates a possible higher-latitude HF propagation risk, not a guaranteed outage.
- The 15-minute window is a course-sized streaming rule, not an official NOAA alerting algorithm.
- Live conditions may remain below the threshold throughout a demonstration.

## Cache and deterministic replay

The required reviewer path uses a small attributed JSONL file under `data/sample_or_replay_data/`. It must contain:

- valid observations below Kp 6;
- a first transition that makes the rolling maximum reach or exceed Kp 6;
- additional elevated observations that must not duplicate the alert;
- enough later observations for the 15-minute window to return below Kp 6;
- a second threshold crossing;
- one duplicate `time_tag`; and
- separate invalid records in a labeled negative-test fixture.

Replay requirements:

- preserve the canonical schema used by live ingestion;
- process valid records in ascending `time_tag` order;
- use a configurable short replay delay rather than sleeping for real minutes;
- record the original source URL and the cache creation date;
- contain no credentials or private information; and
- be committed with the final submission so the demo does not depend on NOAA availability.

## Data-source completion checklist

- [x] Save a small raw NOAA sample with retrieval date and source URL.
- [x] Add labeled threshold and invalid fixtures without misrepresenting synthetic records as raw NOAA observations.
- [ ] Confirm field names and types again before the final report.
- [x] Record the official NWS public-domain, attribution, and disclaimer terms.
- [ ] Document actual timeout, retry, and polling settings.
- [ ] Demonstrate duplicate suppression and invalid-record handling.
- [ ] Confirm the required replay works with the network disconnected.
