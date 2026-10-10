#!/usr/bin/env python3
"""Offline integrity check for the frozen 100/20 handoff bundle."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = "deepseek_miniswe_20_20261008"
errors: list[str] = []


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return {}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def original_tree_hash(path: Path) -> str:
    """Stage 1 preparation's tree hash, including relative file names."""
    digest = hashlib.sha256()
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(f"{file_hash(file)}  {file.relative_to(path).as_posix()}\n".encode())
    return digest.hexdigest()


def stage3_tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(file.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(bytes.fromhex(file_hash(file)))
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    selected = [x.strip() for x in (ROOT / "task_list/selected_100.txt").read_text().splitlines() if x.strip()]
    require(len(selected) == len(set(selected)) == 100, "Stage 1 list must contain 100 unique IDs")
    selected_set = set(selected)
    actual_tasks = {p.name for p in (ROOT / "tasks").iterdir() if p.is_dir()}
    require(actual_tasks == selected_set, "tasks/ directory does not exactly match selected_100.txt")
    stage1_dirs = {p.name for p in (ROOT / "data/stage1").iterdir() if p.is_dir()}
    require(stage1_dirs == selected_set, "data/stage1/ must contain exactly selected 100 IDs")
    report = load(ROOT / "data/stage1/final_100_report.json")
    require(report.get("status") == "READY" and report.get("ready_count") == 100,
            "Stage 1 frozen report is not READY 100/100")
    by_id = {x.get("instance_id"): x for x in report.get("tasks", [])}
    require(set(by_id) == selected_set, "Stage 1 report task IDs differ from selection")
    rows = load(ROOT / "data/dataset_rows.json").get("rows", [])
    row_by_id = {x.get("instance_id"): x for x in rows}
    require(set(row_by_id) == selected_set, "dataset_rows.json must contain exactly selected 100")
    for instance in selected:
        original = ROOT / "tasks" / instance / "original"
        source = ROOT / "data/stage1" / instance / "source"
        preflight = load(ROOT / "data/stage1" / instance / "preflight/report.json")
        provenance = load(source / "provenance.json")
        for rel in ["task.toml", "instruction.md", "tests/test.sh", "solution/gold_patch.diff"]:
            require((original / rel).is_file(), f"{instance}: missing original/{rel}")
        for rel in ["problem_statement.md", "requirements.md", "interface.md", "dataset_row.json"]:
            require((source / rel).is_file(), f"{instance}: missing source/{rel}")
        require(preflight.get("preflight", {}).get("status") == "pass", f"{instance}: preflight not PASS")
        runs = preflight.get("preflight", {}).get("runs", {})
        require(runs.get("base", {}).get("returncode") not in (None, 0)
                and runs.get("gold", {}).get("returncode") == 0,
                f"{instance}: Base/Gold verdict mismatch")
        if original.is_dir() and provenance:
            require(original_tree_hash(original) == provenance.get("original", {}).get("tree_sha256"),
                    f"{instance}: original tree hash mismatch")
        if instance in row_by_id and provenance:
            row_sha = hashlib.sha256(json.dumps(row_by_id[instance], sort_keys=True,
                                                ensure_ascii=False).encode()).hexdigest()
            require(row_sha == provenance.get("dataset", {}).get("row_sha256"),
                    f"{instance}: data row hash mismatch")
        require(by_id.get(instance, {}).get("status") == "READY", f"{instance}: not READY in final report")

    frozen = load(ROOT / "check/frozen_20.json")
    manifest = load(ROOT / "check/stage3" / EXP / "manifest.json")
    qualified = manifest.get("qualified_tasks", [])
    cohort_text = (ROOT / "check/qualified_tasks.txt").read_text(encoding="utf-8")
    cohort_sha = hashlib.sha256(cohort_text.encode()).hexdigest()
    require(cohort_sha == manifest.get("cohort_source_sha256"),
            "qualified_tasks.txt SHA256 differs from frozen Stage 3 manifest")
    listed_ids = re.findall(r"(?m)^\d+\. (instance_\S+)$", cohort_text)
    listed_attempts = re.findall(r"(?m)^\s+attempt: (attempt_\d+)", cohort_text)
    require(list(zip(listed_ids, listed_attempts)) ==
            [(x.get("instance_id"), x.get("attempt")) for x in qualified],
            "qualified_tasks.txt task/attempt order differs from frozen manifest")
    frozen_pairs = [(x.get("instance_id"), x.get("attempt")) for x in frozen.get("qualified_tasks", [])]
    manifest_pairs = [(x.get("instance_id"), x.get("attempt")) for x in qualified]
    require(len(manifest_pairs) == len(set(manifest_pairs)) == 20, "Stage 3 manifest must have 20 unique pairs")
    require(manifest_pairs == frozen_pairs, "frozen_20.json differs from Stage 3 manifest")
    require({x[0] for x in manifest_pairs} <= selected_set, "Stage 3 IDs not contained in Stage 1 selection")
    actual_runs = {p.name for p in (ROOT / "runs").iterdir() if p.is_dir()}
    require(actual_runs == {x[0] for x in manifest_pairs}, "runs/ must contain exactly frozen 20 IDs")
    stage3_dirs = {p.name for p in (ROOT / "check/stage3" / EXP / "instances").iterdir() if p.is_dir()}
    require(stage3_dirs == {x[0] for x in manifest_pairs}, "Stage 3 instances/ must contain exactly frozen 20 IDs")
    for task in qualified:
        instance, attempt = task["instance_id"], task["attempt"]
        attempts_dir = ROOT / "runs" / instance / "attempts"
        require({x.name for x in attempts_dir.iterdir() if x.is_dir()} == {attempt},
                f"{instance}: runs/ contains a later or extra attempt")
        attempt_root = attempts_dir / attempt
        final = attempt_root / "final"
        require((ROOT / "runs" / instance / "source/problem_statement.md").is_file(),
                f"{instance}: run source missing")
        require((final / "tests/test.sh").is_file(), f"{instance}: final verifier missing")
        for rel, status in [("review/final_audit.json", "PASS"),
                            ("review/independent_audit.json", "PASS"),
                            ("intermediate/validation/acceptance.json", "accepted"),
                            ("intermediate/packaging/package_report.json", "packaged")]:
            result = load(attempt_root / rel)
            require(result.get("status") == status, f"{instance}: {rel} status is not {status}")
        require((attempt_root / "intermediate/converter/conversion_trace.json").is_file(),
                f"{instance}: conversion trace missing")
        if (final / "tests").is_dir():
            require(stage3_tree_hash(final / "tests") == task.get("final_tests_sha256"),
                    f"{instance}: final tests hash mismatch")
        instruction = final / "instruction.md"
        if instruction.is_file():
            require(file_hash(instruction) == task.get("final_instruction_sha256"),
                    f"{instance}: final instruction hash mismatch")
        for cohort in ("original", "converted"):
            rollout = ROOT / "check/stage3" / EXP / "instances" / instance / cohort / "rollout_001"
            patch = rollout / "candidate.patch"
            grade = load(rollout / "regrade.json")
            solver = load(rollout / "solver_status.json")
            require(patch.is_file() and patch.stat().st_size > 0, f"{instance}/{cohort}: patch missing")
            if patch.is_file():
                require(file_hash(patch) == grade.get("patch_sha256"),
                        f"{instance}/{cohort}: patch hash mismatch")
            require(solver.get("status") == "complete" and grade.get("status") == "complete",
                    f"{instance}/{cohort}: rollout/regrade incomplete")
            require(all(grade.get(v, {}).get("valid_verdict") for v in ("original", "functional")),
                    f"{instance}/{cohort}: invalid verifier verdict")
            require((rollout / "harbor_trial_result.json").is_file(),
                    f"{instance}/{cohort}: Harbor trial result missing")
    print(json.dumps({"stage1_selected": len(selected), "stage1_ready": report.get("ready_count"),
                      "stage2_stage3_frozen": len(manifest_pairs), "stage3_rollouts": len(manifest_pairs) * 2,
                      "errors": len(errors)}, ensure_ascii=False, indent=2))
    for issue in errors[:30]:
        print("ERROR:", issue)
    if len(errors) > 30:
        print(f"... and {len(errors) - 30} more errors")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
