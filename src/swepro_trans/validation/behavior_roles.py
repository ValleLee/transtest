#!/usr/bin/env python3
"""Verify converted historical F2P roles from per-selector Base replay evidence.

The Converter proposes whether each public behavior is a functional delta or an
existing Base regression. This gate makes that claim executable: it reads the
Base parser output produced by hard replay and checks every emitted selector.
It never infers product semantics from pass/fail alone; semantic review remains
responsible for public-boundary and specification correctness.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from ..conversion_schema import converted_selector_groups, f2p_rows
from ..paths import resolve_task

PASS = "PASSED"
FAIL = "FAILED"


def _normalized_status(value: Any) -> str:
    """Normalize parser vocabulary without weakening executable evidence.

    Repository-native runners use several spellings for the same terminal
    result (for example Go adapters commonly emit PASS/FAIL while pytest
    adapters emit PASSED/FAILED). The role audit reasons about the semantic
    result, not the spelling selected by a language adapter.
    """
    status = str(value or "").strip().upper()
    aliases = {
        "PASS": PASS,
        "PASSED": PASS,
        "OK": PASS,
        "FAIL": FAIL,
        "FAILED": FAIL,
        "FAILURE": FAIL,
    }
    return aliases.get(status, status)


def _load(path: Path) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    # Harbor parsers use both {"tests": [...]} and a top-level list of
    # {"name", "status"} records. Keep the shape intact for normalization.
    return value if isinstance(value, (dict, list)) else None


def _selectors(row: dict[str, Any]) -> list[str]:
    raw = row.get("emitted_tests", [])
    values = raw if isinstance(raw, list) else [raw]
    return [str(value).strip() for value in values if str(value).strip()]


def _replay_output(paths, label: str) -> tuple[Any, str]:
    # Harbor parsers commonly call the same structured result either
    # output.json or parsed_results.json. The schema, not the filename, is the
    # contract consumed by this role gate.
    names = ("output.json", "parsed_results.json", "results.json")
    for name in names:
        direct = paths.hard_replay_root / "docker" / label / name
        payload = _load(direct)
        if payload:
            return payload, str(direct)
    hard = _load(paths.hard_replay_path)
    artifacts = ((hard.get("runs") or {}).get(label) or {}).get("diagnostic_artifacts") or {}
    for name in names:
        raw = artifacts.get(name)
        if not isinstance(raw, str):
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = {}
        if isinstance(value, (dict, list)):
            return value, f"hard_replay.runs.{label}.diagnostic_artifacts.{name}"
    return {}, str(paths.hard_replay_root / "docker" / label / names[0])


_GO_MISSING_MEMBER = re.compile(
    r"(?P<file>[\w./-]+\.go):(?P<line>\d+):\d+:\s+.*?\bundefined\b"
    r".*?\(type .*? has no field or method (?P<symbol>[A-Za-z_]\w*)\)"
)
_GO_FUNC = re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?(?P<name>Test[A-Za-z0-9_]*)\s*\(")


def _missing_public_api_errors(paths, revision: Path, raw_statuses: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Recognize Base compile failures caused by an absent method called by that selector.

    Go emits ERROR for every selector when a package fails to compile. A missing
    method on a public product type can itself be the behavior under test (for
    example, a PR that moves an operation onto a collection type). Count that as
    a Base functional failure only when the compiler location maps to the emitted
    test function and the named method call is present there. Generic build,
    environment, and unrelated compile errors remain ERROR and still fail the role
    audit.
    """
    if not any(status == "ERROR" for status in raw_statuses.values()):
        return {}
    hard = _load(paths.hard_replay_path)
    base_run = (hard.get("runs") or {}).get("base") or {}
    if not isinstance(base_run, dict) or base_run.get("returncode") in (None, 0):
        return {}
    compiler_output = base_run.get("output")
    if not isinstance(compiler_output, str):
        return {}

    test_root = revision / "tests"
    if not test_root.is_dir():
        return {}
    sources = {path.name: path for path in test_root.rglob("*.go") if path.is_file()}
    evidence: dict[str, dict[str, Any]] = {}
    for match in _GO_MISSING_MEMBER.finditer(compiler_output):
        source = sources.get(Path(match.group("file")).name)
        if source is None:
            continue
        try:
            lines = source.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        line_number = int(match.group("line"))
        if not 1 <= line_number <= len(lines):
            continue

        # Find the enclosing top-level test function for the compiler location.
        function_name = None
        function_start = None
        for index in range(line_number - 1, -1, -1):
            function = _GO_FUNC.match(lines[index])
            if function:
                function_name = function.group("name")
                function_start = index
                break
        if function_name is None or function_start is None:
            continue
        function_end = len(lines)
        for index in range(function_start + 1, len(lines)):
            if _GO_FUNC.match(lines[index]):
                function_end = index
                break
        function_body = "\n".join(lines[function_start:function_end])
        symbol = match.group("symbol")
        if not re.search(rf"\.\s*{re.escape(symbol)}\s*\(", function_body):
            continue

        location = f"{source.relative_to(test_root)}:{line_number}"
        for selector, status in raw_statuses.items():
            if status == "ERROR" and selector.split("/", 1)[0] == function_name:
                evidence[selector] = {
                    "kind": "missing_public_method",
                    "symbol": symbol,
                    "source_location": location,
                    "compiler_diagnostic": match.group(0),
                }
    return evidence


def audit(task_root: Path, revision: Path) -> dict[str, Any]:
    paths = resolve_task(task_root)
    revision = revision.resolve()
    revision_rel = str(revision.relative_to(paths.run_root)) if revision.is_relative_to(paths.run_root) else str(revision)
    trace = _load(revision / "conversion_trace.json")
    base_output, base_evidence_source = _replay_output(paths, "base")
    gold_output, gold_evidence_source = _replay_output(paths, "gold")

    def collect(payload: Any) -> tuple[dict[str, str], set[str]]:
        statuses: dict[str, str] = {}
        duplicates: set[str] = set()
        tests = payload if isinstance(payload, list) else payload.get("tests", []) if isinstance(payload, dict) else []
        if isinstance(tests, list):
            for item in tests:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                status = _normalized_status(item.get("status"))
                if not name:
                    continue
                if name in statuses and statuses[name] != status:
                    duplicates.add(name)
                statuses[name] = status
        return statuses, duplicates

    statuses, duplicate_results = collect(base_output)
    gold_statuses, gold_duplicate_results = collect(gold_output)
    missing_api_evidence = _missing_public_api_errors(paths, revision, statuses)
    observed_statuses = dict(statuses)
    for selector in missing_api_evidence:
        observed_statuses[selector] = "MISSING_PUBLIC_API"
    errors: list[str] = []
    if not base_output:
        errors.append("Base replay did not retain a parseable /logs/verifier/output.json")
    if not gold_output:
        errors.append("Gold replay did not retain a parseable /logs/verifier/output.json")
    if duplicate_results:
        errors.append("Base replay contains conflicting duplicate selector results: " + ", ".join(sorted(duplicate_results)[:10]))
    if gold_duplicate_results:
        errors.append("Gold replay contains conflicting duplicate selector results: " + ", ".join(sorted(gold_duplicate_results)[:10]))

    rows_out: list[dict[str, Any]] = []
    selector_claims: dict[str, set[str]] = {}
    counts = {
        "functional_delta": 0,
        "converted_regression": 0,
        "pending_specification": 0,
        "excluded_implementation": 0,
    }
    for row in f2p_rows(trace):
        source = str(row.get("source_f2p", "<unknown>"))
        decision = row.get("decision")
        classification = row.get("behavior_classification")
        base_status = row.get("base_behavior_status")
        emitted = _selectors(row)
        observed = {selector: observed_statuses.get(selector, "MISSING") for selector in emitted}
        raw_observed = {selector: statuses.get(selector, "MISSING") for selector in emitted}
        gold_observed = {selector: gold_statuses.get(selector, "MISSING") for selector in emitted}
        deltas, regressions = converted_selector_groups({"f2p_accounting": [row]})

        if decision == "specification_gap":
            role = "pending_specification"
            counts[role] += 1
        elif decision == "drop":
            role = "excluded_implementation"
            counts[role] += 1
        else:
            role = "mixed" if deltas and regressions else (
                "functional_delta" if deltas else "converted_regression"
            )
            if deltas:
                counts["functional_delta"] += 1
            if regressions:
                counts["converted_regression"] += 1

        if decision in {"rewrite", "merge"}:
            gold_bad = {selector: status for selector, status in gold_observed.items() if status != PASS}
            if gold_bad:
                errors.append(f"{source}: emitted selectors did not all PASS on Gold: {gold_bad}")
            if not emitted:
                errors.append(f"{source}: retained row has no emitted selectors")
            for selector in regressions:
                selector_claims.setdefault(selector, set()).add("already_satisfies")
            for selector in deltas:
                selector_claims.setdefault(selector, set()).add("changed_or_missing")
            regression_bad = {selector: observed.get(selector, "MISSING") for selector in regressions
                              if observed.get(selector) != PASS}
            if regression_bad:
                errors.append(
                    f"{source}: claimed Base-existing regression but selectors did not all PASS: {regression_bad}"
                )
            delta_bad = {selector: observed.get(selector, "MISSING") for selector in deltas
                         if observed.get(selector) not in {FAIL, "MISSING_PUBLIC_API"}}
            if delta_bad:
                errors.append(
                    f"{source}: claimed changed_or_missing but selectors did not all FAIL on Base: {delta_bad}"
                )

        rows_out.append({
            "source_f2p": source,
            "behavior_classification": classification,
            "base_behavior_status": base_status,
            "verification_role": role,
            "delta_selectors": deltas,
            "regression_selectors": regressions,
            "emitted_tests": emitted,
            "base_selector_statuses": observed,
            "base_selector_statuses_raw": raw_observed,
            "gold_selector_statuses": gold_observed,
        })

    for selector, claims in selector_claims.items():
        if len(claims) > 1:
            errors.append(
                f"{selector}: one emitted selector is shared by Base-existing and changed/missing rows; "
                "split the executable scenarios so each role has independent replay evidence"
            )

    disposition = trace.get("task_disposition")
    if disposition == "convertible" and counts["functional_delta"] == 0:
        errors.append("convertible task has no replay-proven functional_delta row")
    if disposition == "non_discriminative" and counts["functional_delta"]:
        errors.append("non_discriminative task contains replay-proven functional_delta rows")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "revision": revision_rel,
        "task_disposition": disposition,
        "base_output_source": base_evidence_source,
        "gold_output_source": gold_evidence_source,
        "role_counts": counts,
        "rows": rows_out,
        "missing_public_api_evidence": missing_api_evidence,
        "errors": errors,
    }
    out = paths.validation_root / "behavior_roles" / "audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--revision", type=Path, required=True)
    args = parser.parse_args(argv)
    result = audit(args.task_root, args.revision)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
