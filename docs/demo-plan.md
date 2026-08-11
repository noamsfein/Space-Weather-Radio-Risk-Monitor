# Space Weather Radio-Risk Monitor: Demo Plan

This plan defines what Noam and Niki should show during the seven-minute final presentation. It is a presentation guide, not another implementation checklist. The detailed build tasks remain in `docs/project-checklist.md`.

## Demo decision

Use a short terminal-based replay through the real local Kafka path. Do not build a frontend solely for the presentation.

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
```

The required presentation path must not depend on the live NOAA endpoint, active storm conditions, Wi-Fi, or an OpenAI API key.

## Story the audience should understand

An amateur-radio operator needs a clear indication when current planetary Kp conditions become elevated enough to create radio-risk concerns. The application turns timestamped Kp observations into an ordered Kafka stream, calculates the rolling 15-minute maximum, and emits one alert when the maximum first reaches or exceeds Kp 6. It does not repeatedly alert while conditions remain elevated.

The rule-based processor owns the risk label and alert decision. The bounded AI component may word already calculated facts as a two-sentence briefing, but it cannot change a value, label, or alert.

## Be explicit about the data

Show both of these, but do not confuse their purposes:

- `data/sample_or_replay_data/noaa_raw_sample.json` contains records captured from the real public NOAA SWPC one-minute estimated planetary Kp feed. Use one record to establish the authentic source and raw schema.
- `data/sample_or_replay_data/kp_replay.jsonl` is a project-created, deterministic threshold fixture. It is clearly labeled `synthetic://kp-threshold-fixture`. Use it to demonstrate alert, duplicate, window-expiry, and rearming behavior on demand.

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

Use `Speaker A` and `Speaker B` until the team assigns the sections during task `PRES-3`. Both students must speak and must understand every section.

| Time | Speaker | What to show | What to explain |
|---|---|---|---|
| 0:00-0:40 | A | Problem/result slide | Amateur-radio operator, useful alert, and why timely interpretation matters. |
| 0:40-1:25 | A | NOAA source plus one raw and one canonical record | Source, four canonical fields, event time, and constant Kafka key. Clearly label the replay fixture synthetic. |
| 1:25-2:10 | B | Architecture chart | Replay/producer, `kp_observations`, consumer, rolling window, outputs, AI boundary, and validation. Give one reason for Kafka: an ordered, replayable event path. |
| 2:10-4:05 | B, then A | Terminal running `./run_demo.sh` | Follow the 6.3 crossing, duplicate skip, rearm, and second crossing. Do not narrate every normal row. |
| 4:05-5:05 | A | Alert, metrics summary, and briefing | Show the useful result. State that the calculated facts and rule-based label exist before AI wording. |
| 5:05-6:05 | B | Evaluation summary | Show expected versus actual counts, fact checks, fallback behavior, and overall PASS. |
| 6:05-7:00 | A and B | Limitation/next-step slide | Limitation: the live feed may remain quiet and estimated values may be revised. Next step: continuous live polling and a delivery channel after the reproducible core is stable. End with the useful result. |

Aim for 6:30-6:45 during rehearsal so a slow transition does not exceed seven minutes.

## What should appear on screen

Keep the visual sequence small and readable:

1. One slide with the problem and expected alert.
2. One slide with the NOAA source, representative raw record, and canonical Kafka event.
3. One architecture slide showing the implemented path.
4. One large terminal window for the replay.
5. One result/evidence view showing the alert, briefing, counts, and validation status.
6. One final slide with the limitation and realistic next step.

Use large text. Do not open an editor and tour the repository. If code must be shown, show only the few lines defining the threshold/crossing rule or event contract, and only when they are easier to understand than the architecture and output.

## Live terminal sequence

Before presenting, Docker Desktop should already be open and the Python environment should already be installed. These setup commands belong in the README and should not consume presentation time.

The live presentation command is:

```bash
./run_demo.sh
```

The script should print, without extra manual steps:

- Kafka readiness and topic name;
- the compact event progression;
- both alert timestamps;
- message, unique-event, duplicate, and alert counts;
- the four artifact paths;
- whether the deterministic or model briefing was used; and
- a final acceptance result of `PASS` or a clear nonzero failure.

After the script finishes, show only the most useful artifact excerpts. Candidate commands are:

```bash
jq '.alerts' outputs/alert.json
column -s, -t < outputs/metrics.csv | sed -n '1,12p'
cat outputs/briefing.txt
jq . evaluation/evaluation.json
```

Finalize these commands after the artifact schemas are implemented. Avoid dumping a long evaluation file if a compact summary can show expected versus actual results more clearly.

## Statements to make during the demo

Use natural language, but cover these facts:

- “This is a deterministic, clearly labeled synthetic replay using the same canonical contract as the real NOAA input.”
- “Every replay record is published to the real local Kafka topic; demo mode does not bypass Kafka.”
- “The first alert is created when the rolling 15-minute maximum first crosses from below 6 to at least 6.”
- “This repeated timestamp is skipped, so it cannot create a second alert.”
- “Remaining elevated also does not create an alert every minute.”
- “After the earlier high value leaves the window, the monitor rearms and a later crossing creates a second alert.”
- “AI did not determine this alert. It only worded the calculated facts, and automatic checks reject unsupported wording.”
- “The required path works offline and without an API key.”

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

Do not spend base-project time on:

- a dashboard or frontend;
- maps or geographic radio-impact claims;
- SMS, email, or push notifications;
- multiple Kafka topics without a demonstrated need;
- a forecasting model;
- a second live source; or
- a live model call that makes the demonstration less reliable.

Those may be future work, but none is needed to prove the course-sized streaming path.

## Demo is ready when

The demo is ready when a viewer can see one representative event enter the real Kafka path, understand why two alerts and only two alerts were created, inspect the useful output, see objective validation evidence, understand the AI boundary and fallback, and hear one limitation and one realistic next step within seven minutes.
