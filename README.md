# Space Weather Radio-Risk Monitor

Kafka-based final project for MSDS 682, Data Stream Processing (Summer 2026).

**Team:** Noam Fein (`nsfein`) and Niki Naderzad (`nnaderzad`)

**Approved proposal:** [`output/pdf/final_project_proposal_nsfein_nnaderzad.pdf`](output/pdf/final_project_proposal_nsfein_nnaderzad.pdf)

**Current status:** Implemented and verified. Every command in this README has been run as written; `./run_demo.sh` passes end-to-end through the local Kafka broker, with and without an OpenAI key. Task-level progress and evidence are tracked in [the team checklist](docs/project-checklist.md). The presentation scenario and backup procedure are in [the demo plan](docs/demo-plan.md).

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

The required local demo creates:

- `outputs/alert.json`: the threshold-crossing alert and supporting facts;
- `outputs/metrics.csv`: each processed observation, rolling maximum, rule-based label, and whether an alert was emitted;
- `outputs/briefing.txt`: a two-sentence briefing or deterministic fallback; and
- `evaluation/evaluation.json`: alert and AI-validation evidence.

## Scope

### In scope (implemented)

- Deterministic replay of a labeled synthetic threshold fixture through real Kafka.
- Validation and normalization into one Kafka event contract, shared by cached NOAA records and replay records.
- Publication to `kp_observations` with the constant key `planetary_kp`.
- Deduplication by `time_tag`.
- A rolling 15-minute event-time maximum.
- One alert on each below-threshold to at-or-above-threshold crossing.
- Automated alert tests and saved evaluation evidence.
- A fact-constrained, two-sentence AI briefing with a no-key fallback.

### Deliberately omitted

The optional 60-second live NOAA poller (checklist task `INGEST-2`) was not built. The checklist keeps it off the critical path, and the team prioritized the required deterministic replay, evidence, and presentation instead. The committed NOAA sample and dated source profile prove the endpoint's shape and viability; the contract's `normalize_noaa_record` already converts a raw NOAA record into the same canonical event the replay uses, so a poller could be added later without changing the contract, topic, or consumer.

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

Live and replay inputs must produce the same canonical JSON event. The project's representative event is the first alert-producing record from the clearly labeled synthetic replay:

```json
{
  "time_tag": "2026-08-11T00:10:00Z",
  "kp_value": 6.3,
  "source": "synthetic://kp-threshold-fixture",
  "ingested_at": "2026-08-11T00:10:05Z"
}
```

The authoritative copy is [`data/fixtures/representative_event.json`](data/fixtures/representative_event.json). It is published to `kp_observations` with key `planetary_kp`; later processing should calculate a rolling maximum of 6.3 and emit the first alert. The source field makes clear that this event is a project-created demonstration fixture, not observed NOAA history.

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

With the local Kafka broker running, publish the complete nine-message fixture with:

```bash
python -m src.replay_producer
```

Use `--delay-seconds 0.25` when a slower event-by-event replay is helpful for the presentation. The command validates the entire JSONL file and its nondecreasing event-time order before publishing anything; it deliberately preserves the repeated `00:10` record so the consumer can demonstrate deduplication.

To run the current Kafka-to-output path manually, start the finite consumer in one
terminal before publishing the replay in another:

```bash
python -m src.stream_processor
python -m src.replay_producer
```

The consumer stops after nine valid events, writes `outputs/alert.json` and
`outputs/metrics.csv`, skips malformed messages with a visible warning, and fails
if the next valid event does not arrive within 15 seconds. `./run_demo.sh` wraps
these commands, so the manual two-terminal path is only needed for debugging or
a slowed-down presentation replay.

## Alert behavior

For each valid observation, the consumer calculates the maximum `kp_value` in the inclusive 15-minute event-time window ending at the current `time_tag`.

An alert is emitted when:

```text
previous rolling maximum < 6 and current rolling maximum >= 6
```

No duplicate alert is emitted while a Kp 6-or-higher observation remains inside the rolling window. After the rolling maximum drops below 6, a later crossing may emit a new alert. The rule is deterministic and is not controlled by AI.

## Architecture

This chart shows the implemented path, exercised end to end by `./run_demo.sh`. Optional components that require credentials or the network are marked and are never on the required path.

```text
REQUIRED REPLAY PATH (no network, no API key)

  data/sample_or_replay_data/kp_replay.jsonl     [labeled synthetic fixture]
                      |
                      v
  src/replay_producer.py: validate every record (src/contract.py),
  reject disorder, publish in event-time order
                      |
                      v
        Kafka topic: kp_observations  (1 partition, local Docker broker)
        message key: planetary_kp
                      |
                      v
  src/stream_processor.py: finite consumer
        src/processor.py: deduplicate by time_tag
        + rolling 15-minute event-time maximum (inclusive)
        + alert on below-6 to at-or-above-6 crossing, rearm below 6
                      |
             +--------+---------+
             v                  v
   outputs/alert.json    outputs/metrics.csv
             |
             v
  src/briefing.py: deterministic two-sentence template
  from the five approved alert facts
             |
             v
   outputs/briefing.txt
             |
             v
  src/evaluate.py: expected-vs-actual alerts + six fixed
  briefing acceptance cases
             |
             v
   evaluation/evaluation.json

OPTIONAL, OFF THE REQUIRED PATH
  - live OpenAI briefing (python -m src.briefing --use-live-ai): needs a
    private key in .env; the candidate must pass the same fact checks or
    the deterministic fallback is used
  - live NOAA poller: deliberately omitted (see Scope); the committed
    NOAA sample proves the raw-to-canonical mapping instead
```

One representative event can be traced across every box: the record at `data/fixtures/representative_event.json` enters the replay, is published with key `planetary_kp`, raises the rolling maximum to 6.3, emits the first alert in `alert.json` and the matching `alert_emitted` row in `metrics.csv`, and supplies the facts in `briefing.txt` that `evaluation.json` checks.

## Technology

| Tool | Responsibility |
|---|---|
| Python 3.11 | Application and tests |
| Pydantic | Canonical event validation |
| `confluent-kafka` | Kafka producer and consumer |
| Docker Compose | Local Kafka broker |
| `pytest` | Unit and integration acceptance tests |
| OpenAI API | Optional two-sentence briefing only |
| `python-dotenv` | Loading the optional private `.env` for the live briefing |

Dependencies are pinned in `requirements.txt` (`requests` remains pinned there for the one-time source-viability check even though the runtime path does not poll NOAA). Secrets belong in a local `.env`, which must never be submitted. `.env.example` contains no credentials and preselects the shared, non-secret model name `gpt-5-nano`.

Niki's one-time shared-project and private-key setup is documented in
[`docs/niki-openai-setup.md`](docs/niki-openai-setup.md). Each partner uses a
separate local key; neither key is shared or committed. Both partners use
`OPENAI_MODEL=gpt-5-nano` for the optional live briefing.

The local broker uses the official `apache/kafka:4.1.2` image in single-node KRaft mode. Docker Compose exposes it at `localhost:9092`; Kafka does not need to be installed separately. Its state is disposable: restarting the same container preserves it, while removing and recreating the container starts a clean broker. Start and inspect it with:

```bash
docker compose up -d
docker compose ps
```

Wait for the `kafka` service to report `healthy` before running Kafka clients. The project uses one partition for `kp_observations` so the single planetary event sequence remains ordered. Remove the local broker and its project data with `docker compose down -v`.

## Repository layout

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
│   ├── contract.py          # canonical KpEvent + NOAA normalization
│   ├── kafka_io.py          # shared producer/consumer/topic helpers
│   ├── replay_producer.py   # validated JSONL replay through Kafka
│   ├── processor.py         # dedup + rolling window + crossing rule
│   ├── alert_output.py      # writes outputs/alert.json
│   ├── metrics_output.py    # writes outputs/metrics.csv
│   ├── stream_processor.py  # finite Kafka consumer wiring it together
│   ├── briefing.py          # deterministic + optional live briefing
│   ├── evaluate.py          # deterministic evaluation evidence
│   └── demo_ui.py           # optional local artifact viewer (not graded)
├── data/
│   ├── sample_or_replay_data/   # raw NOAA sample, source profile, replay
│   └── fixtures/                # expected results, invalid records,
│                                # representative event
├── outputs/                 # alert.json, metrics.csv, briefing.txt
├── evaluation/              # evaluation.json (+ optional live candidate)
├── tests/
├── docs/
│   └── project-checklist.md
└── report.pdf
```

Differences from the proposal's planned layout: `outputs.py` became the two focused writers `alert_output.py` and `metrics_output.py`; `settings.py` was unnecessary because configuration lives in explicit constants and CLI flags; and `live_poller.py` was deliberately omitted with the live poller (see Scope). The detailed task sequence, prerequisites, and acceptance checks are in [docs/project-checklist.md](docs/project-checklist.md). Changes to a public field, artifact, command, topic, key, threshold, or window must be reflected in the documentation and tests.

## Local review path

This is the required reviewer path. It needs no NOAA access, no OpenAI key, and no network beyond `localhost`. All commands below have been run as written on macOS with Docker Desktop.

Prerequisites: Git, Python 3.11, and Docker Desktop with `docker compose` v2. Docker Desktop must be running before the demo starts.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional; only needed for the live-AI extra
./run_demo.sh
```

`./run_demo.sh` is the one required demo command after setup. It:

1. verifies Docker, Compose, and the Python dependencies, with a clear message if one is missing;
2. resets the local broker (`docker compose down -v`, then `up -d --wait`) so no run can reuse stale topics or consumer offsets;
3. deletes only the four generated artifacts;
4. starts the finite consumer in the background, publishes the nine-message replay through the real Kafka producer, and waits for the consumer;
5. writes the deterministic briefing and the evaluation evidence;
6. verifies every artifact field against `data/fixtures/replay_expected.json`; and
7. runs the automated test suite.

It exits nonzero, printing the consumer log, if any step fails. A successful run ends with:

```text
Processed 9 valid event(s); skipped 0 malformed; emitted 2 alert(s)
...
Artifacts match the labeled fixture: 2 alert(s), 9 metrics row(s), briefing present, evaluation 7/7 assertions passed.
...
147 passed, 3 skipped in ...s

Demo complete. Artifacts:
  outputs/alert.json
  outputs/metrics.csv
  outputs/briefing.txt
  evaluation/evaluation.json
```

The three skipped tests are the Kafka integration tests, which are opt-in so `pytest` never depends on Docker. To run them against a clean broker:

```bash
docker compose down -v && docker compose up -d --wait kafka
RUN_KAFKA_INTEGRATION=1 pytest -q tests/test_kafka_integration.py \
  tests/test_replay_integration.py tests/test_stream_processor_integration.py
```

Verified success criteria:

- the labeled fixture's two Kp 6-or-higher crossings produce exactly two alerts, at `2026-08-11T00:10:00Z` and `2026-08-11T00:27:00Z`;
- repeated and still-elevated observations do not create duplicate alerts;
- `metrics.csv` contains the expected rolling maximum for every fixture row, including one `duplicate_skipped` row;
- briefing facts match the deterministic alert facts, or the fallback is used;
- all automated tests pass; and
- no network connection or API key is required (`env -u OPENAI_API_KEY ./run_demo.sh` passes identically, with `briefing.txt` from the deterministic fallback).

Troubleshooting:

- `DEMO FAILED: Docker is not running`: open Docker Desktop and rerun.
- `Kafka broker did not become healthy`: check `docker compose ps` and port `9092`; another local broker or an old container can hold the port (`docker compose down -v` then rerun).
- `Python dependencies missing`: activate the virtual environment and rerun `pip install -r requirements.txt`.
- A `Coordinator load in progress: retrying` line from the producer on a fresh broker is normal; the idempotent producer retries and the run continues.

Cleanup:

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

The deterministic fallback is already runnable after `outputs/alert.json` exists:

```bash
python -m src.briefing
```

It reads only the latest alert's approved facts and writes
`outputs/briefing.txt`. If the alert list is empty, it writes a two-sentence
no-alert briefing without inventing Kp values or timestamps. This command does
not read `OPENAI_API_KEY`, load `.env`, or make a network request.

The optional live briefing is an explicit separate command:

```bash
python -m src.briefing --use-live-ai \
  --candidate-path evaluation/live_candidate.txt
```

It loads the private local `.env`, sends only the five approved alert facts to
`gpt-5-nano`, applies a 10-second request timeout, and validates the returned
text before writing it. Missing credentials, request failure, empty or rejected
output, and no-alert input all use the deterministic fallback automatically.
The optional candidate file preserves the raw response for evaluation; it is
never treated as the accepted briefing unless validation passes.

Generate the required deterministic alert and AI evaluation evidence with:

```bash
python -m src.evaluate
```

This command does not load `.env`, contact OpenAI, or require Kafka. It replays
the committed canonical events in memory, compares alert counts and crossings
with `data/fixtures/replay_expected.json`, evaluates six fixed briefing cases,
and writes `evaluation/evaluation.json`. The cases are clearly identified as
project-authored test candidates, not fresh live-model responses. The command
returns nonzero if any expected alert or briefing decision does not match.

## Optional demo UI

An optional, dependency-free presentation layer can display the generated
artifacts in a browser after the required demo has run:

```bash
./run_demo.sh
python -m src.demo_ui   # http://127.0.0.1:8765
```

The page shows the run counts, both alerts, every metrics row (with the alert
and duplicate rows highlighted), the briefing, and the evaluation summary, all
read from `outputs/` and `evaluation/`, nothing recomputed. A
**Generate Live AI Briefing** button reuses the exact `src.briefing` live path:
approved facts only, the same six validation checks (displayed on screen), and
the deterministic fallback on any failure. It binds to `127.0.0.1` only and
adds no dependencies. This UI is not part of the graded review path; the
terminal output of `./run_demo.sh` remains the required evidence. Walkthrough:
[docs/ui-demo.md](docs/ui-demo.md).

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

- Presentation: Thursday, August 13, 2026, 5:40 to 5:48 PM PDT. Seven minutes plus one minute of Q&A; both team members must speak.
- Written report and code ZIP: Friday, August 14, 2026, 11:59 PM PDT.
- ZIP name: `final_project_nsfein_nnaderzad.zip`.
- Top-level folder: `final_project_nsfein_nnaderzad/`.

The detailed implementation, presentation, report, clean-room review, and packaging steps are tracked in [docs/project-checklist.md](docs/project-checklist.md).

## Limitations

This product reports a recent estimated planetary Kp condition; it does not forecast future conditions or guarantee a particular radio impact at a location. A short rolling window is chosen for a clear streaming demonstration, not as a complete propagation model. NOAA data can be delayed, revised, missing, or quiet during the demo, which is why cached replay is the required path.
