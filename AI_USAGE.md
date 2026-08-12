# AI Usage and Verification

This project has two distinct AI disclosures: the bounded runtime briefing and AI assistance used while preparing or developing the project. This file begins as the agreed plan and must be updated with actual model names, examples, decisions, and evidence before submission.

## Bounded runtime AI task

The language model may convert already calculated alert facts into a two-sentence briefing for an amateur-radio operator.

Planned input:

```json
{
  "latest_kp": 6.33,
  "rolling_15m_max_kp": 6.67,
  "window_start_utc": "2026-08-11T15:10:00Z",
  "window_end_utc": "2026-08-11T15:25:00Z",
  "risk_label": "elevated"
}
```

Planned output artifact: `outputs/briefing.txt`

The AI does not consume the raw stream and does not decide whether an alert exists.

## Authority boundary

The deterministic consumer owns:

- the rolling-window calculation;
- the Kp 6 threshold;
- the risk label;
- the decision to emit an alert; and
- every number and timestamp passed to the model.

The model owns only wording. It may not:

- trigger, suppress, or reclassify an alert;
- change a number, label, or timestamp;
- claim a specific cause;
- add an unsupported location or impact; or
- give operational recommendations.

## Verification

The briefing is accepted only if automatic checks confirm that it is consistent with the input facts. At minimum, the validator must:

- reject any numeric Kp value not present in the approved input;
- reject a risk label that differs from the deterministic label;
- reject unsupported causes, locations, and recommendations;
- enforce the two-sentence limit; and
- save the pass/fail decision and rejection reason.

The exact checks and their limitations must be documented in the final report. A human spot-check is additional evidence, not a replacement for automated validation.

## Evaluation set

The final `evaluation/evaluation.json` should include at least these fixed cases:

| Case | Candidate behavior | Expected decision |
|---|---|---|
| Correct facts | Uses only supplied values, UTC window, and label | Accept |
| Wrong Kp | Changes or invents a Kp number | Reject |
| Wrong label | Describes a different risk state | Reject |
| Unsupported detail | Adds a cause, location, or recommendation not supplied | Reject |
| Too long | Exceeds two sentences | Reject |
| API unavailable | No model response | Use deterministic fallback |

Each saved case must include the model input, candidate output, expected decision, actual decision, check results, and whether expected matched actual. The report should state the number and percentage of cases that passed their expected outcome.

## Fallback

If no API key is provided, the request fails, or the response is rejected, the project writes a deterministic two-sentence template using the same approved facts. The required replay demo must succeed without an API key.

The fallback is part of the base design, not a hidden error path. `evaluation.json` must state whether the model or fallback produced the representative briefing.

## Runtime AI evidence to save

- [ ] Exact provider and model identifier.
- [ ] Prompt or prompt template.
- [ ] Representative model input.
- [ ] One accepted response with validator results.
- [ ] At least two rejected responses with specific rejection reasons.
- [ ] Deterministic fallback output.
- [ ] Evaluation summary and known validator gaps.
- [ ] Instructions for optional API-key setup, with no secret committed.

## AI-assisted project development

OpenAI Codex and ChatGPT helped compare project ideas, organize proposal sections, edit wording, and create the initial project plan and documentation scaffolds. Noam Fein and Niki Naderzad selected the topic, verified the course requirements and NOAA source, reviewed and revised generated content, and own the implementation, testing, evaluation, report, and explanation.

Before submission, add actual development uses to this log rather than making a broad claim that AI “built the project.”

| Date | Tool | Task | What students changed or decided | How students verified it |
|---|---|---|---|---|
| 2026-08-04 | Codex and ChatGPT | Compared ideas and drafted/reviewed proposal wording | Selected NOAA Kp topic, reduced scope, fixed alert semantics and AI boundary | Checked proposal template, proposal rubric, source, and final PDF |
| 2026-08-11 | Codex | Drafted README, source notes, AI plan, and incremental checklist | Team must review assignments, commands, schema, and deadlines before implementation | Compared with final-project requirements, written rubric, presentation rubric, proposal, and NOAA sample |
| 2026-08-12 | Codex | Scaffolded the repository and configured the Python environment | Noam chose local Docker Kafka and kept the dependency set limited to the planned implementation | Installed from scratch with Python 3.11 and ran dependency smoke tests without secrets |
| 2026-08-12 | Codex | Configured the local Kafka broker | Noam chose Docker over Confluent Cloud; the project uses one official Kafka image and no extra services | Validated Compose, broker health, topic access, message round-trip, restart, and cleanup |
| 2026-08-12 | Codex | Implemented the canonical Kafka event contract | Noam retained the agreed four fields, documented provenance allowlist, and strict validation boundary | Tested every committed NOAA/replay/invalid fixture plus timestamp, Kp, schema, serialization, and immutability edge cases |
| YYYY-MM-DD | Tool/model | Describe the specific task | Describe the human decision or edit | Name the test, review, or evidence |

## Known limitations

- String and number checks cannot prove that every sentence is scientifically complete or well phrased.
- A response can avoid banned terms and still be misleading.
- Provider or model behavior can change.
- Saved responses demonstrate the tested cases, not all possible outputs.
- The deterministic fallback is more reliable but less natural.

The team should prefer rejecting an uncertain briefing over weakening the deterministic alert path.
