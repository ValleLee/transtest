#!/usr/bin/env python3
"""Restore the original verifier's test space before applying its P2P patch."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

CODE_DIRS = {"tests", "test", "__tests__", "spec", "specs"}
DATA_DIRS = {"testdata", "test_data", "fixtures", "fixture", "mocks", "mock", "__snapshots__"}


def git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def names(*args: str) -> list[str]:
    return [os.fsdecode(x) for x in git(*args).stdout.split(b"\0") if x]


def is_test_code(path: str) -> bool:
    parts = path.split("/")
    parents, base = parts[:-1], parts[-1]
    if any(part in DATA_DIRS for part in parents):
        return False
    return (any(part in CODE_DIRS for part in parents)
            or base == "conftest.py"
            or bool(re.search(r"_test\.(go|py|js|jsx|ts|tsx)$", base))
            or bool(re.search(r"^test_.*\.py$", base))
            or bool(re.search(r"\.(test|spec)\.(js|jsx|ts|tsx)$", base)))


def restore(path: str, tracked: set[str]) -> None:
    if path in tracked:
        git("checkout", "HEAD", "--", path)
    else:
        target = Path(path)
        if target.is_file() or target.is_symlink():
            target.unlink()


def main() -> None:
    patch = sys.argv[1]
    tracked = set(names("ls-files", "-z"))
    untracked = set(names("ls-files", "--others", "--exclude-standard", "-z"))
    modified = set(names("diff", "--name-only", "-z", "HEAD", "--"))
    reset = {p for p in modified | untracked if is_test_code(p)}
    for record in git("apply", "--numstat", "-z", patch).stdout.split(b"\0"):
        if record:
            fields = record.split(b"\t", 2)
            if len(fields) == 3:
                reset.add(os.fsdecode(fields[2]))
    for path in modified:
        if any(part in DATA_DIRS for part in path.split("/")[:-1]):
            reset.add(path)
    for path in sorted(reset):
        restore(path, tracked)
    print(f"__TEST_SPACE_RESET__ {len(reset)}", flush=True)


if __name__ == "__main__":
    main()
