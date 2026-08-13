# Optional demo UI walkthrough

The demo UI is an **optional presentation layer**. It does not replace, wrap,
or gate the graded review path. `./run_demo.sh` and the terminal output remain
the required, sufficient evidence. The UI only displays the artifacts that the
required pipeline already wrote, plus one button that reuses the existing
bounded live-AI briefing code.

It adds no dependencies (Python standard library only) and serves on
`127.0.0.1` only.

## Run it

```bash
./run_demo.sh                 # 1. prove the pipeline; creates the artifacts
python -m src.demo_ui         # 2. serve the viewer on http://127.0.0.1:8765
```

Open <http://127.0.0.1:8765>. Stop with `Ctrl-C`.

## What the page shows

Everything on the page is read from disk on load; nothing is recomputed:

- **Run counts** from `outputs/alert.json` (9 consumed, 8 unique, 1 duplicate
  skipped, 2 alerts).
- **Alerts**: both threshold crossings with their UTC windows and rule facts.
- **Metrics table**: every consumed Kafka message from `outputs/metrics.csv`,
  with the two alert rows and the `duplicate_skipped` row highlighted.
- **Briefing**: the current `outputs/briefing.txt`.
- **Evaluation summary** from `evaluation/evaluation.json` (7/7).

If an artifact is missing, the page says so and tells you to run
`./run_demo.sh` first.

## The "Generate Live AI Briefing" button

Clicking the button POSTs to the local server, which calls the same
`src.briefing` code as `python -m src.briefing --use-live-ai`:

1. reads the already-generated `outputs/alert.json`;
2. sends **only the five approved facts** to OpenAI (`gpt-5-nano`, 10-second
   timeout, key from the private local `.env`);
3. validates the response with the same six automatic checks (nonempty,
   sentence limit, risk label, approved numbers, approved timestamps, no
   unsupported details);
4. falls back to the deterministic briefing on a missing key, request failure,
   or rejected response; and
5. displays the final briefing with its provenance badge, "live model
   (validated)" or "deterministic fallback," plus every check result and any
   fallback reason.

The raw model candidate is saved to `evaluation/live_candidate.txt`
(git-ignored) exactly as the CLI does. The AI still cannot trigger, suppress,
or relabel an alert; the button only rewords facts that the deterministic
pipeline already produced.

## Suggested 60-second walkthrough (after the terminal demo)

1. "Everything on this page is the artifacts you just watched
   `./run_demo.sh` creates; nothing is recomputed."
2. Point at the run counts and the highlighted rows: crossing, skipped
   duplicate, no alert spam while elevated, rearm, second crossing.
3. Click **Generate Live AI Briefing**. Narrate: five approved facts out, two
   sentences back, six automatic checks shown on screen.
4. If Wi-Fi or the key is unavailable, the same click shows the deterministic
   fallback with its reason. That failure mode *is* part of the design story.

## Failure story (worth saying out loud)

- **No `.env` / no key** → badge says "deterministic fallback", reason
  `OPENAI_API_KEY is missing`.
- **No network** → fallback with `model request failed: ...`.
- **Model invents a number or adds advice** → validator rejects it, the
  rejection reasons are displayed, and the fallback is used. Nothing is
  silently repaired.
