# AI Usage and Verification

This project uses AI in two separate ways: an optional runtime briefing and
AI-assisted project development. The runtime model is restricted to wording
facts that the deterministic stream processor has already calculated. It does
not read the raw Kafka stream, calculate Kp metrics, assign the risk label, or
decide whether to emit an alert.

## Runtime AI configuration

| Setting | Implemented value |
|---|---|
| Provider | OpenAI |
| API | Responses API (`client.responses.create`) |
| Configured model identifier | `gpt-5-nano` |
| Reasoning effort | `low` |
| Maximum output tokens | 600 |
| Client timeout | 10 seconds |
| Automatic retries | 0 |
| Required for the replay demo | No |

`gpt-5-nano` is the exact model alias sent by the application. The project does
not claim a snapshot identifier because no committed live response records the
resolved snapshot. The model can be overridden locally with `OPENAI_MODEL`, but
the committed configuration, documentation, and deterministic evaluation all
use `gpt-5-nano`.

The live path is optional and explicit:

```bash
python -m src.briefing --use-live-ai \
  --candidate-path evaluation/live_candidate.txt
```

Only this command loads `.env`. The required replay path uses the deterministic
fallback and neither reads an API key nor contacts OpenAI. API keys are private,
local values; `.env` is ignored and `.env.example` contains no credential.

## Input and authority boundary

The model receives exactly five fields from the most recent deterministic
alert. The representative input from the committed replay is:

```json
{
  "latest_kp": 7.0,
  "rolling_15m_max_kp": 7.0,
  "window_start_utc": "2026-08-11T00:12:00Z",
  "window_end_utc": "2026-08-11T00:27:00Z",
  "risk_label": "elevated"
}
```

The application serializes this as compact, sorted JSON. The deterministic
consumer owns:

- validation and normalization of the source event;
- the inclusive rolling 15-minute maximum;
- the Kp 6 alert threshold;
- the `normal` or `elevated` risk label;
- the threshold-crossing decision; and
- every number and timestamp supplied to the model.

The model owns only the wording of a briefing. It may not trigger, suppress, or
reclassify an alert; alter a value or timestamp; assert a cause, location,
impact, or forecast; or give an operational recommendation.

## Exact prompt

The following instruction is defined as `MODEL_INSTRUCTIONS` in
`src/briefing.py` and saved in `evaluation/evaluation.json`:

> Write a concise briefing of no more than two sentences using only the facts
> supplied as JSON. Include the rule-based risk label. Do not add causes,
> locations, impacts, recommendations, forecasts, or any numbers or timestamps
> that are not supplied. Return only the briefing text.

The JSON shown above is passed separately as the Responses API input. No raw
NOAA record, Kafka metadata, alert rule, source description, user profile, or
location is sent to the model.

## Output validation and fallback

`validate_briefing` applies six deterministic checks before model text can be
written as the accepted briefing:

1. `nonempty` rejects a missing or whitespace-only response.
2. `sentence_limit` allows no more than two detected sentences.
3. `risk_label` requires the unnegated word `elevated` and rejects a conflicting
   known label such as `normal`.
4. `approved_numbers` rejects numeric values other than the supplied Kp values;
   the phrase `15-minute` is explicitly allowed.
5. `approved_timestamps` rejects ISO-like timestamps outside the supplied UTC
   window.
6. `unsupported_details` rejects matched cause, location, impact, and
   recommendation phrases.

The validator returns every check result and explicit rejection reasons. It
does not edit or repair a failed response. A candidate is used only when all
checks pass. Otherwise, the output comes from this deterministic two-sentence
template:

> Elevated radio-risk conditions were detected with a latest Kp of 7 and a
> rolling 15-minute maximum of 7. The UTC window ran from
> 2026-08-11T00:12:00Z to 2026-08-11T00:27:00Z, and the rule-based risk label
> was elevated.

The same fallback is used when live AI was not requested, the API key is
missing, no alert facts exist, the request fails, the response has no text, or
the response fails validation. A separate no-alert template contains no Kp
number or timestamp.

## Saved evaluation evidence

Run this command to regenerate the committed evidence without Kafka, a key, or
network access:

```bash
python -m src.evaluate
```

`evaluation/evaluation.json` records the provider, configured model, exact
prompt, five-field input boundary, model input, candidate output,
expected/actual decision, individual checks, rejection reasons, fallback
status, and expected-versus-actual result for each case. It also replays the
canonical events in memory and compares the two produced alerts with the
committed oracle.

The current saved result is 7/7 assertions passed: one alert comparison and six
AI boundary cases.

| Case | Saved candidate behavior | Actual decision | Final source |
|---|---|---|---|
| `correct` | Uses the supplied values, window, and label | Accepted | Candidate |
| `wrong_number` | Claims Kp 8 | Rejected: unsupported number | Fallback |
| `wrong_label` | Claims `normal` | Rejected: wrong label | Fallback |
| `unsupported_detail` | Attributes conditions to a solar flare | Rejected: unsupported cause | Fallback |
| `too_long` | Returns three sentences | Rejected: sentence limit | Fallback |
| `api_unavailable` | Simulates a timeout and returns no candidate | Unavailable | Fallback |

The accepted candidate in the deterministic evaluation is the project-authored
fallback text shown above. The rejected candidates are also project-authored
boundary tests. They are not represented as outputs from a fresh live model
call. If the optional live command is run, its raw response can be saved to the
git-ignored `evaluation/live_candidate.txt`; it is still used only after the
same validator accepts it.

## Verification performed

- `python -m src.evaluate` regenerates the evidence deterministically and exits
  nonzero if an expected alert or AI decision does not match.
- `tests/test_briefing.py` covers the five-field input boundary, exact fallback,
  request arguments, missing credentials, timeout, malformed output, accepted
  and rejected candidates, candidate saving, and atomic writes.
- `tests/test_evaluate.py` verifies all six saved cases, evidence fields,
  byte-for-byte deterministic output, no-network behavior, failure exit status,
  and atomic writes.
- The full local suite on 2026-08-12 passed: 167 standard tests passed and 3
  opt-in Kafka integration tests were skipped by the default command. All 3
  Docker-backed integration tests also passed when enabled separately.
- The committed required demo evidence records two expected alerts, nine
  metrics rows, and 7/7 evaluation assertions without an OpenAI request.

## Runtime evidence checklist

- [x] Provider and configured model identifier: OpenAI, `gpt-5-nano`.
- [x] Exact prompt template.
- [x] Representative input from the committed replay.
- [x] Accepted project-authored candidate with all validator results.
- [x] Four rejected candidates with specific rejection reasons.
- [x] Simulated API-unavailable case and deterministic fallback.
- [x] Evaluation summary and validator limitations.
- [x] Optional private API-key setup with no committed secret.
- [ ] A live model candidate and resolved snapshot identifier. This is optional,
  is not required for the deterministic demo, and has not been claimed as saved
  evidence.

## AI-assisted project development

OpenAI Codex and ChatGPT assisted with ideation, planning, documentation,
implementation drafts, tests, and review. Noam Fein and Niki Naderzad selected
the topic and scope, verified the course requirements and NOAA source, accepted
or changed design choices, ran the project, reviewed generated work, and remain
responsible for the submitted implementation and explanation.

| Date | Tool | Assisted task | Student decision or revision | Verification |
|---|---|---|---|---|
| 2026-08-04 | Codex and ChatGPT | Compared ideas and drafted/reviewed proposal wording | Selected the NOAA Kp topic, reduced scope, and fixed the alert semantics and AI authority boundary | Checked the proposal template, rubrics, source, and final PDF |
| 2026-08-11 | Codex | Drafted the README, source notes, AI plan, and incremental checklist | Kept a deterministic replay as the required path and made live NOAA and OpenAI optional | Compared the plan with the proposal, rubrics, and NOAA sample |
| 2026-08-12 | Codex | Scaffolded the repository, Python environment, and local Kafka setup | Chose local Docker Kafka, one topic and partition, and a limited pinned dependency set | Reinstalled dependencies and tested broker health, round trips, restart, and cleanup |
| 2026-08-12 | Codex | Drafted the event contract, replay producer, Kafka I/O, processor, and output writers | Retained four canonical fields, constant-key ordering, event-time deduplication, an inclusive window, threshold crossing/rearm semantics, and atomic artifacts | Tested fixtures and edge cases, then compared the real Kafka path with the committed oracle |
| 2026-08-12 | Codex | Drafted the bounded briefing, validator, fallback, and evaluation harness | Retained a five-field wording-only boundary, explicit rejection instead of repair, a no-key fallback, and project-authored evaluation cases | Ran briefing/evaluation tests, regenerated saved evidence, and confirmed a deliberately wrong expectation fails |
| 2026-08-12 | Codex | Reviewed the repository and completed this AI disclosure | Required honest separation between deterministic cases and live model evidence; did not claim an unsaved live call | Ran the full local suite (167 passed, 3 opt-in tests skipped), separately passed all 3 Docker-backed integration tests, and regenerated `evaluation/evaluation.json` |

This log describes assistance, not authorship or independent verification by the
model. Team members should review this disclosure and add any material AI use
that is not represented here before submission.

## Known limitations

- The validator uses regular expressions and a finite banned-phrase list. It
  cannot prove that every accepted sentence is scientifically complete,
  semantically faithful, or well written.
- Sentence detection is punctuation-based and can miscount unusual
  abbreviations or formatting.
- Numeric equality accepts equivalent formatting such as `7` and `7.0`, but it
  does not understand more complex paraphrases or word-form numbers.
- A response could avoid the known unsupported-detail patterns and still imply
  an unsupported cause, impact, location, forecast, or recommendation.
- The validator requires the correct risk label but does not require every
  supplied number and timestamp to appear.
- The configured model name is an alias, so provider behavior can change unless
  a supported snapshot is selected and recorded.
- Fixed candidates cover the stated boundaries, not every possible model
  output. No committed artifact is presented as a fresh live-model response.
- The deterministic fallback is less natural than generated prose, but it is
  the safer result when any check is uncertain.

The system therefore prefers rejecting an uncertain candidate and preserving
the deterministic alert path over weakening validation to accept more prose.
