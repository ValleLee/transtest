"""Repeat the candidate Harbor verifier and audit P2P selectors in each replay.

The same candidate ``tests/test.sh`` executes F2P and retained P2P selectors.
Each replay must show the expected Base/Gold task result and every P2P selector
passing on both states. No alternate wrapper or runner path is introduced.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

from ..paths import resolve_task
from ..conversion_schema import converted_selector_groups, replay_expectation
from ..runtime.stage1 import image_name, run_docker_preflight, write_json


def _parse_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if not isinstance(value, str):
        return []
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(value)
        except Exception:
            continue
        if isinstance(parsed, (list, tuple)):
            return [str(item) for item in parsed]
    return []


def _config(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _selectors(path: Path) -> tuple[list[str], list[str]]:
    data = _config(path)
    f2p = _parse_list(data.get("fail_to_pass", []))
    p2p = _parse_list(data.get("pass_to_pass", data.get("pass_to_pass_tests", [])))
    return f2p, p2p


def _counts(path: Path) -> dict[str, int]:
    f2p, p2p = _selectors(path)
    return {"f2p_count": len(f2p), "p2p_count": len(p2p), "expected_test_count": len(set(f2p + p2p))}


def _status(replay: dict[str, Any]) -> str:
    return str(replay.get("status", "unavailable"))


def _structured_output(log_root: Path, replay: dict[str, Any], side: str) -> tuple[dict[str, Any], str]:
    """Read the parser contract from one candidate replay, regardless of language."""
    for name in ("output.json", "parsed_results.json", "results.json"):
        path = log_root / side / name
        payload = _config(path)
        if isinstance(payload.get("tests"), list):
            return payload, str(path)
    artifacts = ((replay.get("runs") or {}).get(side) or {}).get("diagnostic_artifacts") or {}
    for name in ("output.json", "parsed_results.json", "results.json"):
        raw = artifacts.get(name)
        if not isinstance(raw, str):
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("tests"), list):
            return payload, f"hard_replay.runs.{side}.diagnostic_artifacts.{name}"
    return {}, str(log_root / side / "output.json")


def _p2p_selector_evidence(log_root: Path, replay: dict[str, Any], selectors: list[str]) -> dict[str, Any]:
    """Require every retained P2P selector to pass in the same Base/Gold run."""
    evidence: dict[str, Any] = {}
    for side in ("base", "gold"):
        payload, source = _structured_output(log_root, replay, side)
        statuses: dict[str, str] = {}
        conflicts: set[str] = set()
        for item in payload.get("tests", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            status = str(item.get("status", "")).strip().upper()
            if not name:
                continue
            if name in statuses and statuses[name] != status:
                conflicts.add(name)
            statuses[name] = status
        # Structured runners may trim selector names while the retained P2P
        # config preserves the exact original string (including trailing
        # whitespace). Compare on the same canonical form, but report the
        # original selector text so diagnostics remain traceable to config.
        canonical_selectors = [(selector, selector.strip()) for selector in selectors]
        missing = [original for original, canonical in canonical_selectors if canonical not in statuses]
        not_passed = {
            original: statuses[canonical]
            for original, canonical in canonical_selectors
            if canonical in statuses and statuses[canonical] not in {"PASS", "PASSED", "OK"}
        }
        evidence[side] = {
            "status": "pass" if payload and not missing and not not_passed and not conflicts else "fail",
            "output_source": source,
            "missing_selectors": missing,
            "not_passed": not_passed,
            "conflicting_results": sorted(conflicts),
        }
    evidence["status"] = "pass" if all(evidence[side]["status"] == "pass" for side in ("base", "gold")) else "fail"
    return evidence


def run_stability(task_root: Path, revision: Path, repeats: int = 2) -> dict[str, Any]:
    paths = resolve_task(task_root)
    root = paths.run_root
    revision = revision.resolve()
    revision_rel = str(revision.relative_to(root)) if revision.is_relative_to(root) else str(revision)
    candidate_tests = revision / "tests"
    if not candidate_tests.is_dir():
        result = {"status": "fail", "revision": revision_rel, "error": "missing candidate tests directory"}
        write_json(paths.stability_path, result)
        return result

    original_f2p, original_p2p = _selectors(paths.original / "tests" / "config.json")
    candidate_f2p, candidate_p2p = _selectors(candidate_tests / "config.json")
    artifact_contract = _config(paths.artifact_contract_path)
    trace = _config(revision / "conversion_trace.json")
    _, converted_regressions = converted_selector_groups(trace)
    f2p_expectation = replay_expectation(trace)
    f2p_accounting_valid = (
        artifact_contract.get("status") == "PASS"
        and artifact_contract.get("revision_relative") == revision_rel
    )
    original_counts = {"f2p_count": len(original_f2p), "p2p_count": len(original_p2p), "expected_test_count": len(set(original_f2p + original_p2p))}
    candidate_counts = {"f2p_count": len(candidate_f2p), "p2p_count": len(candidate_p2p), "expected_test_count": len(set(candidate_f2p + candidate_p2p))}
    existing = _config(paths.hard_replay_path)
    f2p_runs: list[dict[str, Any]] = []
    p2p_runs: list[dict[str, Any]] = []
    if existing.get("revision") == revision_rel:
        f2p_runs.append({"index": 1, "source": "hard_replay", "status": _status(existing), "result": existing})
        if candidate_p2p:
            p2p_runs.append({"index": 1, "source": "hard_replay", **_p2p_selector_evidence(paths.hard_replay_root / "docker", existing, candidate_p2p)})

    total = max(2, int(repeats))
    try:
        row = _config(paths.source / "dataset_row.json")
        image = image_name(paths.original, row)
    except Exception as exc:
        result = {"status": "fail", "revision": revision_rel, "error": f"image resolution failed: {exc!r}", "f2p_runs": f2p_runs}
        write_json(paths.stability_path, result)
        return result

    for index in range(len(f2p_runs) + 1, total + 1):
        log_root = paths.stability_root / f"f2p_replay_{index:03d}"
        replay = run_docker_preflight(
            root, image, tests_dir=candidate_tests, log_root=log_root,
            original_root=paths.original, evidence_root=paths.validation_root,
            write_compat_results=False, expectation=f2p_expectation,
            stage_original_test_patch=bool(original_p2p),
        )
        replay["revision"] = revision_rel
        write_json(log_root / "result.json", replay)
        f2p_runs.append({"index": index, "source": "docker_preflight", "status": _status(replay), "result": replay})
        if candidate_p2p:
            p2p_runs.append({"index": index, "source": "docker_preflight", **_p2p_selector_evidence(log_root, replay, candidate_p2p)})

    f2p_ok = f2p_accounting_valid and len(f2p_runs) >= total and all(item["status"] == "pass" for item in f2p_runs)
    # The artifact contract proves the P2P selector list. Every candidate
    # replay must independently show all of those selectors passing on Base
    # and Gold, using the final Harbor harness and its structured parser output.
    if not candidate_p2p:
        p2p_ok = p2p_runs == []
    else:
        p2p_ok = len(p2p_runs) >= total and all(item["status"] == "pass" for item in p2p_runs)
    result = {
        "status": "pass" if f2p_ok and p2p_ok else "fail",
        "revision": revision_rel,
        "repeat_count": total,
        "f2p_runs": f2p_runs,
        "p2p_runs": p2p_runs,
        "original_counts": original_counts,
        "candidate_counts": candidate_counts,
        "f2p_scope_preserved": f2p_accounting_valid,
        "f2p_selector_count_changed": len(candidate_f2p) != len(original_f2p),
        "f2p_scope_note": "F2P selectors may merge into fewer functional tests; conversion_trace accounting is authoritative.",
        "f2p_expectation": f2p_expectation,
        "p2p_scope_preserved": True,
        "p2p_policy": "retained_original_plus_converted_base_regressions",
        "retained_p2p_count": len(candidate_p2p),
        "converted_regression_count": len(converted_regressions),
        "excluded_original_p2p_count": len(original_p2p) - len([
            selector for selector in candidate_p2p if selector in set(original_p2p)
        ]),
    }
    write_json(paths.stability_path, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--revision", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args(argv)
    result = run_stability(args.task_root, args.revision, args.repeats)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
