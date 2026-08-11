# Space Weather Radio-Risk Monitor

Kafka-based final project for MSDS 682, Data Stream Processing (Summer 2026).

**Team:** Noam Fein (`nsfein`) and Niki Naderzad (`nnaderzad`)

**Approved proposal:** [`output/pdf/final_project_proposal_nsfein_nnaderzad.pdf`](output/pdf/final_project_proposal_nsfein_nnaderzad.pdf)

**Current status:** Planning and initial setup. The commands and artifacts described below are the agreed implementation target. Check [the team checklist](docs/project-checklist.md) for current progress; do not assume the demo works until its end-to-end acceptance task is checked off.

**Repository:** `https://github.com/noamsfein/Space-Weather-Radio-Risk-Monitor`. This directory now has its own Git root and `main` tracks the project repository rather than the unrelated home-directory repository.

## What we are building

Amateur-radio operators need a simple warning when geomagnetic activity may affect high-frequency (HF) radio communication. This project reads NOAA Space Weather Prediction Center estimated planetary Kp updates, validates them, streams them through Kafka, and calculates a rolling 15-minute maximum.

The consumer emits an alert only when the rolling maximum crosses from below Kp 6 to Kp 6 or higher. Kp 6 corresponds to a G2 geomagnetic storm; NOAA notes that HF propagation can fade at higher latitudes at this level.

The minimum result is deliberately small:

- one NOAA data source;
- one Kafka topic, `kp_observations`;
- one canonical event contract;
- one rolling 15-minute calculation;
- one deterministic alert rule;
- JSON, CSV, text, and evaluation artifacts; and
- one bounded AI-generated briefing that never controls the alert.

## Target user and useful result

The target user is an amateur-radio operator who wants a short, machine-readable indication of elevated geomagnetic conditions.

The required local demo will create:

- `outputs/alert.json` — the threshold-crossing alert and supporting facts;
- `outputs/metrics.csv` — each processed observation, rolling maximum, rule-based label, and whether an alert was emitted;
- `outputs/briefing.txt` — a two-sentence briefing or deterministic fallback; and
- `evaluation/evaluation.json` — alert and AI-validation evidence.

## Scope

### In scope

- Polling NOAA's public near-real-time JSON feed every 60 seconds.
- Deterministic replay from a cached, attributed NOAA JSONL sample.
- Validation and normalization into one Kafka event contract.
- Publication to `kp_observations` with the constant key `planetary_kp`.
- Deduplication by `time_tag`.
- A rolling 15-minute event-time maximum.
- One alert on each below-threshold to at-or-above-threshold crossing.
- Automated alert tests and saved evaluation evidence.
- A fact-constrained, two-sentence AI briefing with a no-key fallback.

### Out of scope

- Forecasting future Kp values.
- A dashboard, mobile app, notifications, or user accounts.
- Multiple space-weather feeds or Kafka topics.
- Geographic or station-specific propagation predictions.
- Allowing AI to choose the risk level, trigger an alert, or add unsupported advice.
- Production deployment, long-term storage, or exactly-once guarantees.

## Data source

The source is the NOAA/NWS Space Weather Prediction Center public JSON service:

`https://services.swpc.noaa.gov/json/planetary_k_index_1m.json`

A current source record contains `time_tag`, `kp_index`, `estimated_kp`, and `kp`. The application uses `time_tag` and `estimated_kp`, then adds provenance and ingestion time during normalization. NOAA describes the values as estimated/preliminary; they are not independent one-minute observations and may be revised or unavailable.

Access details, field definitions, limitations, caching, and replay rules are in [DATA_SOURCE.md](DATA_SOURCE.md).

## Event contract

Live and replay inputs must produce the same canonical JSON event:

```json
{
  "time_tag": "2026-08-11T15:24:00Z",
  "kp_value": 1.0,
  "source": "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",
  "ingested_at": "2026-08-11T15:25:03Z"
}
```

Validation rules:

- `time_tag` and `ingested_at` must be valid UTC timestamps;
- `kp_value` must be numeric and between 0 and 9 inclusive;
- `source` must be either the documented NOAA endpoint for observed data or the documented `synthetic://kp-threshold-fixture` identifier for labeled replay data;
- duplicate `time_tag` values must not be processed twice; and
- records used by the replay must be ordered by `time_tag`.

Kafka topic: `kp_observations`
Kafka message key: `planetary_kp`

The constant key keeps the single planetary sequence ordered if the topic later has more than one partition.

The repository includes a real NOAA subset at `data/sample_or_replay_data/noaa_raw_sample.json`, its dated viability profile at `data/sample_or_replay_data/source_profile.json`, and a clearly labeled synthetic threshold replay at `data/sample_or_replay_data/kp_replay.jsonl`. The synthetic fixture is necessary because quiet live snapshots may contain no Kp 6 crossing.

## Alert behavior

For each valid observation, the consumer calculates the maximum `kp_value` in the inclusive 15-minute event-time window ending at the current `time_tag`.

An alert is emitted when:

```text
previous rolling maximum < 6 and current rolling maximum >= 6
```

No duplicate alert is emitted while a Kp 6-or-higher observation remains inside the rolling window. After the rolling maximum drops below 6, a later crossing may emit a new alert. The rule is deterministic and is not controlled by AI.

## Architecture

```text
NOAA live JSON                 Cached NOAA JSONL + labeled fixtures
      |                                      |
      +---------------+----------------------+
                      |
            poller or replay producer
                      |
        validate + normalize event contract
                      |
                      v
        Kafka: kp_observations
        key: planetary_kp
                      |
                      v
     consumer: deduplicate by time_tag
     + rolling 15-minute maximum
     + first Kp >= 6 crossing rule
                      |
             +--------+---------+
             |                  |
             v                  v
       alert.json          metrics.csv
             |
             v
     bounded AI briefing -> automatic fact checks
             |
             +----> briefing.txt + evaluation.json
                         |
                         v
               deterministic fallback
```

The cached replay is the required review path. The live poller is useful but may be removed from the final scope if it threatens the reproducible demo.

## Planned technology

| Tool | Responsibility |
|---|---|
| Python 3.11 | Application and tests |
| `requests` | NOAA HTTP polling |
| Pydantic | Canonical event validation |
| `confluent-kafka` | Kafka producer and consumer |
| Docker Compose | Local Kafka broker |
| `pytest` | Unit and integration acceptance tests |
| OpenAI API | Optional two-sentence briefing only |

Dependencies will be pinned in `requirements.txt`. Secrets belong in a local `.env`, which must never be submitted. `.env.example` will contain blank variable names only.

## Planned repository layout

```text
.
├── README.md
├── DATA_SOURCE.md
├── AI_USAGE.md
├── requirements.txt
├── .env.example
├── docker-compose.yml
├── run_demo.sh
├── src/
│   ├── settings.py
│   ├── contract.py
│   ├── kafka_io.py
│   ├── replay_producer.py
│   ├── live_poller.py
│   ├── processor.py
│   ├── outputs.py
│   ├── stream_processor.py
│   ├── briefing.py
│   └── evaluate.py
├── data/
│   ├── sample_or_replay_data/
│   └── fixtures/
├── outputs/
│   └── representative_result
├── evaluation/
│   └── validation_or_eval_artifact
├── tests/
├── docs/
│   └── project-checklist.md
└── report.pdf
```

The detailed task sequence, prerequisites, and acceptance checks are in [docs/project-checklist.md](docs/project-checklist.md). Equivalent internal helper names are acceptable if the README is updated to map them clearly. Changes to a public field, artifact, command, topic, key, threshold, or window must be reflected in the documentation and tests.

## Local review path

The final reviewer path will be:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
./run_demo.sh
```

`./run_demo.sh` is the one required demo command after setup. It must use cached data, start or verify Kafka, run the replay through the real Kafka producer and consumer, write fresh artifacts, run validation, and exit with a nonzero status if an acceptance check fails.

These are target commands until task `E2E-1` in the checklist is complete. The final README must show the commands actually tested on a clean machine.

Expected success criteria:

- at least one labeled Kp 6-or-higher crossing produces exactly one matching alert;
- repeated and still-elevated observations do not create duplicate alerts;
- `metrics.csv` contains the expected rolling maximum for every valid fixture;
- invalid and duplicate records are counted or rejected as documented;
- briefing facts match the deterministic alert facts, or the fallback is used;
- all automated tests pass; and
- no network connection or API key is required for the required replay review path.

Planned cleanup command:

```bash
docker compose down -v
```

## AI boundary

The language model receives only calculated facts: the latest Kp value, rolling 15-minute maximum, UTC window, and rule-based risk label. It may turn those facts into a two-sentence briefing.

It may not:

- set the risk label;
- trigger or suppress an alert;
- change calculated numbers or times; or
- invent causes, locations, impacts, or recommendations.

Automatic checks reject unsupported output. Saved accepted and rejected examples allow the reviewer to inspect the AI element without an API key. If the API is unavailable or a response fails checks, a deterministic template produces `briefing.txt`. See [AI_USAGE.md](AI_USAGE.md).

## Team ownership

| Area | Lead | Cross-review |
|---|---|---|
| NOAA ingestion, event validation, replay producer, live poller | Noam | Niki |
| Consumer, window calculation, outputs, AI evaluation | Niki | Noam |
| Kafka integration, tests, documentation, report, presentation | Shared approximately 50-50 | Both |

A lead is not the only person responsible. Both students will run the full demo, review the other person's work, and be able to explain the complete event path, AI boundary, and evaluation.

## Development workflow

Use one branch per checklist task:

```text
<owner>/<task>-<short-description>
```

Examples for this project include `noam/ingest-noaa-data`, `noam/add-replay-producer`, and `niki/process-kp-window`.

After the project has a dedicated Git root, the normal workflow is:

```bash
git switch main
git pull --ff-only
git switch -c noam/task-description

# Work, test, and commit
git push -u origin noam/task-description

# Open a PR targeting main
gh pr create --base main
```

Replace the example branch with the actual owner and task. The other partner reviews the PR, and a checklist task is not complete until the PR is merged into `main` and manually verified. Full collaboration rules are in [docs/project-checklist.md](docs/project-checklist.md).

## Course deliverables

- Presentation: Thursday, August 13, 2026, 5:40–5:48 PM PDT. Seven minutes plus one minute of Q&A; both team members must speak.
- Written report and code ZIP: Friday, August 14, 2026, 11:59 PM PDT.
- Planned ZIP name: `final_project_nsfein_nnaderzad.zip`.
- Planned top-level folder: `final_project_nsfein_nnaderzad/`.

The detailed implementation, presentation, report, clean-room review, and packaging steps are tracked in [docs/project-checklist.md](docs/project-checklist.md).

## Limitations

This product reports a recent estimated planetary Kp condition; it does not forecast future conditions or guarantee a particular radio impact at a location. A short rolling window is chosen for a clear streaming demonstration, not as a complete propagation model. NOAA data can be delayed, revised, missing, or quiet during the demo, which is why cached replay is the required path.
