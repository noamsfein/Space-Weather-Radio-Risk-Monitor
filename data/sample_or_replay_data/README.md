# Sample and Replay Data

This directory contains one small real NOAA sample and one synthetic replay fixture.

## `noaa_raw_sample.json`

- Owner: NOAA/NWS Space Weather Prediction Center (SWPC)
- Source: `https://services.swpc.noaa.gov/json/planetary_k_index_1m.json`
- Retrieved: 2026-08-11 at 21:37:37 UTC
- Format: JSON array
- Contents: 12 unmodified records selected at intervals from the live response
- Purpose: confirm the raw source fields and provide a small, reviewable source sample

The complete response contained 358 unique records from `2026-08-11T15:35:00` through `2026-08-11T21:32:00`. The saved file is a subset, not a continuous series and not the replay input.

## `kp_replay.jsonl`

- Origin: project-created synthetic fixture
- Format: one canonical event per line
- Purpose: deterministically exercise Kafka, the inclusive 15-minute rolling maximum, duplicate handling, alert suppression, rearming, and a second threshold crossing

The values in `kp_replay.jsonl` were **not observed by NOAA at the listed times**. Its `source` value is `synthetic://kp-threshold-fixture` so the fixture cannot be confused with observed NOAA data. Live and replay records still use the same four-field event contract.

Expected results are stored in `../fixtures/replay_expected.json`. Invalid input cases are stored separately in `../fixtures/invalid_records.jsonl`; they must not be sent through the successful replay path.

## Refreshing the real sample

Before final submission, rerun checklist task `DATA-0`. Fetch the live endpoint into a temporary file, confirm it is viable, and then deliberately replace this small sample and `source_profile.json` if a newer snapshot is desired. Do not overwrite the synthetic replay fixture with quiet live data because the reviewer path must always exercise the alert.

Example temporary download:

```bash
curl -fsSL --retry 2 --connect-timeout 10 --max-time 30 \
  'https://services.swpc.noaa.gov/json/planetary_k_index_1m.json' \
  -o /tmp/planetary_k_index_1m.json
```
