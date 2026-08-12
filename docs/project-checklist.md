# Space Weather Radio-Risk Monitor: Team Build Checklist

This is the working board for Noam Fein (`nsfein`) and Niki Naderzad (`nnaderzad`). It takes the project from an empty implementation to the presentation, final report, reproducible ZIP, and submission.

**Presentation:** Thursday, August 13, 2026, 5:40–5:48 PM PDT, in person at 101 Howard, Room 529. The team has 7 minutes plus 1 minute of Q&A, and both students must speak.

**Written report and code:** Friday, August 14, 2026, 11:59 PM PDT.

## How to use this board

- Check a box only after its “done when” condition is true.
- Do not begin a task until its prerequisites are checked.
- Claim a task by replacing `Initials: ____` with `NF` for Noam, `NN` for Niki, or `NF/NN` for a genuinely joint task. Also announce the branch to the team.
- When work begins, replace `PR: ____` with `PR: pending`. After opening the PR, update the same task line with its actual number, such as `PR: #12`, and push that checklist update to the PR branch.
- Keep pull requests or commits small. Coordinate before both editing shared files such as `README.md`, `run_demo.sh`, the event contract, or the consumer.
- Add evidence paths and actual commands as work is completed.
- Both partners must be able to explain every stage before submission.

Status notation:

- `[ ]` not started
- `[~]` in progress — replace the space manually while working
- `[x]` implemented, reviewed, and verified; initials and PR number must already be filled in

## Manual and external actions

Most of this checklist is normal repository work that can be implemented and tested from a task branch. The labels below appear only where a person must act outside the codebase or make a human decision.

| Label | Meaning |
|---|---|
| `[MANUAL SETUP]` | One-time software or GitHub configuration must be completed by a person. |
| `[PERMISSION]` | Repository or course-system access must be granted or accepted. |
| `[MESSAGE]` | One partner must notify, coordinate with, or request action from another person. |
| `[HUMAN CHECK]` | A person must inspect, approve, rehearse, or verify the result. |
| `[MANUAL SUBMISSION]` | A person must upload or confirm something in an external course system. |

### One-time setup and access

- [x] **`[PERMISSION]` Invite Niki to the GitHub repository** · Initials: `NF` · PR: `N/A—GitHub setting`. Noam sent the repository invitation.
- [ ] **`[PERMISSION]` Niki accepts the invitation and verifies access** · Initials: `____` · PR: `N/A—external access`. Niki should clone or pull the repository, create a task branch when beginning real work, and confirm that she can push that branch and open a PR. Do not test access by pushing directly to `main`.
- [ ] **`[MANUAL SETUP]` Save the GitHub protection rule for `main`** · Initials: `____` · PR: `N/A—GitHub setting`. Require a pull request, one approval, and resolved conversations before merging. This needs repository administration access and is configured in GitHub, not in project code.
- [ ] **`[MANUAL SETUP]` Verify each development computer** · Initials: `____` · PR: `N/A—local setup`. Each partner who will run the project needs Git, Python 3.11, and Docker Desktop with `docker compose`. GitHub CLI (`gh`) is optional if PRs will be opened in the browser.
- [ ] **`[MANUAL SETUP]` Open Docker Desktop before the first Kafka run** · Initials: `____` · PR: `N/A—local setup`. Docker must be running; the repository's Compose file will create the broker, and the demo code will create or verify `kp_observations`. Do not install Kafka separately or manually create a Kafka environment or topic.
- [ ] **NIKI-API-1 · `[PERMISSION] [MANUAL SETUP] [MESSAGE]` Configure Niki's private OpenAI project access** · Initials: `____` · PR: `N/A—external and local setup`
  - Assigned to: Niki Naderzad (`nnaderzad`). Niki must enter `NN` herself after completing and verifying the task.
  - Prerequisites: Noam has invited Niki to the `MSDS` OpenAI API organization and added her to the `Space Weather Radio Risk` project after she accepts.
  - Follow: `docs/niki-openai-setup.md` from beginning to end.
  - Create locally: `.env` copied from `.env.example`, with Niki's own project key and `OPENAI_MODEL=gpt-5-nano`.
  - Never share the key with Noam or commit it. Verify with `git check-ignore -v .env` and `git status --short`.
  - Done when: Niki can select the shared project, has her own privately stored key, confirms `.env` is ignored, and messages Noam that setup is complete. Live-call verification happens after AI-2 is merged.

The NOAA endpoint is public and needs no account, permission, API key, or manual download. A live OpenAI key is optional and belongs only in a local `.env`; never send it to a partner or commit it. The required replay and deterministic briefing must work without it.

Human actions that repeat during development are already part of every task's definition of done: claim the task with initials, announce the branch, request the other partner's PR review, respond to review comments, and merge only after approval. These are collaboration steps, not additional implementation tasks.

## Branch and pull-request workflow

Use one branch per task with this naming pattern:

```text
<owner>/<task>-<short-description>
```

Use lowercase owner names and short kebab-case descriptions. Examples:

```text
noam/ingest-noaa-data
noam/add-risk-model
niki/dashboard-map
tom/terraform-storage
```

For this project, branches will normally start with `noam/` or `niki/`. The normal workflow is:

```bash
git switch main
git pull --ff-only
git switch -c noam/task-description

# Work, test, and commit
git push -u origin noam/task-description

# Open a PR targeting main
gh pr create --base main
```

Replace `noam/task-description` with the actual owner and task. Start this workflow only after task `P0-0` confirms that the project has a safe, dedicated Git root.

Every task heading carries two required tracking fields:

```text
- [ ] **TASK-ID · Description** · Initials: `NF` · PR: `pending`
- [x] **TASK-ID · Description** · Initials: `NF` · PR: `#12`
```

Do not put someone else's initials on a task. The person claiming or verifying the work must enter their own initials. Do not invent a PR number. The four setup/data tasks completed before this rule use the documented commit hash instead; a team member still needs to add initials after reviewing them.

Pull-request rules:

- one checklist task per branch where practical;
- branch from an up-to-date `main`;
- include the test command and result in the PR description;
- identify the output or evidence created;
- request review from the other partner;
- target `main`; and
- update the task with the actual PR number before merge; and
- check the task off only after the PR is reviewed, merged, manually verified, and attributed with initials.

## Project guardrails

These decisions are fixed unless both partners explicitly change the proposal and documentation:

| Decision | Agreed choice |
|---|---|
| User | Amateur-radio operator |
| Source | NOAA SWPC `planetary_k_index_1m.json` |
| Required review path | Local deterministic replay through Kafka |
| Topic | `kp_observations` |
| Message key | `planetary_kp` |
| Canonical fields | `time_tag`, `kp_value`, `source`, `ingested_at` |
| Processing | Deduplicate by `time_tag`; rolling 15-minute maximum |
| Alert | Emit on the first below-6 to at-or-above-6 crossing |
| Required outputs | `alert.json`, `metrics.csv`, `briefing.txt`, `evaluation.json` |
| AI authority | Wording only; never labels or triggers alerts |
| Fallback | Cached replay and deterministic briefing; no network or API key required |
| Explicitly excluded | Dashboard, prediction model, multiple feeds, deployment |

### Definition of done for every implementation task

A task is done only when:

- the code or document exists in the agreed path;
- its focused test or manual acceptance check passes;
- the implementer can explain what it does and why;
- the other partner has reviewed it;
- the task heading contains the responsible person's initials and actual PR number;
- the work used the agreed `<owner>/<task>-<short-description>` branch;
- its pull request targeted and was merged into `main`;
- any representative output has been saved; and
- the README still matches reality.

## Critical path

```text
Scope + repo skeleton
        |
Event contract + replay fixtures
        |
Local Kafka smoke test
        |
Replay producer -----> consumer/window/alert
        |                       |
        +---------- integration+
                                |
                    deterministic outputs
                                |
                    AI validator + fallback
                                |
                       one-command demo
                                |
                presentation + report evidence
                                |
                      clean-room ZIP review
```

The live NOAA poller is not on the critical path. Build it only after the replay, outputs, tests, and presentation evidence work.

## Deadline-first plan

### Tuesday, August 11 — make Kafka carry one correct alert

- [x] Establish a dedicated project Git repository before staging any files.
- [ ] Freeze scope and claim non-overlapping tasks by branch name.
- [ ] Create the repository skeleton, dependency file, environment example, and ignore rules.
- [x] Save and document a small NOAA sample.
- [x] Check that the official endpoint is current, structurally compatible, and viable; repeat before submission.
- [ ] Lock the canonical Pydantic contract and representative event.
- [ ] Create threshold, duplicate, and invalid replay fixtures.
- [ ] Start Kafka locally and pass a produce/consume smoke test.
- [ ] Implement the replay producer and consumer/window logic in parallel.
- [ ] Integrate them and create the first correct `alert.json` and `metrics.csv`.
- [ ] End the day with deterministic alert tests green.

### Wednesday, August 12 — finish the reproducible product and slides

- [ ] Make `./run_demo.sh` work from clean outputs with one command after setup.
- [ ] Add the AI briefing validator, saved evaluation cases, and deterministic fallback.
- [ ] Confirm the demo works without network access and without an OpenAI key.
- [ ] Complete the architecture chart and representative event for the presentation.
- [ ] Draft `report.pdf` from actual evidence, not planned behavior.
- [ ] Rehearse the 7-minute presentation twice; both partners speak.
- [ ] Freeze new features Wednesday night.

### Thursday, August 13 — present a stable replay

- [ ] By noon, rerun the full demo and save known-good output/evaluation artifacts.
- [ ] Use replay for the presentation; do not depend on live NOAA or a live AI call.
- [ ] Put backup screenshots or terminal output in the slides.
- [ ] Do a timed final rehearsal and prepare short Q&A answers.
- [ ] Present at 5:40 PM; both partners speak.
- [ ] After the presentation, record instructor feedback and only make controlled fixes.

### Friday, August 14 — clean-room review and submit

- [ ] Run every README command from a fresh clone/copy or clean environment.
- [ ] Finalize `report.pdf`, ownership, AI disclosure, and limitations.
- [ ] Build `final_project_nsfein_nnaderzad.zip` with one top-level folder.
- [ ] Inspect the ZIP for missing files, secrets, environments, caches, and unrelated PDFs.
- [ ] Extract the ZIP elsewhere and run the required replay from the extracted copy.
- [ ] Both partners inspect the exact final ZIP.
- [ ] Upload before 11:59 PM PDT. If Canvas has not linked the team, both upload the same ZIP.

## Phase 0 — coordination and repository foundation

- [x] **P0-0 · Establish a safe project Git root** · Initials: `NF` · PR: `N/A—commit 1840e86`
  - Prerequisites: none.
  - Branch suffix: `setup-project-repo`.
  - Completed: this directory is now its own Git repository, the default branch is `main`, and `origin` is `https://github.com/noamsfein/Space-Weather-Radio-Risk-Monitor.git`.
  - Verified: `git rev-parse --show-toplevel` returns this project directory, and the unrelated home-directory repository is no longer in scope.

- [ ] **P0-1 · Confirm the contract and claim the first tasks `[MESSAGE] [HUMAN CHECK]`** · Initials: `____` · PR: `____`
  - Prerequisites: P0-0.
  - Branch suffix: `confirm-project-contract`.
  - Do: read `README.md`, this checklist, `DATA_SOURCE.md`, `AI_USAGE.md`, and the proposal together. Confirm the fixed decisions and claim non-overlapping ready tasks.
  - Done when: both partners can explain the source-to-output path and have agreed not to add a dashboard, model, or extra source.

- [x] **P0-2 · Create implementation directories** · Initials: `NF` · PR: `#3`
  - Prerequisites: P0-1.
  - Branch suffix: `scaffold-project-layout`.
  - Create: `src/`, `tests/`, `data/sample_or_replay_data/`, `data/fixtures/`, `outputs/`, and `evaluation/`.
  - Add: `.gitkeep` only where an empty required directory must remain tracked.
  - Done when: the layout matches the README and every required final-package category has a clear destination.

- [x] **P0-3 · Pin the environment** · Initials: `NF` · PR: `#4`
  - Prerequisites: P0-1.
  - Branch suffix: `configure-python-environment`.
  - Create: `requirements.txt`, `.env.example`, `.gitignore`, and pytest configuration.
  - Include only packages actually used. Pin exact versions after the first green installation.
  - Ignore: `.env`, `.venv*`, `__pycache__/`, `.pytest_cache/`, `.DS_Store`, generated Kafka state, and local logs.
  - Done when: Python 3.11 installs the requirements in a fresh virtual environment and no secret is required for replay or test collection.

- [x] **P0-4 · Add local Kafka Compose configuration** · Initials: `NF` · PR: `#5`
  - Prerequisites: P0-1.
  - Branch suffix: `configure-local-kafka`.
  - Create: `docker-compose.yml` with one local Kafka broker and a health/readiness check.
  - Keep `localhost:9092` explicit and documented. Do not add ZooKeeper, a Kafka UI, or extra services unless required.
  - Done when: `docker compose up -d` starts the broker, a client can use `kp_observations`, and `docker compose down -v` cleans it up.

## Phase 1 — source, replay data, and event contract

- [x] **DATA-0 · Verify the source is correct, current, and viable** · Initials: `NF` · PR: `N/A—commit 1840e86`
  - Prerequisites: none for the initial check; rerun after P0-3 once the project environment exists.
  - Branch suffix: `verify-noaa-source`.
  - Fetch the official endpoint into a temporary file. Confirm HTTP success, JSON-array shape, required raw fields, numeric `estimated_kp` in 0–9, unique/ordered timestamps, recent last timestamp, and roughly one-minute cadence.
  - Record count, time span, missing/duplicate counts, minimum/maximum Kp, and number of Kp 6-or-higher records in `data/sample_or_replay_data/source_profile.json`.
  - Viability rule: the feed must contain enough ordered observations for a 15-minute window. It does not need to contain Kp 6; if it does not, the labeled replay fixture remains the required alert demonstration.
  - Initial result on 2026-08-11: 358 unique records, 357-minute span, no missing required fields, one-minute cadence, Kp range 0.00–3.33, and no Kp 6 crossing. The source is viable and the deterministic threshold fixture is required.
  - Done when: the official endpoint, committed raw sample, source documentation, canonical field mapping, and replay strategy agree. Repeat this check before the final report and update the dated profile.

- [x] **DATA-1 · Capture and attribute a raw NOAA sample** · Initials: `NF` · PR: `N/A—commit 1840e86`
  - Prerequisites: DATA-0.
  - Branch suffix: `capture-noaa-sample`.
  - Save: a small raw response or subset at `data/sample_or_replay_data/noaa_raw_sample.json` with the source URL and retrieval timestamp in the directory README.
  - Update: observed schema and rights/attribution note in `DATA_SOURCE.md`.
  - Done when: the sample parses, contains no private data, the four raw fields are confirmed, and a reviewer can tell which records are observed NOAA data.

- [x] **DATA-2 · Create labeled deterministic fixtures** · Initials: `NF` · PR: `N/A—commit 1840e86`
  - Prerequisites: DATA-1.
  - Branch suffix: `add-replay-fixtures`.
  - Create: `data/sample_or_replay_data/kp_replay.jsonl`, `data/fixtures/invalid_records.jsonl`, and `data/fixtures/replay_expected.json`. Synthetic records must not be presented as raw NOAA history.
  - The valid fixture must include below-threshold values, a first crossing, still-elevated non-duplicates, a return below threshold after window expiry, a second crossing, and one duplicate timestamp.
  - Done when: every JSON/JSONL file parses, expected rolling maxima and alert timestamps are recorded, and the synthetic source identifier is distinct from the NOAA endpoint.

- [x] **CONTRACT-1 · Implement the canonical Pydantic event** · Initials: `NF` · PR: `#6`
  - Prerequisites: DATA-1.
  - Branch suffix: `add-event-contract`.
  - Create: `src/contract.py` with `time_tag`, `kp_value`, `source`, and `ingested_at`.
  - Validate UTC timestamps, `kp_value` in 0–9, and documented source provenance. Normalize NOAA `estimated_kp` to `kp_value`; allow the synthetic fixture identifier only for replay.
  - Tests: accept representative raw and replay records; reject missing fields, malformed timestamps, nonnumeric Kp, and out-of-range values.
  - Done when: `pytest -q tests/test_contract.py` passes and the representative event serializes to the documented four-field contract.

- [x] **CONTRACT-2 · Freeze a representative event** · Initials: `NF` · PR: `#7`
  - Prerequisites: CONTRACT-1.
  - Branch suffix: `document-event-contract`.
  - Save: one representative canonical JSON record for the README, report, and presentation.
  - Done when: the same field names appear in code, tests, docs, and slides.

## Phase 2 — Kafka and replay ingestion

- [x] **KAFKA-1 · Pass a broker smoke test** · Initials: `NF` · PR: `#8`
  - Prerequisites: P0-4, P0-3, CONTRACT-1.
  - Branch suffix: `add-kafka-io`.
  - Create: small shared Kafka producer/consumer helpers if needed.
  - Do: produce one canonical test event to `kp_observations` with key `planetary_kp`, then consume it.
  - Done when: the consumed key and JSON value match what was produced and the result is reproducible after a clean broker restart.

- [x] **INGEST-1 · Implement replay producer** · Initials: `NF` · PR: `#10`
  - Prerequisites: CONTRACT-1, DATA-2, KAFKA-1.
  - Branch suffix: `add-replay-producer`.
  - Create: `src/replay_producer.py`.
  - Read JSONL in timestamp order, validate each event, publish with key `planetary_kp`, flush before exit, and support a short configurable delay.
  - Keep the deliberate duplicate so the consumer's deduplication behavior is tested. Do not bypass Kafka in demo mode.
  - Tests: use an injected or fake producer for parsing, invalid input, ordering, delivery, and flush behavior.
  - Done when: `pytest -q tests/test_replay_producer.py` passes and an integration run delivers every valid fixture message in order.

- [ ] **INGEST-2 · Implement live NOAA poller — optional until base path is green** · Initials: `____` · PR: `____`
  - Prerequisites: INGEST-1 and E2E-1 complete.
  - Branch suffix: `add-noaa-poller`.
  - Create: `src/live_poller.py` using the same normalization and producer code.
  - Poll every 60 seconds, use HTTP timeouts, publish unseen `time_tag` values only, log failures, and avoid fabricated data.
  - Tests: mock HTTP responses, time, duplicates, invalid JSON, timeouts, and empty data. Include one mocked full NOAA response so the poller is tested against the endpoint's realistic array shape and record count without making unit tests call NOAA.
  - Optional final viability check: fetch a fresh live response into a temporary file before submission, validate its shape/cadence/fields, and update the dated source profile only if the committed evidence is deliberately refreshed. Never make the required demo depend on this call.
  - Done when: a short `--once` run publishes a new event or clearly reports no new timestamp, the mocked full-response test passes, and cached replay still works if NOAA is unavailable.

## Phase 3 — stream processing and useful outputs

- [x] **PROCESS-1 · Implement deduplication and rolling window** · Initials: `NF` · PR: `#11`
  - Prerequisites: CONTRACT-1, DATA-2.
  - Branch suffix: `add-rolling-kp-window`.
  - Create: `src/processor.py` with pure processing logic independent of Kafka.
  - Use event time and an inclusive 15-minute window. Deduplicate by `time_tag`; skipped duplicates must not change state.
  - Tests: normal window updates, event exactly 15 minutes old, expired events, duplicate timestamp, and expected maximum at each fixture timestamp.
  - Done when: the focused processor tests pass and a duplicate cannot create another alert.

- [x] **PROCESS-2 · Implement crossing state** · Initials: `NF` · PR: `#12`
  - Prerequisites: PROCESS-1.
  - Branch suffix: `add-alert-crossing-state`.
  - Emit only when the prior rolling maximum is below 6 and the current maximum is at least 6. Rearm only after the maximum falls below 6.
  - Tests: direct jump from 5 to 7, sustained elevation, duplicate high value, window expiry, and a second crossing.
  - Done when: the full fixture produces exactly the labeled first and second alerts, with no duplicate alert while the window remains elevated.

- [x] **OUTPUT-1 · Write `alert.json`** · Initials: `NF` · PR: `#13`
  - Prerequisites: PROCESS-2.
  - Branch suffix: `write-alert-output`.
  - Create: output-writing logic that includes event time, latest Kp, rolling maximum, UTC window, threshold, rule-based label, source, alert ID, and run counts.
  - Use a JSON object with an `alerts` list so the replay can show both crossings. Write through a temporary file so a failed run does not leave partial JSON.
  - Done when: the saved JSON contains the two expected alerts and no AI-derived decision field.

- [x] **OUTPUT-2 · Write `metrics.csv`** · Initials: `NF` · PR: `#14`
  - Prerequisites: PROCESS-1.
  - Branch suffix: `write-metrics-output`.
  - Include: `time_tag`, Kp value, rolling maximum, risk label, alert-emitted flag, and processing status.
  - Write one row per consumed canonical Kafka message so the duplicate can appear as `duplicate_skipped`.
  - Done when: row order/count and values match the fixture and the file opens as standard CSV with no extra index column.

- [x] **PROCESS-3 · Connect Kafka consumer to processor and files** · Initials: `NF` · PR: `#16`
  - Prerequisites: KAFKA-1, PROCESS-2, OUTPUT-1, OUTPUT-2.
  - Branch suffix: `connect-stream-processor`.
  - Create: `src/stream_processor.py`.
  - Consume canonical events from `kp_observations`, apply one processor instance, write outputs, and exit predictably after the finite replay using a documented idle timeout or equivalent finite-run rule.
  - Handle malformed Kafka values without crashing the whole run, close the consumer, and return nonzero on Kafka or output failure.
  - Done when: real Kafka replay creates the same alerts and metrics as the pure fixture test.

## Phase 4 — bounded AI and evaluation

- [x] **AI-1 · Define briefing facts and deterministic fallback** · Initials: `NF` · PR: `#17`
  - Prerequisites: OUTPUT-1.
  - Branch suffix: `add-briefing-fallback`.
  - Create: `src/briefing.py` with structured input containing only latest Kp, rolling maximum, UTC window, and rule-based label.
  - Implement the two-sentence deterministic template first, including a no-alert form.
  - Done when: `briefing.txt` is produced with no API key and every number/label comes from `alert.json`.

- [x] **AI-2 · Add optional model call** · Initials: `NF` · PR: `#21`
  - Prerequisites: AI-1.
  - Branch suffix: `add-optional-ai-briefing`.
  - Read an optional API key from the environment; never commit it. Keep provider/model, timeout, and prompt visible in configuration or code.
  - Ask only for a two-sentence briefing from supplied facts. Use an injected client so tests never make a live call.
  - Done when: one model response can be saved for evaluation, while missing credentials or request failure automatically uses the fallback.

- [x] **AI-3 · Implement automatic briefing checks** · Initials: `NF` · PR: `#18`
  - Prerequisites: AI-1.
  - Branch suffix: `validate-ai-briefing`.
  - Reject changed or invented Kp numbers, a mismatched label, unsupported causes/locations/recommendations, empty output, and more than two sentences.
  - Return explicit rejection reasons. Do not silently repair a rejected response and call it accepted.
  - Done when: fixed accepted and rejected candidates receive their expected decisions in `tests/test_briefing.py`.

- [~] **AI-4 · Save evaluation evidence** · Initials: `NF` · PR: `#23`
  - Prerequisites: AI-2, AI-3.
  - Branch suffix: `add-evaluation-harness`.
  - Create: `src/evaluate.py` and `evaluation/evaluation.json` containing expected/actual alert results plus AI input, candidate output, expected/actual decision, checks, rejection reasons, fallback status, totals, and pass rate.
  - Include correct, wrong-number, wrong-label, unsupported-detail, too-long, and unavailable-API cases.
  - Done when: `python -m src.evaluate` is deterministic over saved candidates, returns nonzero on failed acceptance checks, and honestly records failures.

- [ ] **AI-5 · Complete `AI_USAGE.md` from actual work** · Initials: `____` · PR: `____`
  - Prerequisites: AI-4.
  - Branch suffix: `finalize-ai-disclosure`.
  - Replace planned wording with the actual model/provider, prompt, accepted/rejected evidence, verification, limitations, fallback, and development-assistance log.
  - Done when: both partners agree it accurately discloses runtime and development AI use without claiming AI owned student decisions.

## Phase 5 — testing and one-command review path

- [x] **TEST-1 · Complete contract and source tests** · Initials: `NN` · PR: `#24`
  - Prerequisites: CONTRACT-1.
  - Branch suffix: `complete-contract-tests`.
  - Test valid source normalization, UTC handling, missing field, malformed time, nonnumeric Kp, NaN/infinity, and Kp outside 0–9.
  - Done when: `pytest -q tests/test_contract.py` passes and each validation rule has a positive or negative case.

- [x] **TEST-2 · Complete window and alert tests** · Initials: `NN` · PR: `#25`
  - Prerequisites: PROCESS-2.
  - Branch suffix: `complete-processor-tests`.
  - Test the exact 15-minute boundary, direct jump above 6, still-elevated observations, duplicate timestamp, window expiry, rearm, and second crossing.
  - Done when: exact expected alert count and trigger timestamps match the fixture.
  - Audit 2026-08-12 (NN): every required case is covered in `tests/test_processor.py`; alert count and trigger timestamps are asserted against `data/fixtures/replay_expected.json`. Command: `pytest -q tests/test_processor.py` (13 passed).

- [x] **TEST-3 · Complete output and AI tests** · Initials: `NN` · PR: `#26`
  - Prerequisites: OUTPUT-2, AI-4.
  - Branch suffix: `complete-output-ai-tests`.
  - Test JSON/CSV shape, fact agreement, accepted/rejected AI cases, provider failure, and fallback without credentials.
  - Done when: corrupting an output fact, CSV header/count, or candidate response causes a clear focused failure without a live API call.
  - Audit 2026-08-12 (NN): every required case is covered across `tests/test_alert_output.py`, `tests/test_metrics_output.py`, `tests/test_briefing.py`, and `tests/test_evaluate.py`; all AI cases use injected fake clients, and no test makes a live call. Command: `pytest -q tests/test_alert_output.py tests/test_metrics_output.py tests/test_briefing.py tests/test_evaluate.py` (52 passed).

- [x] **DEMO-1 · Build `run_demo.sh`** · Initials: `NN` · PR: `#27`
  - Prerequisites: INGEST-1, PROCESS-3, AI-4.
  - Branch suffix: `add-one-command-demo`.
  - Start and wait for Kafka, clear only generated demo artifacts, run the finite consumer and replay in a controlled order, wait for completion, create all four artifacts, and run acceptance tests.
  - Use `set -euo pipefail`, clean up background child processes, surface logs on failure, and avoid hidden manual terminal steps.
  - Print artifact paths and a short result summary.
  - Done when: one command after documented setup runs start to finish, exits nonzero on failure, and three consecutive runs do not reuse stale output or offsets.

- [~] **E2E-1 · Required end-to-end replay acceptance** · Initials: `NN` · PR: `#28`
  - Prerequisites: DEMO-1, TEST-1, TEST-2, TEST-3.
  - Branch suffix: `verify-end-to-end-replay`.
  - Run: `./run_demo.sh` through the actual local Kafka broker.
  - Verify: expected alerts; metrics match the fixture; duplicate counts match; briefing is accepted or uses fallback; evaluation matches labels.
  - Save: representative `outputs/` and `evaluation/` artifacts.
  - Done when: both partners independently run it successfully and can trace one record from JSONL to Kafka to alert to briefing.
  - Niki's run 2026-08-12 (NN): `./run_demo.sh` on merged `main` passed — 9 events through the local broker, 2 alerts at the labeled timestamps, all metrics rows and duplicate counts match the fixture, briefing via deterministic fallback, evaluation 7/7, suite 141 passed. Representative artifacts committed under `outputs/` and `evaluation/`. Awaiting Noam's independent run before checking off.

- [~] **E2E-2 · Offline/no-key acceptance** · Initials: `NN` · PR: `#28`
  - Prerequisites: E2E-1.
  - Branch suffix: `verify-offline-fallback`.
  - Run with `OPENAI_API_KEY` unset and without relying on NOAA.
  - Done when: replay still passes, `briefing.txt` clearly comes from the deterministic fallback, and the README identifies this as the required reviewer path.
  - Niki's run 2026-08-12 (NN): `env -u OPENAI_API_KEY ./run_demo.sh` passed with identical artifacts; briefing source reported `fallback`, and the README already states no network or API key is required for the required replay review path.

- [ ] **E2E-DATA · Larger replay robustness test — optional after the base path is green** · Initials: `____` · PR: `____`
  - Prerequisites: E2E-1 and E2E-2.
  - Branch suffix: `test-larger-replay`.
  - Create or generate a separately labeled deterministic replay of approximately 100–300 canonical events. Preserve event-time order and include enough normal, elevated, duplicate, expiry, and rearm cases to verify longer-running state behavior.
  - Run it through the real Kafka producer and consumer, record expected/actual message, unique-event, duplicate, and alert counts, and confirm processing completes without stale offsets or reused outputs.
  - Keep the nine-message fixture as the presentation and required reviewer path; summarize the larger result instead of presenting every row.
  - Done when: the larger replay has a reproducible generator or committed non-private fixture, a deterministic expected-results file, a passing automated Kafka acceptance test, and a short saved summary. Skip this task if any base requirement is incomplete.

- [ ] **E2E-3 · Failure recovery demonstration — optional bonus only** · Initials: `____` · PR: `____`
  - Prerequisites: every base task through E2E-2 and core docs complete.
  - Branch suffix: `demonstrate-failure-recovery`.
  - Demonstrate a controlled broker/process failure and recovery using the same input, with exact reviewer steps and saved evidence.
  - Done when: it is a working, clearly labeled extension with exact commands and saved output. Skip it if any base requirement remains incomplete.

- [x] **UI-1 · Optional local demo UI — presentation layer only, agreed 2026-08-12** · Initials: `NN` · PR: `#33`
  - Prerequisites: E2E-1 and E2E-2 (the base path stayed untouched and green).
  - Branch suffix: `add-optional-demo-ui`.
  - Scope note: the guardrails exclude a dashboard from the required product; this task adds `src/demo_ui.py` only as a clearly labeled optional viewer of already-generated artifacts, agreed by both partners via this PR's review. It adds no dependencies, binds to `127.0.0.1` only, and never appears in the required review path.
  - The "Generate Live AI Briefing" button reuses `src.briefing` unchanged: approved facts only, the same validator, deterministic fallback on any failure.
  - Done when: `python -m src.demo_ui` serves the artifacts after `./run_demo.sh`, the button shows a validated model briefing or the fallback with reasons, `pytest -q tests/test_demo_ui.py` passes with no live call, and the README and `docs/ui-demo.md` label the layer optional.

## Phase 6 — README, report, and rubric evidence

- [~] **DOC-1 · Make README commands factual** · Initials: `NN` · PR: `#29`
  - Prerequisites: E2E-1.
  - Replace target/planned language with exact tested prerequisites, setup, one-command run, expected output, validation, troubleshooting, and cleanup.
  - Map any layout differences from the required package structure.
  - Done when: the other partner follows only the README from a clean copy and succeeds.

- [~] **DOC-2 · Finalize source documentation** · Initials: `NN` · PR: `#30`
  - Prerequisites: DATA-1, plus INGEST-2 or a documented decision to omit it.
  - Complete owner, URL, access, rights, schema, polling/rate-limit assumptions, failures, limitations, cache provenance, and replay details.
  - Done when: every item requested for `DATA_SOURCE.md` by the course handout is easy to locate.

- [~] **DOC-3 · Draw final architecture chart** · Initials: `NN` · PR: `#29`
  - Prerequisites: E2E-1.
  - Show the implemented path, not the proposal plan. Separate optional live components from the required replay and Kafka path.
  - Use the same chart in the report and presentation when possible.
  - Done when: one representative event can be traced across every box and every box maps to submitted code or artifacts.

- [~] **REPORT-1 · Draft problem and result section** · Initials: `NN` · PR: `#31`
  - Prerequisites: E2E-1.
  - Cover target user, problem, narrow scope, alert rule, and one observable representative result.
  - Done when: it directly supports written-rubric category 1 without marketing language.

- [~] **REPORT-2 · Draft data and contract section** · Initials: `NN` · PR: `#31`
  - Prerequisites: DOC-2, CONTRACT-2.
  - Cover source/limitations, raw-to-canonical mapping, validation, topic/key, representative event, dedup identity, and replay provenance.
  - Done when: it directly supports written-rubric category 2.

- [~] **REPORT-3 · Draft architecture and implementation section** · Initials: `NN` · PR: `#31`
  - Prerequisites: DOC-3.
  - Cover the end-to-end chart, one real replay example, rolling/crossing logic, outputs, and why a one-topic local Kafka design was chosen.
  - Done when: it directly supports written-rubric category 3 and describes implemented behavior only.

- [~] **REPORT-4 · Draft evidence and reproducibility section** · Initials: `NN` · PR: `#31`
  - Prerequisites: E2E-2, AI-5.
  - Cover test/evaluation results, bounded AI and verification, exact review path, expected artifacts, fallback, team contributions, limitations, and one realistic next step.
  - Done when: it directly supports written-rubric category 4.

- [~] **REPORT-5 · Assemble and verify `report.pdf` `[HUMAN CHECK]`** · Initials: `NN` · PR: `#31`
  - Prerequisites: REPORT-1 through REPORT-4.
  - Keep it concise and use readable charts/code samples. Include actual result/evaluation numbers.
  - Render every page and check for clipping, tiny text, inconsistent filenames, planned-vs-actual claims, and missing attribution.
  - Done when: both partners read the rendered PDF and all four 5-point rubric categories have explicit evidence.

### Written rubric evidence map

| Category | Required full-credit evidence | Planned locations |
|---|---|---|
| 1. Problem and useful result | Problem, target user, useful observable result | README; report; `outputs/alert.json` |
| 2. Data and event contract | Source/limitations, validated Kafka event, key fields, sample | `DATA_SOURCE.md`; `src/contract.py`; report |
| 3. Architecture and implementation | Architecture chart, working Kafka path, example, design reason | README/report chart; `src/`; demo output |
| 4. Evidence and reproducibility | Validation/eval, bounded AI verification, exact review, expected output, organized files, ownership | README; `AI_USAGE.md`; tests; `evaluation/`; report |

Do not pursue the optional +3 extension until every row above has complete evidence.

## Phase 7 — presentation

- [~] **PRES-1 · Build a short evidence-first deck** · Initials: `NN` · PR: `#32`
  - Prerequisites: E2E-1, DOC-3.
  - Suggested flow: problem/result; source and representative event; architecture/design choice; replay result and validation; AI boundary/evaluation; lesson, limitation, and next step.
  - Done when: every presentation-rubric category is explicit and the deck does not depend on reading small code.

- [~] **PRES-2 · Prepare stable demo evidence** · Initials: `NN` · PR: `#32`
  - Prerequisites: E2E-1.
  - Prefer a short replay or saved output. Put backup terminal output or screenshots in the deck.
  - Done when: the story still works if Docker, NOAA, Wi-Fi, or the OpenAI API fails during class.

- [ ] **PRES-3 · Divide the 7 minutes `[MESSAGE] [HUMAN CHECK]`** · Initials: `____` · PR: `____`
  - Prerequisites: PRES-1.
  - Both must speak. Agree on a roughly equal split and simple handoff.
  - Done when: transitions are scripted and neither partner exceeds about 3.5 minutes.

- [ ] **PRES-4 · Rehearse and prepare Q&A `[MESSAGE] [HUMAN CHECK]`** · Initials: `____` · PR: `____`
  - Prerequisites: PRES-2, PRES-3.
  - Rehearse twice under 7 minutes.
  - Be ready to explain: why Kafka; why the constant key; why 15 minutes; why Kp 6; why replay; duplicate/crossing behavior; why AI is bounded; limitations; and what each partner contributed.
  - Done when: both can answer without relying on the other and can trace the full event path.

### Presentation rubric check

- [ ] Clear problem, user, useful result, and why it matters.
- [ ] NOAA source, Kafka event, key fields, and representative record.
- [ ] Implemented architecture, concrete example, and design reason.
- [ ] Evidence-based lesson or limitation and one realistic next step.
- [ ] Both students speak and the total presentation stays within 7 minutes.

## Phase 8 — final package and submission

- [ ] **PKG-1 · Confirm required package contents** · Initials: `____` · PR: `____`
  - Prerequisites: REPORT-5, DOC-1, DOC-2, AI-5.
  - The final top-level folder must contain or clearly map: `README.md`, `DATA_SOURCE.md`, `AI_USAGE.md`, `requirements.txt`, `.env.example`, `src/`, sample/replay data, representative output, evaluation evidence, and `report.pdf`.
  - Include tests, Compose configuration, and demo files needed by the README.
  - Done when: every required item is present and referenced by the README.

- [ ] **PKG-2 · Scan for prohibited or unrelated files** · Initials: `____` · PR: `____`
  - Prerequisites: PKG-1.
  - Exclude: `.env`, keys/tokens, virtual environments, caches, `__pycache__`, broker data, `.DS_Store`, generated dependency folders, course handout PDFs, proposal-building temp files, and unrelated large files.
  - Search submitted text for likely secrets and inspect the archive listing.
  - Done when: no credentials or unnecessary local files are present.

- [ ] **PKG-3 · Create the exact archive** · Initials: `____` · PR: `____`
  - Prerequisites: PKG-2.
  - Name: `final_project_nsfein_nnaderzad.zip`.
  - Top-level folder: `final_project_nsfein_nnaderzad/`.
  - Done when: opening the ZIP shows exactly one top-level project folder.

- [ ] **PKG-4 · Clean-room TA test from extracted ZIP `[HUMAN CHECK]`** · Initials: `____` · PR: `____`
  - Prerequisites: PKG-3.
  - Extract to a new directory. Follow only the included README. Use no network and no OpenAI key for the required replay if practical.
  - Confirm all expected artifacts and validation evidence are created.
  - Done when: the extracted submission passes, cleanup works, and any discrepancy is fixed in the source and rebuilt into a new ZIP.

- [ ] **SUBMIT-1 · Final joint approval and upload `[MESSAGE] [HUMAN CHECK] [MANUAL SUBMISSION]`** · Initials: `____` · PR: `____`
  - Prerequisites: PKG-4.
  - Both partners review the exact final file so the same ZIP is submitted.
  - Upload before Friday, August 14 at 11:59 PM PDT. If Canvas has not linked the team, both students upload the same ZIP.
  - `[MESSAGE]` If Canvas team membership or the required upload path is unclear, contact the instructor or TA early and keep their response with the submission evidence.
  - Done when: Canvas confirms the correct filename and upload for each required student.

## Scope-cut rules

Use these without debate if the critical path slips:

1. If the Kafka replay is not green by Wednesday noon, stop work on the live poller.
2. If the OpenAI call is unreliable, keep saved examples plus the deterministic fallback; do not weaken the alert path.
3. Do not build a dashboard, database, notification service, second topic, schema registry, or prediction model.
4. Use one broker, one topic, and one partition for the minimum demo unless a tested need says otherwise.
5. Skip the optional bonus unless the base report/code evidence is complete and the clean-room replay passes.
6. The presentation uses cached replay and saved artifacts even if the live components work.

## Final handoff questions

Before submission, both Noam and Niki should answer all of these:

- What exact problem does the alert solve, and what does it not claim to do?
- Which raw NOAA field becomes `kp_value`, and what are the source limitations?
- Why is `planetary_kp` a constant Kafka key?
- How does the 15-minute event-time window work at its boundary?
- What prevents repeated alerts while an elevated value remains in the window?
- What happens to invalid, duplicate, late, or unavailable data?
- Which facts can the AI see, what can it decide, and how is output rejected?
- How does the required demo work without NOAA or an API key?
- What evidence proves the output is correct?
- What did each partner contribute, review, and learn?

If either partner cannot answer one, schedule a walkthrough before the final ZIP is approved.
