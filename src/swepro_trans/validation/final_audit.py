"""Audit published Harbor-to-Harbor conversions without changing them.

The conversion pipeline is strict for new revisions.  This command exists for
batch review of already published runs: it checks the canonical layout,
F2P coverage, instruction leakage, recorded gates, and whether the revision
uses the current accounting schema.  Legacy artifacts are reported explicitly
rather than silently treated as current artifacts.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

from ..conversion_schema import (
    REQUIRED_F2P_FIELDS, classification_errors, converted_selector_groups, canonical_retained_p2p, append_f2p_regressions,
    replay_expectation, trace_disposition_errors,
)
from ..paths import PROJECT_ROOT, latest_attempt, resolve_task
from ..layout import build_final_instruction
from .binding_signals import revision_evidence_fingerprint
from .revision import _selector_is_emitted


_LEAK_PATTERNS = (
    re.compile(r"^\s*##\s*Behavior from\b", re.I | re.M),
    re.compile(r"^\s*##\s*(?:Requirements|New Interfaces|Interface)\s*$", re.I | re.M),
    re.compile(r"reference implementation", re.I),
    re.compile(r"Gold[- ]only", re.I),
    re.compile(r"gold[_ -]patch", re.I),
    re.compile(r"(?:^|\s)tests?/[^\s]+::[^\s]+"),
)


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (OSError, json.JSONDecodeError):
        return None


def _f2p_selectors(original: Path) -> list[str]:
    cfg = _load(original / "tests" / "config.json") or {}
    raw = cfg.get("fail_to_pass", [])
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        for parser in (json.loads, ast.literal_eval):
            try:
                value = parser(raw)
                if isinstance(value, (list, tuple)):
                    return [str(x) for x in value]
            except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
                continue
    return []


def _selector_list(config: dict[str, Any], *keys: str) -> list[str]:
    raw: Any = []
    for key in keys:
        if key in config:
            raw = config[key]
            break
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        for parser in (json.loads, ast.literal_eval):
            try:
                value = parser(raw)
                if isinstance(value, (list, tuple)):
                    return [str(x) for x in value]
            except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
                continue
    return []


def _revision_for(attempt: Path) -> Path | None:
    revisions_root = attempt / "intermediate" / "converter" / "revisions"
    # Acceptance/state is authoritative.  A later exploratory revision may
    # exist after the accepted one and must never replace the published
    # artifact during an audit.
    for record_path in (attempt / "intermediate" / "validation" / "acceptance.json", attempt / "intermediate" / "control" / "state.json"):
        record = _load(record_path)
        if isinstance(record, dict):
            value = record.get("revision") or record.get("accepted_revision")
            if value:
                value_path = Path(str(value))
                if value_path.is_absolute():
                    candidate = value_path
                elif str(value_path).startswith("attempts/"):
                    candidate = attempt.parent.parent / value_path
                else:
                    candidate = attempt / value_path
                if candidate.is_dir():
                    return candidate
    revisions = [p for p in revisions_root.glob("rev_*") if p.is_dir() and (p / "conversion_trace.json").is_file()]
    if revisions:
        def key(path: Path) -> tuple[int, str]:
            try:
                return (int(path.name.removeprefix("rev_")), path.name)
            except ValueError:
                return (-1, path.name)
        return max(revisions, key=key)
    return None


def audit_task(task_root: Path, *, allow_legacy: bool = False) -> dict[str, Any]:
    paths = resolve_task(task_root)
    attempt = latest_attempt(paths.run_root)
    if attempt is None:
        return {"status": "FAIL", "instance_id": paths.instance_id, "errors": ["no attempt directory"]}
    revision = _revision_for(attempt)
    final = attempt / "final"
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    state = _load(attempt / "intermediate" / "control" / "state.json") or {}
    independent = _load(attempt / "review" / "independent_audit.json") or {}
    checks["attempt_status"] = state.get("status", "missing")
    checks["independent_audit"] = independent.get("status", "not_run")
    if state.get("status") != "accepted":
        errors.append("latest attempt is not certified accepted")
    if independent.get("status") == "FAIL":
        errors.append("independent audit rejected this published revision")

    required_final = (final / "instruction.md", final / "task.toml", final / "tests" / "test.sh")
    missing_final = [str(p.relative_to(attempt)) for p in required_final if not p.is_file()]
    checks["final_artifact"] = "PASS" if not missing_final else "FAIL"
    if missing_final:
        errors.append("missing final artifacts: " + ", ".join(missing_final))

    selectors = _f2p_selectors(paths.original)
    checks["source_f2p_count"] = len(selectors)
    trace = _load(revision / "conversion_trace.json") if revision else None
    rows = trace.get("f2p_accounting", []) if isinstance(trace, dict) else []
    rows = [r for r in rows if isinstance(r, dict)]
    accounted = [str(r.get("source_f2p")) for r in rows]
    missing = sorted(set(selectors) - set(accounted))
    extra = sorted(set(accounted) - set(selectors))
    duplicate = sorted({x for x in accounted if accounted.count(x) > 1})
    checks["f2p_accounting"] = {
        "source": len(selectors), "accounted": len(rows),
        "missing": missing, "extra": extra, "duplicates": duplicate,
    }
    if missing or extra or duplicate:
        errors.append("F2P accounting does not match canonical source selectors")

    current_schema = bool(rows) and all(REQUIRED_F2P_FIELDS.issubset(row) for row in rows)
    checks["conversion_schema"] = "current" if current_schema else "legacy"
    if not current_schema:
        message = "revision uses legacy F2P rows; recorded evidence can be inspected but this is not a current-schema conversion"
        warnings.append(message)
        if not allow_legacy:
            errors.append(message)
    else:
        row_errors = [err for row in rows for err in classification_errors(row)]
        checks["classification"] = "PASS" if not row_errors else {"status": "FAIL", "errors": row_errors}
        if row_errors:
            errors.append("current-schema F2P classification errors")
        disposition_errors = trace_disposition_errors(trace)
        checks["task_disposition"] = {
            "value": trace.get("task_disposition"),
            "errors": disposition_errors,
        }
        if disposition_errors:
            errors.append("task disposition/P2P accounting is invalid")
        if trace.get("task_disposition") != "convertible":
            errors.append("only convertible tasks may have a published final artifact")

        candidate_config = _load(revision / "tests" / "config.json") if revision else {}
        candidate_config = candidate_config if isinstance(candidate_config, dict) else {}
        candidate_f2p = _selector_list(candidate_config, "fail_to_pass")
        delta_selectors, regression_selectors = converted_selector_groups(trace)
        checks["functional_selector_provenance"] = {
            "config_count": len(candidate_f2p), "trace_count": len(delta_selectors),
            "config_only": sorted(set(candidate_f2p) - set(delta_selectors)),
            "trace_only": sorted(set(delta_selectors) - set(candidate_f2p)),
        }
        if set(candidate_f2p) != set(delta_selectors):
            errors.append("functional-delta config selectors and trace roles differ")

        original_config = _load(paths.original / "tests" / "config.json") or {}
        original_p2p = _selector_list(original_config, "pass_to_pass", "pass_to_pass_tests")
        candidate_p2p = _selector_list(candidate_config, "pass_to_pass", "pass_to_pass_tests")
        p2p_accounting = trace.get("p2p_accounting", {})
        excluded_items = p2p_accounting.get("excluded", []) if isinstance(p2p_accounting, dict) else []
        excluded = [str(item.get("selector")) for item in excluded_items if isinstance(item, dict)]
        retained_native_p2p, mapping_errors = canonical_retained_p2p(original_p2p, p2p_accounting)
        errors.extend(mapping_errors)
        expected_p2p = append_f2p_regressions(retained_native_p2p, regression_selectors)
        checks["p2p_policy"] = {
            "original": len(original_p2p), "retained": len(candidate_p2p),
            "excluded": len(excluded), "converted_regressions": len(regression_selectors),
        }
        if candidate_p2p != expected_p2p:
            errors.append("published P2P must preserve the original list verbatim, then append only converted F2P regressions")

        test_root = revision / "tests" if revision else None
        test_text = ""
        if test_root and test_root.is_dir():
            test_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in test_root.rglob("*") if path.is_file())
        if (test_root and (test_root / "test_patch.patch").exists()) or "test_patch.patch" in test_text or "historical_tests/test_patch" in test_text:
            errors.append("published verifier depends on historical test_patch.patch")
        gaps = [str(row.get("source_f2p")) for row in rows if row.get("decision") == "specification_gap"]
        if gaps:
            errors.append("unresolved specification_gap rows: " + ", ".join(gaps[:10]))
        emitted_missing = [str(row.get("source_f2p")) for row in rows if row.get("decision") in {"rewrite", "merge"} and not row.get("emitted_tests")]
        if emitted_missing:
            errors.append("rewrite/merge rows without emitted tests: " + ", ".join(emitted_missing[:10]))
        emitted_test_sources = []
        if revision:
            tests_root = revision / "tests"
            for row in rows:
                if row.get("decision") not in {"rewrite", "merge"}:
                    continue
                raw = row.get("emitted_tests", [])
                selectors_for_row = raw if isinstance(raw, list) else [raw]
                for selector in selectors_for_row:
                    selector = str(selector).strip()
                    if selector and not _selector_is_emitted(selector, tests_root):
                        emitted_test_sources.append({
                            "source_f2p": row.get("source_f2p"),
                            "selector": selector,
                        })
        checks["emitted_test_sources"] = {
            "status": "PASS" if not emitted_test_sources else "FAIL",
            "missing": emitted_test_sources,
        }
        if emitted_test_sources:
            errors.append("F2P accounting references selectors without emitted test source")

    instruction = ""
    instruction_path = final / "instruction.md"
    if instruction_path.is_file():
        instruction = instruction_path.read_text(encoding="utf-8", errors="replace")
    leakage = [pattern.pattern for pattern in _LEAK_PATTERNS if pattern.search(instruction)]
    checks["instruction_leakage"] = "PASS" if not leakage else {"status": "FAIL", "patterns": leakage}
    if leakage:
        errors.append("final instruction contains test/reference implementation leakage")
    problem_path = paths.source / "problem_statement.md"
    if problem_path.is_file() and instruction_path.is_file():
        expected_instruction = build_final_instruction(problem_path, paths.specification_addendum_path)
        matches_p_only_source = instruction == expected_instruction
        checks["instruction_matches_p_only_source"] = "PASS" if matches_p_only_source else "FAIL"
        if not matches_p_only_source:
            errors.append("final instruction differs from P-only source plus audited addendum")
    else:
        checks["instruction_matches_p_only_source"] = "HOLD"
        errors.append("cannot verify final instruction against missing P-only source")

    acceptance = _load(attempt / "intermediate" / "validation" / "acceptance.json") or {}
    checks["recorded_acceptance"] = acceptance.get("status", "missing")
    if acceptance.get("status") != "accepted":
        errors.append("recorded acceptance is not accepted")

    hard = _load(attempt / "intermediate" / "validation" / "hard_replay" / "result.json")
    if isinstance(hard, dict) and isinstance(trace, dict):
        expected = replay_expectation(trace)
        actual = hard.get("expectation")
        checks["replay_expectation"] = {"expected_from_trace": expected, "recorded": actual}
        if actual != expected:
            errors.append(f"hard replay expectation {actual!r} does not match conversion trace {expected!r}")
        runs = hard.get("runs")
        if not isinstance(runs, dict) or not isinstance(runs.get("base"), dict) or not isinstance(runs.get("gold"), dict):
            errors.append("hard replay lacks separate Base and Gold execution records")

    qa_values: dict[str, Any] = {}
    for name, rel in {
        "semantic": "intermediate/validation/semantic/review.json",
        "hard_replay": "intermediate/validation/hard_replay/result.json",
        "behavior_role_audit": "intermediate/validation/behavior_roles/audit.json",
        "stability": "intermediate/validation/stability/result.json",
        "positive_qa": "intermediate/qa/positive/summary.json",
        "negative_qa": "intermediate/qa/negative/summary.json",
    }.items():
        value = _load(attempt / rel)
        qa_values[name] = value
        status = value.get("verdict" if name == "semantic" else "status") if isinstance(value, dict) else None
        checks[name] = status or "missing"
        expected = "PASS" if name in {"semantic", "behavior_role_audit"} else "pass"
        if status != expected:
            errors.append(f"{name} gate is {status or 'missing'}")

    semantic_review = qa_values.get("semantic") or {}
    recorded_fingerprint = semantic_review.get("verifier_evidence_fingerprint") if isinstance(semantic_review, dict) else None
    if recorded_fingerprint and revision:
        current_fingerprint = revision_evidence_fingerprint(revision / "tests")
        checks["semantic_evidence_current"] = recorded_fingerprint == current_fingerprint
        if recorded_fingerprint != current_fingerprint:
            errors.append("semantic review predates current verifier files or binding-signal rules")
    elif not recorded_fingerprint:
        checks["semantic_evidence_current"] = "legacy_unversioned"
        warnings.append("semantic review predates verifier evidence fingerprint contract")

    positive = qa_values.get("positive_qa")
    if isinstance(positive, dict) and positive.get("status") == "pass":
        if positive.get("mode") == "base_is_positive_reference":
            errors.append("Base may not substitute for an independent Positive QA implementation")
        else:
            valid = [item for item in positive.get("attempts", []) if isinstance(item, dict) and item.get("judge_verdict") == "VALID" and item.get("replay_status") == "pass" and item.get("functional_pass") is True]
            if not valid:
                errors.append("positive QA lacks a judged, replayed, functionally passing candidate")
    negative = qa_values.get("negative_qa")
    if isinstance(negative, dict) and negative.get("status") == "pass":
        rejected = [item for item in negative.get("attempts", []) if isinstance(item, dict) and item.get("judge_verdict") and item.get("replay_status") == "pass" and item.get("functional_pass") is False]
        if not rejected:
            errors.append("negative QA lacks a judged, replayed, functionally rejected candidate")

    status = "PASS" if not errors else "FAIL"
    return {
        "status": status,
        "instance_id": paths.instance_id,
        "run_root": str(paths.run_root),
        "attempt": str(attempt.relative_to(paths.run_root)),
        "revision": str(revision.relative_to(paths.run_root)) if revision else None,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


def _run_root_candidates() -> list[Path]:
    root = PROJECT_ROOT / "runs"
    return sorted(path for path in root.iterdir() if path.is_dir() and (path / "latest_attempt.json").is_file()) if root.is_dir() else []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--task-root", type=Path)
    group.add_argument("--all-runs", action="store_true")
    parser.add_argument("--write", action="store_true", help="write review/final_audit.json under each run")
    parser.add_argument("--allow-legacy", action="store_true", help="report legacy accepted artifacts as compatible evidence instead of failing the current-schema gate")
    args = parser.parse_args(argv)
    roots = [args.task_root] if args.task_root else _run_root_candidates()
    results = []
    for root in roots:
        result = audit_task(root, allow_legacy=args.allow_legacy)
        results.append(result)
        if args.write and result.get("run_root") and result.get("attempt"):
            out = Path(result["run_root"]) / result["attempt"] / "review" / "final_audit.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload: Any = results[0] if len(results) == 1 else {"status": "PASS" if all(r.get("status") == "PASS" for r in results) else "FAIL", "results": results}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if (payload.get("status") == "PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
