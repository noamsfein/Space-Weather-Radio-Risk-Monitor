"""Optional local demo UI: view the generated artifacts in a browser.

This is an optional presentation layer on top of the required pipeline. It
never replaces or gates the graded review path (``./run_demo.sh``): it only
reads the artifacts that path already wrote, and its one action button reuses
``src.briefing`` — the same bounded facts, validator, and deterministic
fallback as the CLI. It serves on 127.0.0.1 only, uses only the standard
library, and contacts OpenAI only when the button is clicked and a key exists.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Callable, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from src.alert_output import DEFAULT_ALERT_PATH
from src.briefing import (
    BriefingError,
    BriefingGeneration,
    DEFAULT_BRIEFING_PATH,
    write_briefing,
)
from src.evaluate import DEFAULT_EVALUATION_PATH
from src.metrics_output import DEFAULT_METRICS_PATH

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_LIVE_CANDIDATE_PATH = Path("evaluation/live_candidate.txt")
RUN_DEMO_HINT = "Artifact not found; run ./run_demo.sh first."


def read_artifacts(
    alert_path: str | Path = DEFAULT_ALERT_PATH,
    metrics_path: str | Path = DEFAULT_METRICS_PATH,
    briefing_path: str | Path = DEFAULT_BRIEFING_PATH,
    evaluation_path: str | Path = DEFAULT_EVALUATION_PATH,
) -> dict:
    """Assemble every artifact the page shows; missing files become hints."""

    payload: dict = {
        "alert": None,
        "metrics": None,
        "briefing": None,
        "evaluation_summary": None,
        "hints": [],
    }

    alert_file = Path(alert_path)
    if alert_file.exists():
        payload["alert"] = json.loads(alert_file.read_text(encoding="utf-8"))
    else:
        payload["hints"].append(f"{alert_file}: {RUN_DEMO_HINT}")

    metrics_file = Path(metrics_path)
    if metrics_file.exists():
        with metrics_file.open(encoding="utf-8", newline="") as handle:
            payload["metrics"] = list(csv.DictReader(handle))
    else:
        payload["hints"].append(f"{metrics_file}: {RUN_DEMO_HINT}")

    briefing_file = Path(briefing_path)
    if briefing_file.exists():
        payload["briefing"] = briefing_file.read_text(encoding="utf-8").strip()
    else:
        payload["hints"].append(f"{briefing_file}: {RUN_DEMO_HINT}")

    evaluation_file = Path(evaluation_path)
    if evaluation_file.exists():
        evaluation = json.loads(evaluation_file.read_text(encoding="utf-8"))
        payload["evaluation_summary"] = evaluation.get("summary")
    else:
        payload["hints"].append(f"{evaluation_file}: {RUN_DEMO_HINT}")

    return payload


def _serialize_generation(generation: BriefingGeneration) -> dict:
    validation = None
    if generation.validation is not None:
        validation = {
            "accepted": generation.validation.accepted,
            "rejection_reasons": list(generation.validation.rejection_reasons),
            "checks": [
                {"name": check.name, "passed": check.passed, "detail": check.detail}
                for check in generation.validation.checks
            ],
        }
    return {
        "briefing": generation.text,
        "source": generation.source,
        "model": generation.model,
        "fallback_reason": generation.fallback_reason,
        "validation": validation,
    }


def run_live_briefing(
    alert_path: str | Path = DEFAULT_ALERT_PATH,
    output_path: str | Path = DEFAULT_BRIEFING_PATH,
    candidate_path: str | Path = DEFAULT_LIVE_CANDIDATE_PATH,
    live_writer: Callable[..., str] = write_briefing,
) -> dict:
    """Run the existing bounded live-briefing path and describe the outcome.

    The heavy lifting stays in ``src.briefing.write_briefing``: approved facts
    only, validation, deterministic fallback, and an atomic file write.
    """

    generation: BriefingGeneration | None = None

    def capture(value: BriefingGeneration) -> None:
        nonlocal generation
        generation = value

    live_writer(
        alert_path,
        output_path,
        use_live_ai=True,
        candidate_path=candidate_path,
        generation_callback=capture,
    )
    if generation is None:
        raise BriefingError("briefing generation reported no provenance")
    return _serialize_generation(generation)


PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Space Weather Radio-Risk Monitor — Demo UI</title>
<style>
  * { box-sizing: border-box; }
  body {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    margin: 0; background: #fbfaf7; color: #1c1c1c;
  }
  header {
    background: #14324f; color: #fff; padding: 18px 28px;
  }
  header h1 { margin: 0; font-size: 22px; }
  header p { margin: 6px 0 0; color: #b9c8d8; font-size: 13px; }
  main { max-width: 980px; margin: 0 auto; padding: 20px 28px 60px; }
  section { margin: 26px 0; }
  h2 { font-size: 16px; color: #14324f; border-bottom: 2px solid #e2ddd2; padding-bottom: 6px; }
  .chips { display: flex; gap: 10px; flex-wrap: wrap; }
  .chip {
    background: #fff; border: 1px solid #d5cfc2; border-radius: 10px;
    padding: 10px 16px; text-align: center; min-width: 110px;
  }
  .chip b { display: block; font-size: 22px; color: #14324f; }
  .chip span { font-size: 12px; color: #666; }
  .card {
    background: #fff; border: 1px solid #d5cfc2; border-left: 6px solid #b3402e;
    border-radius: 8px; padding: 12px 16px; margin: 10px 0; font-size: 14px;
  }
  .card b { color: #b3402e; }
  table { border-collapse: collapse; width: 100%; font-size: 13px; background: #fff; }
  th, td { border: 1px solid #d5cfc2; padding: 6px 9px; text-align: left; }
  th { background: #ece8e0; }
  tr.alert-row { background: #e4f4e4; font-weight: 700; }
  tr.dup-row { background: #fdf3dd; }
  .briefing {
    background: #14181d; color: #ffb454; border-radius: 8px;
    padding: 14px 18px; font-size: 15px; line-height: 1.5;
  }
  .badge {
    display: inline-block; border-radius: 99px; padding: 2px 12px;
    font-size: 12px; font-weight: 700; margin-left: 8px; vertical-align: middle;
  }
  .badge.fallback { background: #ece8e0; color: #555; }
  .badge.model { background: #dcecdc; color: #1e6329; }
  button {
    background: #14324f; color: #fff; border: 0; border-radius: 8px;
    padding: 12px 22px; font-size: 15px; cursor: pointer;
  }
  button:disabled { opacity: 0.5; cursor: wait; }
  .muted { color: #777; font-size: 13px; }
  ul.checks { list-style: none; padding: 0; font-size: 13px; }
  ul.checks li::before { content: "✓ "; color: #1e6329; }
  ul.checks li.failed::before { content: "✗ "; color: #b3402e; }
  .note {
    background: #fdf8f1; border: 1px dashed #a05a2c; border-radius: 8px;
    padding: 10px 14px; font-size: 13px; color: #6d4a2f;
  }
</style>
</head>
<body>
<header>
  <h1>Space Weather Radio-Risk Monitor — Demo UI</h1>
  <p>Optional presentation layer. It only displays what the required pipeline
  (<code>./run_demo.sh</code>: replay → Kafka → rolling window → artifacts) already produced.</p>
</header>
<main>
  <div class="note">The graded review path is the terminal command, not this page.
  Every number below comes from <code>outputs/</code> and <code>evaluation/</code>.</div>

  <section id="counts-section">
    <h2>Run counts (outputs/alert.json)</h2>
    <div class="chips" id="counts"></div>
  </section>

  <section>
    <h2>Alerts</h2>
    <div id="alerts"></div>
  </section>

  <section>
    <h2>Every consumed Kafka message (outputs/metrics.csv)</h2>
    <div id="metrics"></div>
  </section>

  <section>
    <h2>Briefing (outputs/briefing.txt) <span id="briefing-badge"></span></h2>
    <div class="briefing" id="briefing">—</div>
    <p style="margin-top:14px">
      <button id="live-button">Generate Live AI Briefing</button>
      <span class="muted">Sends only the five approved alert facts to OpenAI, validates the
      response, and falls back to the deterministic briefing if needed.</span>
    </p>
    <div id="live-result"></div>
  </section>

  <section>
    <h2>Evaluation (evaluation/evaluation.json)</h2>
    <div class="chips" id="evaluation"></div>
  </section>

  <section id="hints-section" hidden>
    <h2>Missing artifacts</h2>
    <div id="hints" class="note"></div>
  </section>
</main>
<script>
function chip(value, label) {
  return `<div class="chip"><b>${value}</b><span>${label}</span></div>`;
}

function renderArtifacts(data) {
  const counts = document.getElementById("counts");
  const alerts = document.getElementById("alerts");
  const metrics = document.getElementById("metrics");
  const briefing = document.getElementById("briefing");
  const badge = document.getElementById("briefing-badge");
  const evaluation = document.getElementById("evaluation");

  if (data.alert) {
    const c = data.alert.run_counts;
    counts.innerHTML =
      chip(c.messages_consumed, "messages consumed") +
      chip(c.unique_events, "unique events") +
      chip(c.duplicates_skipped, "duplicates skipped") +
      chip(c.late_events_skipped, "late skipped") +
      chip(c.alerts_emitted, "alerts emitted");
    alerts.innerHTML = data.alert.alerts.map(a =>
      `<div class="card"><b>${a.alert_id}</b> — rolling 15-min max Kp
       <b>${a.rolling_15m_max_kp}</b> at ${a.triggered_at}
       (window ${a.window_start_utc} → ${a.window_end_utc},
       threshold ${a.threshold_kp}, label ${a.risk_label})</div>`).join("")
      || "<p class='muted'>No alerts in the latest run.</p>";
  }

  if (data.metrics) {
    const header = Object.keys(data.metrics[0] || {});
    metrics.innerHTML = "<table><tr>" +
      header.map(h => `<th>${h}</th>`).join("") + "</tr>" +
      data.metrics.map(row => {
        const cls = row.alert_emitted === "true" ? "alert-row"
          : row.processing_status === "duplicate_skipped" ? "dup-row" : "";
        return `<tr class="${cls}">` +
          header.map(h => `<td>${row[h]}</td>`).join("") + "</tr>";
      }).join("") + "</table>";
  }

  if (data.briefing) {
    briefing.textContent = data.briefing;
    badge.innerHTML = '<span class="badge fallback">from file</span>';
  }

  if (data.evaluation_summary) {
    const s = data.evaluation_summary;
    evaluation.innerHTML =
      chip(`${s.assertions_passed}/${s.total_assertions}`, "assertions passed") +
      chip(`${s.ai_cases_passed}/${s.ai_cases_total}`, "AI cases as expected") +
      chip(s.overall_passed ? "PASS" : "FAIL", "overall");
  }

  if (data.hints && data.hints.length) {
    document.getElementById("hints-section").hidden = false;
    document.getElementById("hints").textContent = data.hints.join(" · ");
  }
}

async function loadArtifacts() {
  const response = await fetch("/api/artifacts");
  renderArtifacts(await response.json());
}

document.getElementById("live-button").addEventListener("click", async () => {
  const button = document.getElementById("live-button");
  const result = document.getElementById("live-result");
  button.disabled = true;
  result.innerHTML = "<p class='muted'>Requesting briefing…</p>";
  try {
    const response = await fetch("/api/live-briefing", {method: "POST"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || response.statusText);
    document.getElementById("briefing").textContent = data.briefing;
    document.getElementById("briefing-badge").innerHTML =
      `<span class="badge ${data.source}">${data.source === "model"
        ? "live model (validated)" : "deterministic fallback"}</span>`;
    let html = "";
    if (data.fallback_reason) {
      html += `<p class="muted">Fallback reason: ${data.fallback_reason}</p>`;
    }
    if (data.validation) {
      html += "<ul class='checks'>" + data.validation.checks.map(c =>
        `<li class="${c.passed ? "" : "failed"}">${c.name}: ${c.detail}</li>`
      ).join("") + "</ul>";
    }
    result.innerHTML = html;
  } catch (error) {
    result.innerHTML = `<div class="card">Live briefing failed: ${error.message}</div>`;
  } finally {
    button.disabled = false;
  }
});

loadArtifacts();
</script>
</body>
</html>
"""


class DemoUIHandler(BaseHTTPRequestHandler):
    """Three routes: the page, the artifact JSON, and the live-AI action."""

    # Injection points so tests never bind a socket or call OpenAI.
    artifacts_reader: Callable[[], dict] = staticmethod(read_artifacts)
    live_briefing_runner: Callable[[], dict] = staticmethod(run_live_briefing)

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

    def do_GET(self) -> None:  # noqa: N802 - http.server naming
        if self.path == "/":
            self._send(200, PAGE_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/artifacts":
            try:
                self._send_json(200, type(self).artifacts_reader())
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self._send_json(500, {"error": str(exc)})
        else:
            self._send_json(404, {"error": "unknown path"})

    def do_POST(self) -> None:  # noqa: N802 - http.server naming
        if self.path == "/api/live-briefing":
            try:
                self._send_json(200, type(self).live_briefing_runner())
            except (BriefingError, OSError, ValueError) as exc:
                self._send_json(409, {"error": str(exc)})
        else:
            self._send_json(404, {"error": "unknown path"})

    def log_message(self, format: str, *args: object) -> None:
        print(f"demo-ui: {format % args}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Optional local viewer for the generated demo artifacts."
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    server = ThreadingHTTPServer((DEFAULT_HOST, args.port), DemoUIHandler)
    print(f"Demo UI on http://{DEFAULT_HOST}:{args.port} (Ctrl-C to stop)")
    print("Optional layer only; the graded review path remains ./run_demo.sh")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
