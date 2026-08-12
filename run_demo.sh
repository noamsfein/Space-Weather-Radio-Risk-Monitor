#!/usr/bin/env bash
# One-command reproducible demo for the Space Weather Radio-Risk Monitor.
#
# Resets the local Kafka broker, replays the nine-message deterministic
# fixture through the real producer and consumer, writes the four required
# artifacts (alert.json, metrics.csv, briefing.txt, evaluation.json),
# verifies them against data/fixtures/replay_expected.json, and runs the
# automated test suite. Exits nonzero on any failure.
#
# Requires: Docker Desktop running, docker compose v2, and the project
# Python environment (pip install -r requirements.txt). No network access
# beyond localhost and no OpenAI key are required.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="$(command -v python3)"
fi

ALERT_PATH="outputs/alert.json"
METRICS_PATH="outputs/metrics.csv"
BRIEFING_PATH="outputs/briefing.txt"
EVALUATION_PATH="evaluation/evaluation.json"
EXPECTED_PATH="data/fixtures/replay_expected.json"

LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/space-weather-demo.XXXXXX")"
CONSUMER_LOG="$LOG_DIR/stream_processor.log"
CONSUMER_PID=""

cleanup() {
  if [ -n "$CONSUMER_PID" ] && kill -0 "$CONSUMER_PID" 2>/dev/null; then
    kill "$CONSUMER_PID" 2>/dev/null || true
    wait "$CONSUMER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

fail() {
  echo "DEMO FAILED: $1" >&2
  if [ -s "$CONSUMER_LOG" ]; then
    echo "--- consumer log ($CONSUMER_LOG) ---" >&2
    cat "$CONSUMER_LOG" >&2
  fi
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "docker is not installed or not on PATH"
docker info >/dev/null 2>&1 || fail "Docker is not running; open Docker Desktop first"
docker compose version >/dev/null 2>&1 || fail "docker compose v2 is required"
"$PYTHON" -c "import confluent_kafka, pydantic" 2>/dev/null \
  || fail "Python dependencies missing; run: pip install -r requirements.txt"

echo "==> Resetting the local Kafka broker (a fresh broker prevents stale topics and offsets)"
docker compose down -v --remove-orphans >/dev/null 2>&1 || true
docker compose up -d --wait kafka || fail "Kafka broker did not become healthy"

echo "==> Clearing generated demo artifacts"
rm -f "$ALERT_PATH" "$METRICS_PATH" "$BRIEFING_PATH" "$EVALUATION_PATH"

echo "==> Starting the finite Kafka consumer in the background (log: $CONSUMER_LOG)"
"$PYTHON" -m src.stream_processor >"$CONSUMER_LOG" 2>&1 &
CONSUMER_PID=$!

echo "==> Publishing the nine-message deterministic replay through Kafka"
"$PYTHON" -m src.replay_producer || fail "replay producer failed"

echo "==> Waiting for the consumer to finish"
if ! wait "$CONSUMER_PID"; then
  CONSUMER_PID=""
  fail "stream processor exited nonzero"
fi
CONSUMER_PID=""
cat "$CONSUMER_LOG"

echo "==> Writing the deterministic briefing (no API key or network required)"
"$PYTHON" -m src.briefing || fail "briefing failed"

echo "==> Writing deterministic evaluation evidence"
"$PYTHON" -m src.evaluate || fail "evaluation failed"

echo "==> Verifying artifacts against $EXPECTED_PATH"
"$PYTHON" - "$EXPECTED_PATH" "$ALERT_PATH" "$METRICS_PATH" "$BRIEFING_PATH" "$EVALUATION_PATH" <<'PYCHECK' \
  || fail "artifact acceptance check failed"
import csv
import json
import sys

expected_path, alert_path, metrics_path, briefing_path, evaluation_path = sys.argv[1:6]
problems = []

with open(expected_path, encoding="utf-8") as handle:
    expected = json.load(handle)

with open(alert_path, encoding="utf-8") as handle:
    alert = json.load(handle)
if alert["run_counts"] != expected["expected_counts"]:
    problems.append(
        f"run_counts {alert['run_counts']} != expected {expected['expected_counts']}"
    )
actual_alerts = alert["alerts"]
expected_alerts = expected["expected_alerts"]
if len(actual_alerts) != len(expected_alerts):
    problems.append(f"{len(actual_alerts)} alert(s), expected {len(expected_alerts)}")
else:
    for position, (actual, wanted) in enumerate(zip(actual_alerts, expected_alerts), 1):
        for field in ("triggered_at", "latest_kp", "rolling_15m_max_kp"):
            if actual[field] != wanted[field]:
                problems.append(
                    f"alert {position} {field}={actual[field]!r}, expected {wanted[field]!r}"
                )

with open(metrics_path, encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
expected_rows = expected["expected_metrics"]
if len(rows) != len(expected_rows):
    problems.append(f"{len(rows)} metrics row(s), expected {len(expected_rows)}")
else:
    for position, (row, wanted) in enumerate(zip(rows, expected_rows), 1):
        actual_row = {
            "time_tag": row["time_tag"],
            "kp_value": float(row["kp_value"]),
            "rolling_15m_max_kp": float(row["rolling_15m_max_kp"]),
            "risk_label": row["risk_label"],
            "alert_emitted": row["alert_emitted"] == "true",
            "processing_status": row["processing_status"],
        }
        if actual_row != wanted:
            problems.append(f"metrics row {position}: {actual_row} != {wanted}")

with open(briefing_path, encoding="utf-8") as handle:
    briefing = handle.read().strip()
if not briefing:
    problems.append("briefing.txt is empty")

with open(evaluation_path, encoding="utf-8") as handle:
    evaluation = json.load(handle)
summary = evaluation["summary"]
if summary.get("overall_passed") is not True:
    problems.append(f"evaluation did not pass: {summary}")

if problems:
    print("Artifact acceptance problems:")
    for problem in problems:
        print(f"  - {problem}")
    raise SystemExit(1)
print(
    f"Artifacts match the labeled fixture: {len(actual_alerts)} alert(s), "
    f"{len(rows)} metrics row(s), briefing present, evaluation "
    f"{summary['assertions_passed']}/{summary['total_assertions']} assertions passed."
)
PYCHECK

echo "==> Running the automated test suite"
"$PYTHON" -m pytest -q || fail "test suite failed"

echo
echo "Demo complete. Artifacts:"
echo "  $ALERT_PATH"
echo "  $METRICS_PATH"
echo "  $BRIEFING_PATH"
echo "  $EVALUATION_PATH"
echo "Expected results fixture: $EXPECTED_PATH"
echo "Consumer log: $CONSUMER_LOG"
