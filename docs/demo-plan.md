# Space Weather Radio-Risk Monitor: Demo Plan

This plan defines what Noam and Niki should show during the seven-minute final presentation. It is a presentation guide, not another implementation checklist. The detailed build tasks remain in `docs/project-checklist.md`.

## Demo decision

Use a short terminal-based replay through the real local Kafka path, followed by
the optional local UI as a readable view of the generated artifacts. The
terminal proves the Kafka pipeline; the UI presents the result but does not
replace or recompute the pipeline.

The demo should prove one complete path:

```text
Labeled replay event
        |
        v
Kafka producer -> kp_observations -> consumer
                                      |
                                      v
                         15-minute rolling maximum
                         + duplicate handling
                         + first Kp >= 6 crossing
                                      |
                                      v
               alert.json + metrics.csv + briefing.txt
                                      |
                                      v
                         evaluation.json + PASS
                                      |
                                      v
                         optional local demo UI
```

The required presentation path must not depend on the live NOAA endpoint, active storm conditions, Wi-Fi, or an OpenAI API key. Mention the implemented live NOAA poller briefly using saved evidence; do not run it during the timed demo because current conditions may be quiet and `run_demo.sh` intentionally resets Kafka.

## Story the audience should understand

An amateur-radio operator needs a clear indication when current planetary Kp conditions become elevated enough to create radio-risk concerns. The application turns timestamped Kp observations into an ordered Kafka stream, calculates the rolling 15-minute maximum, and emits one alert when the maximum first reaches or exceeds Kp 6. It does not repeatedly alert while conditions remain elevated.

The rule-based processor owns the risk label and alert decision. The bounded AI component may word already calculated facts as a two-sentence briefing, but it cannot change a value, label, or alert.

## Be explicit about the data

Show both of these, but do not confuse their purposes:

- `data/sample_or_replay_data/noaa_raw_sample.json` contains records captured from the real public NOAA SWPC one-minute estimated planetary Kp feed. Use one record to establish the authentic source and raw schema.
- `data/sample_or_replay_data/kp_replay.jsonl` is a project-created, deterministic threshold fixture. It is clearly labeled `synthetic://kp-threshold-fixture`. Use it to demonstrate alert, duplicate, window-expiry, and rearming behavior on demand.
- `data/fixtures/representative_event.json` is the authoritative canonical record for the README, report, and presentation. Show this Kp 6.3 event and trace it through Kafka to the first alert.

Never describe the synthetic fixture as NOAA history, a forecast, or an official NOAA alert. The project is a streaming monitor, not a forecasting model.

## Demonstration scenario

The replay contains nine messages representing eight unique event timestamps:

| Event time | Kp | Expected behavior |
|---|---:|---|
| 00:00 | 4.0 | Normal; rolling maximum is 4.0. |
| 00:05 | 5.0 | Normal; rolling maximum is 5.0. |
| 00:10 | 6.3 | First below-6 to at-or-above-6 crossing; emit alert 1. |
| 00:10 | 6.3 | Deliberate duplicate; skip it and emit no alert. |
| 00:20 | 5.5 | Rolling window still contains 6.3; remain elevated without another alert. |
| 00:25 | 5.2 | Rolling window still contains 6.3 at the inclusive boundary; no new alert. |
| 00:26 | 5.0 | The 6.3 event has expired; rolling maximum is 5.5 and the alert rearms. |
| 00:27 | 7.0 | New crossing after rearming; emit alert 2. |
| 00:30 | 6.7 | Still elevated; emit no duplicate alert. |

The `00:10` Kp 6.3 row is the frozen representative event. Publish it with Kafka key `planetary_kp`, then connect it to the first alert while explaining the architecture.

Expected final counts:

```text
Messages consumed:  9
Unique events:      8
Duplicates skipped: 1
Alerts emitted:     2
Alert times:         00:10 and 00:27 UTC
```

This scenario is valuable because it demonstrates the window and crossing state, not merely a hard-coded check of whether one Kp value is at least 6.

## Seven-minute run of show

This division matches the current deck. Both students must still understand the complete path and be ready to answer questions about any stage.

| Time | Speaker | What to show | What to explain |
|---|---|---|---|
| 0:00-0:40 | Noam | Problem/result slide | Amateur-radio operator, useful alert, and why timely interpretation matters. |
| 0:40-1:25 | Noam | NOAA source plus one raw and one canonical record | Source, four canonical fields, event time, and constant Kafka key. Clearly label the replay fixture synthetic. |
| 1:25-2:10 | Noam | Architecture chart | Replay/producer, `kp_observations`, consumer, rolling window, outputs, AI boundary, and validation. Explain that Kafka transports and orders messages; the consumer calculates risk. |
| 2:10-2:30 | Niki | Open `kp_replay.jsonl` and point to the Kp 6.3 row | One JSONL row becomes one validated Kafka message; the whole file is not sent as one message. |
| 2:30-4:10 | Niki | Terminal running `./run_demo.sh` | Point out publication to the topic, 9 processed messages, the duplicate, and exactly 2 alerts. Do not narrate every normal row. |
| 4:10-5:25 | Niki | UI from `python -m src.demo_ui` | Show two alerts, the duplicate row, rolling maximum, fallback briefing, and 7/7 evaluation. Trace the Kp 6.3 event to alert 1. |
| 5:25-5:45 | Niki | Saved live-poller terminal evidence | State that real NOAA observations also enter the same topic, but quiet conditions may not create an alert. Do not run the poller live. |
| 5:45-6:25 | Niki | AI/evidence slide | AI only words five calculated facts; fallback and validation preserve reproducibility. |
| 6:25-7:00 | Niki, then Noam | Limitation/next-step slide | Limitation: global estimated Kp is not a forecast or station-level model. Next step: a long-running consumer mode that continuously updates live metrics and the UI. End with the useful result. |

Aim for 6:30-6:45 during rehearsal so a slow transition does not exceed seven minutes.

## What should appear on screen

Keep the visual sequence small and readable:

1. One slide with the problem and expected alert.
2. One slide with the NOAA source, representative raw record, and canonical Kafka event.
3. One architecture slide showing the implemented path.
4. One large terminal window for the replay.
5. The local UI showing the alert, briefing, counts, and validation status.
6. One final slide with the limitation and realistic next step.

Use large text. Do not open an editor and tour the repository. If code must be shown, show only the few lines defining the threshold/crossing rule or event contract, and only when they are easier to understand than the architecture and output.

## Exact live demonstration sequence and script

Before presenting, Docker Desktop should already be open and the Python environment should already be installed. These setup commands belong in the README and should not consume presentation time.

### 1. Show the replay input briefly

Open `data/sample_or_replay_data/kp_replay.jsonl` and point to the Kp 6.3
representative event. Do not scroll through all nine rows.

Say:

> "This file contains nine labeled observations. The producer reads each row,
> validates it, and publishes it as a separate Kafka message. The entire file
> is not sent as one message."

Also state that the `synthetic://kp-threshold-fixture` provenance makes clear
that these threshold values are not claimed as NOAA history.

### 2. Run the Kafka pipeline

Run:

```bash
./run_demo.sh
```

Point out these lines when they appear:

```text
Published 9 event(s)
Topic=kp_observations key=planetary_kp
Processed 9 valid event(s)
emitted 2 alert(s)
```

Say:

> "Kafka stores the validated messages in order and makes them available to
> our independent consumer. Kafka does not calculate the risk. The consumer
> reads the messages and applies our rolling-window and threshold-crossing
> rules."

The script also prints:

- Kafka readiness and topic name;
- publication and processing counts;
- the four artifact paths;
- whether the deterministic or model briefing was used; and
- artifact verification, test results, and a clear nonzero exit on failure.

### 3. Show the generated result in the UI

After `run_demo.sh` finishes, run:

```bash
python -m src.demo_ui
```

Open `http://127.0.0.1:8765` and show, in this order:

1. exactly two emitted alerts;
2. the `duplicate_skipped` metrics row;
3. the rolling 15-minute maximum and rule-based label;
4. the natural-language fallback briefing; and
5. the 7/7 evaluation result.

Trace the representative event by saying:

> "This Kp 6.3 row was published to Kafka. The consumer read it, calculated a
> rolling maximum of 6.3, detected the first crossing of Kp 6, and wrote alert
> number one."

The UI reads the artifacts created by `run_demo.sh`. It does not replace Kafka,
calculate risk, or generate separate results.

If the UI cannot open, use only these compact artifact commands:

```bash
jq '.alerts' outputs/alert.json
column -s, -t < outputs/metrics.csv | sed -n '1,12p'
cat outputs/briefing.txt
jq . evaluation/evaluation.json
```

Avoid dumping the complete evaluation file if a compact summary is enough.

### 4. Mention live NOAA briefly

Use a saved terminal line such as:

```text
Published 1 new NOAA event(s) to kp_observations
```

The number may be greater than one if multiple timestamps appeared since the
poller's saved checkpoint. Say:

> "The optional poller also publishes current real NOAA observations into the
> same Kafka topic. We use the labeled replay during the presentation because
> current conditions may not cross Kp 6."

Do not run the live poller during the seven-minute presentation and do not
overwrite the replay artifacts before showing the UI.

## How the live NOAA path works

Use this section to answer questions after briefly mentioning live ingestion.
The poller does not download a permanent NOAA data file before publishing.

1. `src/live_poller.py` requests NOAA's public JSON response and holds it in
   memory.
2. It compares NOAA `time_tag` values with its local checkpoint and selects only
   observations newer than the latest one already handled.
3. It converts each selected observation into the same four-field event used by
   the replay: `time_tag`, `kp_value`, `source`, and `ingested_at`.
4. It sends each event directly to the Kafka broker running inside Docker.
5. Kafka appends each event as a separate message in the `kp_observations`
   topic. Kafka does not calculate or change the risk value.
6. A consumer reads those messages, performs deduplication and the rolling
   15-minute calculation, and writes `metrics.csv` and `alert.json`. The current
   consumer is finite; continuous live output and automatic UI refresh are the
   next step.

The poller writes only `.state/live_poller.json`, which stores the newest
handled `time_tag` so a restarted poller does not republish the same NOAA
observation. It is a checkpoint, not a copy of the NOAA dataset.

### What the two timestamps mean

- `time_tag` is when NOAA says the Kp estimate applies. It identifies the
  observation and is used for duplicate prevention and event-time processing.
- `ingested_at` is when our application fetched and converted that observation.

New observations are appended to Kafka as new messages; they do not replace the
older Kafka messages. Kafka assigns each message a new offset. The topic acts as
an ordered log, not as a CSV file with rows.

### One fetch versus continuous polling

Fetch NOAA once, publish timestamps newer than the checkpoint, and exit:

```bash
python -m src.live_poller --once
```

Fetch immediately and then automatically check again every 60 seconds until
the process is stopped with `Ctrl-C`:

```bash
python -m src.live_poller
```

The poller is not automatically started by Docker, Kafka, the UI, or
`run_demo.sh`. Someone must start one of these commands. A single poll can
publish multiple real observations if several new timestamps appeared after the
checkpoint. On the first run with no checkpoint, the poller uses NOAA's complete
response as a baseline and publishes only its newest observation so it does not
mistakenly send approximately six hours of older records as a new backlog.

### What `run_demo.sh` resets

`run_demo.sh` intentionally removes and recreates the local Kafka broker state
before publishing the nine synthetic replay messages. Any live NOAA messages
previously stored in that local Kafka topic are therefore removed. The NOAA
website, committed source sample, and `.state/live_poller.json` checkpoint are
not removed. After the demo, the poller can fetch and publish newer NOAA
observations again.

For a clean one-time live demonstration after the replay, use a separate
temporary checkpoint:

```bash
python -m src.live_poller --once \
  --state-file /tmp/space-weather-live-demo-state.json
```

Student-friendly summary to say if asked:

> "The live poller reads NOAA's JSON into memory, converts each new timestamp
> into our four-field event, and sends it directly to Kafka in Docker. Kafka
> appends and orders those messages. Our consumer, not Kafka, calculates the
> rolling risk and creates the output files. We can fetch once with `--once` or
> leave the poller running to check every 60 seconds. The replay script resets
> local Kafka data so every graded demo starts clean."

The complete story should remain:

```text
Input row -> Kafka message -> consumer calculation -> output artifacts -> UI
```

The key clarification is: Kafka transports, stores, and orders the messages;
the Python consumer performs the rolling-window calculation and alert decision.

## Statements to make during the demo

Use natural language, but cover these facts:

- “This is a deterministic, clearly labeled synthetic replay using the same canonical contract as the real NOAA input.”
- “Every replay record is published to the real local Kafka topic; demo mode does not bypass Kafka.”
- “The whole JSONL file is not one Kafka message; each row becomes its own message.”
- “Kafka transports and orders the events. Our consumer calculates the rolling maximum and decides whether to alert.”
- “The first alert is created when the rolling 15-minute maximum first crosses from below 6 to at least 6.”
- “This repeated timestamp is skipped, so it cannot create a second alert.”
- “Remaining elevated also does not create an alert every minute.”
- “After the earlier high value leaves the window, the monitor rearms and a later crossing creates a second alert.”
- “AI did not determine this alert. It only worded the calculated facts, and automatic checks reject unsupported wording.”
- “The required path works offline and without an API key.”
- “The UI displays the artifacts created by the Kafka pipeline; it does not calculate the result.”
- “The optional live poller publishes real NOAA observations to the same topic, but quiet conditions may produce no alert.”

## Evidence that must be ready

Before the presentation, preserve a known-good run containing:

- `outputs/alert.json` with exactly two expected alerts;
- `outputs/metrics.csv` with nine rows and the duplicate marked `duplicate_skipped`;
- `outputs/briefing.txt` whose values and label agree with the alert facts;
- `evaluation/evaluation.json` with expected/actual results and fact-check decisions;
- terminal output showing the final counts and `PASS`;
- a screenshot of the architecture chart; and
- one backup screenshot or short recording of the successful terminal run.

Saved evidence is a backup, not something to conceal. If the live run fails, say that the screen shows the last successful deterministic run and continue explaining the verified results.

## Failure and backup plan

| Failure | Response during presentation |
|---|---|
| NOAA or Wi-Fi unavailable | No change. The required path uses cached replay data. |
| No OpenAI key or model unavailable | Use the deterministic briefing and show that fallback was recorded. |
| Docker/Kafka fails to start | Stop after one quick attempt; switch to the saved terminal output and artifacts. |
| Terminal output is slow or unreadable | Use the saved result/evidence slide and narrate the two crossings. |
| UI fails to open | Show the generated JSON, CSV, briefing, and evaluation excerpts in the terminal. |
| Live NOAA is quiet | Expected; show saved ingestion evidence and use replay to demonstrate the alert logic. |
| An output differs from the fixture | Do not call it a pass. Use the last known-good saved evidence and state that the live run encountered a problem. |
| Presentation laptop fails | Keep the slides and known-good evidence available on both partners' computers. |

Do not debug live for more than about 15 seconds. Protect the explanation and rubric evidence.

## Rehearsal acceptance checklist

- [ ] Both partners can run `./run_demo.sh` from the documented setup.
- [ ] The demo succeeds three times without stale Kafka offsets or stale output files.
- [ ] The run works with `OPENAI_API_KEY` unset and without a NOAA request.
- [ ] The visible counts are 9 consumed, 8 unique, 1 duplicate, and 2 alerts.
- [ ] Alert timestamps and rolling maxima match `data/fixtures/replay_expected.json`.
- [ ] Every displayed artifact is regenerated by the demonstrated run.
- [ ] The UI is started only after `./run_demo.sh` and displays those same artifacts.
- [ ] The presenter says that each JSONL row becomes one Kafka message.
- [ ] The presenter says that Kafka transports/orders data and the consumer calculates risk.
- [ ] The synthetic fixture label is visible or stated aloud.
- [ ] Both partners can trace one record from JSONL through Kafka to alert and briefing.
- [ ] Both partners speak, the handoff is rehearsed, and the presentation stays under seven minutes.
- [ ] Backup evidence opens without network access.
- [ ] No `.env`, API key, notification, or unrelated browser tab is visible during screen sharing.

## Questions both partners should be ready to answer

- Why use Kafka for one global Kp stream?
- Why use the constant key `planetary_kp`?
- Why use a rolling 15-minute maximum?
- Why alert at Kp 6 rather than Kp 5?
- Why does the required demo use synthetic replay data?
- How does deduplication work?
- Why is there no second alert while the window remains elevated?
- What causes the monitor to rearm?
- Is this a forecast? Why not?
- What exactly may the AI do, and what is it prohibited from doing?
- How is an incorrect AI briefing detected?
- What works when NOAA, Wi-Fi, Docker, or the model is unavailable?
- What did each team member implement and verify?

## Things not to add for the demo

Do not spend remaining presentation time on:

- expanding the optional UI beyond its current artifact-viewer role;
- maps or geographic radio-impact claims;
- SMS, email, or push notifications;
- multiple Kafka topics without a demonstrated need;
- a forecasting model;
- a second live source;
- a live model call that makes the demonstration less reliable; or
- a live NOAA call during the timed presentation.

Those additions are not needed to prove the course-sized streaming path.

## Demo is ready when

The demo is ready when a viewer can see one representative event enter the real Kafka path, understand why two alerts and only two alerts were created, inspect the useful output, see objective validation evidence, understand the AI boundary and fallback, and hear one limitation and one realistic next step within seven minutes.
