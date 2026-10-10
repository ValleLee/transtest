"""Aggregate the frozen Stage 3 two-instruction, dual-verifier experiment."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

COHORTS = ("original", "converted")
MATRIX_KEYS = ("both_pass", "original_fail_functional_pass",
               "original_pass_functional_fail", "both_fail")


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def seconds(phase: dict[str, Any] | None) -> float | None:
    if not phase or not phase.get("started_at") or not phase.get("finished_at"):
        return None
    try:
        start = datetime.fromisoformat(phase["started_at"].replace("Z", "+00:00"))
        finish = datetime.fromisoformat(phase["finished_at"].replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, (finish - start).total_seconds())


def harbor_details(solver: dict[str, Any], artifact_dir: Path) -> dict[str, Any]:
    trial_dir = solver.get("trial_dir")
    trial_path = Path(trial_dir) / "result.json" if trial_dir else None
    trial = read_json(trial_path) if trial_path else None
    if trial is None:
        # Keep the handoff portable without copying full Harbor job directories.
        trial_path = artifact_dir / "harbor_trial_result.json"
        trial = read_json(trial_path)
    if trial is None:
        return {"trial_result": None, "agent_usage": None, "timing_seconds": None,
                "initial_verifier_pass": None}
    agent = trial.get("agent_result") or {}
    verifier = trial.get("verifier_result") or {}
    reward = (verifier.get("rewards") or {}).get("reward")
    return {
        "trial_result": str(trial_path),
        "agent_usage": {name: agent.get(name) for name in
                        ("n_input_tokens", "n_cache_tokens", "n_output_tokens", "cost_usd")}
        if agent else None,
        "timing_seconds": {name: seconds(trial.get(name)) for name in
                           ("environment_setup", "agent_setup", "agent_execution", "verifier")},
        "initial_verifier_pass": reward == 1.0 if reward is not None else None,
    }


def new_counts() -> dict[str, Any]:
    return {
        "planned": 0, "solver_complete": 0, "nonempty_patches": 0,
        "dual_valid": 0, "no_patch": 0, "regrade_error": 0,
        "original_valid": 0, "original_pass": 0,
        "functional_valid": 0, "functional_pass": 0,
        "agent_usage_available": 0,
        "input_tokens": 0, "cache_tokens": 0, "output_tokens": 0,
        "agent_execution_seconds": 0.0, "agent_setup_seconds": 0.0,
        "initial_verifier_valid": 0, "initial_verifier_pass": 0,
        "native_original_comparable": 0, "native_original_disagree": 0,
    }


def new_matrix() -> dict[str, int]:
    return {key: 0 for key in MATRIX_KEYS}


def add_rollout(counts: dict[str, Any], matrix: dict[str, int], row: dict[str, Any]) -> None:
    solver, grade, details = row["solver"], row["regrade"], row["harbor"]
    counts["planned"] += 1
    counts["solver_complete"] += solver.get("status") == "complete"
    counts["nonempty_patches"] += row["patch_nonempty"]
    if grade.get("status") == "no_patch":
        counts["no_patch"] += 1
    elif grade.get("status") in ("error", "infrastructure_or_patch_error"):
        counts["regrade_error"] += 1
    old = grade.get("original") or {}
    new = grade.get("functional") or {}
    old_valid, new_valid = bool(old.get("valid_verdict")), bool(new.get("valid_verdict"))
    if old_valid:
        counts["original_valid"] += 1
        counts["original_pass"] += bool(old.get("pass"))
    if new_valid:
        counts["functional_valid"] += 1
        counts["functional_pass"] += bool(new.get("pass"))
    if old_valid and new_valid:
        counts["dual_valid"] += 1
        if old.get("pass") and new.get("pass"):
            matrix["both_pass"] += 1
        elif not old.get("pass") and new.get("pass"):
            matrix["original_fail_functional_pass"] += 1
        elif old.get("pass") and not new.get("pass"):
            matrix["original_pass_functional_fail"] += 1
        else:
            matrix["both_fail"] += 1
    usage = details.get("agent_usage") or {}
    if usage:
        counts["agent_usage_available"] += 1
        for source, target in (("n_input_tokens", "input_tokens"),
                               ("n_cache_tokens", "cache_tokens"),
                               ("n_output_tokens", "output_tokens")):
            counts[target] += usage.get(source) or 0
    timing = details.get("timing_seconds") or {}
    counts["agent_execution_seconds"] += timing.get("agent_execution") or 0.0
    counts["agent_setup_seconds"] += timing.get("agent_setup") or 0.0
    if details.get("initial_verifier_pass") is not None:
        counts["initial_verifier_valid"] += 1
        counts["initial_verifier_pass"] += bool(details["initial_verifier_pass"])
        if old_valid:
            counts["native_original_comparable"] += 1
            counts["native_original_disagree"] += (
                bool(details["initial_verifier_pass"]) != bool(old.get("pass"))
            )


def fraction(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def rates(counts: dict[str, Any]) -> dict[str, float | None]:
    return {
        "patch_generation": fraction(counts["nonempty_patches"], counts["planned"]),
        "dual_regrade_coverage_per_planned": fraction(counts["dual_valid"], counts["planned"]),
        "dual_regrade_coverage_per_patch": fraction(counts["dual_valid"], counts["nonempty_patches"]),
        "original_pass_per_valid": fraction(counts["original_pass"], counts["original_valid"]),
        "functional_pass_per_valid": fraction(counts["functional_pass"], counts["functional_valid"]),
    }


def paired_instruction(tasks: list[dict[str, Any]], field: str,
                       task_class: str | None = None) -> dict[str, Any]:
    summary = {"paired_tasks": 0, "original_instruction_pass": 0,
               "converted_instruction_pass": 0, "both_pass": 0,
               "original_only_pass": 0, "converted_only_pass": 0, "both_fail": 0}
    for task in tasks:
        if task_class and task["instruction_change_class"] != task_class:
            continue
        a = task["cohorts"]["original"]["regrade"].get(field) or {}
        b = task["cohorts"]["converted"]["regrade"].get(field) or {}
        if not (a.get("valid_verdict") and b.get("valid_verdict")):
            continue
        av, bv = bool(a.get("pass")), bool(b.get("pass"))
        summary["paired_tasks"] += 1
        summary["original_instruction_pass"] += av
        summary["converted_instruction_pass"] += bv
        category = "both_pass" if av and bv else (
            "original_only_pass" if av else "converted_only_pass" if bv else "both_fail")
        summary[category] += 1
    summary["converted_minus_original_pass_rate"] = fraction(
        summary["converted_instruction_pass"] - summary["original_instruction_pass"],
        summary["paired_tasks"],
    )
    return summary


def semantic_review_summary(output: Path, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for task in tasks:
        for cohort in COHORTS:
            item = task["cohorts"][cohort]
            grade = item["regrade"]
            old, new = grade.get("original") or {}, grade.get("functional") or {}
            if not (old.get("valid_verdict") and new.get("valid_verdict")):
                continue
            if bool(old.get("pass")) == bool(new.get("pass")):
                continue
            direction = "original_fail_functional_pass" if new.get("pass") else "original_pass_functional_fail"
            entries.append({
                "key": f"{task['instance_id']}|{cohort}|1",
                "instance_id": task["instance_id"], "cohort": cohort, "rollout": 1,
                "direction": direction, "instruction_change_class": task["instruction_change_class"],
                "patch": item["patch"], "patch_sha256": grade.get("patch_sha256"),
                "logs": grade.get("logs"),
            })
    write_json(output / "semantic_review_queue.json", {"entries": entries})
    decisions = read_json(output / "semantic_reviews.json") or {}
    by_key = decisions.get("reviews") or {}
    summary = {"candidate_disagreements": len(entries),
               "original_fail_functional_pass": sum(e["direction"] == "original_fail_functional_pass" for e in entries),
               "original_pass_functional_fail": sum(e["direction"] == "original_pass_functional_fail" for e in entries),
               "reviewed": 0, "confirmed_rescues": 0,
               "confirmed_false_rejections": 0, "incorrect_patch": 0,
               "uncertain": 0, "unreviewed": 0}
    for entry in entries:
        decision = by_key.get(entry["key"]) or {}
        if decision.get("patch_sha256") != entry["patch_sha256"]:
            summary["unreviewed"] += 1
            continue
        verdict = decision.get("semantic_verdict")
        if verdict not in ("correct", "incorrect", "uncertain"):
            summary["unreviewed"] += 1
            continue
        summary["reviewed"] += 1
        if verdict == "correct" and entry["direction"] == "original_fail_functional_pass":
            summary["confirmed_rescues"] += 1
        elif verdict == "correct" and entry["direction"] == "original_pass_functional_fail":
            summary["confirmed_false_rejections"] += 1
        elif verdict == "incorrect":
            summary["incorrect_patch"] += 1
        else:
            summary["uncertain"] += 1
    summary["status"] = "complete" if summary["unreviewed"] == 0 else "pending"
    return summary


def aggregate(output: Path) -> dict[str, Any]:
    manifest = read_json(output / "manifest.json")
    if not manifest:
        raise FileNotFoundError(output / "manifest.json")
    cohorts = {name: {"counts": new_counts(), "paired_verifier_matrix": new_matrix()}
               for name in COHORTS}
    totals = new_counts()
    total_matrix = new_matrix()
    tasks: list[dict[str, Any]] = []
    solver_statuses: Counter[str] = Counter()
    for task in manifest["qualified_tasks"]:
        task_dir = output / "instances" / task["instance_id"]
        row = {"instance_id": task["instance_id"], "attempt": task["attempt"],
               "instruction_change_class": task.get("instruction_change_class", "unclassified"),
               "cohorts": {}}
        for cohort in COHORTS:
            artifact_dir = task_dir / cohort / "rollout_001"
            solver = read_json(artifact_dir / "solver_status.json") or {"status": "missing"}
            grade = read_json(artifact_dir / "regrade.json") or {"status": "pending"}
            patch = artifact_dir / "candidate.patch"
            item = {"solver": solver, "regrade": grade, "harbor": harbor_details(solver, artifact_dir),
                    "patch": str(patch) if patch.is_file() else None,
                    "patch_nonempty": patch.is_file() and patch.stat().st_size > 0}
            row["cohorts"][cohort] = item
            solver_statuses[solver["status"]] += 1
            add_rollout(cohorts[cohort]["counts"], cohorts[cohort]["paired_verifier_matrix"], item)
            add_rollout(totals, total_matrix, item)
        write_json(task_dir / "analysis.json", row)
        tasks.append(row)
    for summary in cohorts.values():
        summary["rates"] = rates(summary["counts"])
    review_summary = semantic_review_summary(output, tasks)
    if any(task["cohorts"][cohort]["regrade"].get("status") == "pending"
           for task in tasks for cohort in COHORTS):
        review_summary["status"] = "pending_regrade"
    report = {
        "schema_version": 2, "experiment_id": manifest["experiment_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cohort_size": manifest["cohort_size"],
        "rollouts_per_condition": manifest["rollouts_per_condition"],
        "solver_statuses": dict(solver_statuses),
        "cohorts": cohorts,
        "totals": totals, "paired_verifier_matrix": total_matrix, "rates": rates(totals),
        "paired_instruction": {
            "original_verifier": paired_instruction(tasks, "original"),
            "functional_verifier": paired_instruction(tasks, "functional"),
            "deletion_only_original_verifier": paired_instruction(tasks, "original", "deletion_only"),
            "deletion_only_functional_verifier": paired_instruction(tasks, "functional", "deletion_only"),
            "clarification_original_verifier": paired_instruction(tasks, "original", "deletion_plus_behavior_clarification"),
            "clarification_functional_verifier": paired_instruction(tasks, "functional", "deletion_plus_behavior_clarification"),
        },
        "semantic_review": review_summary,
        "cost_note": "Harbor reports 0 USD for the custom model; actual API billing is not measured here.",
        "tasks": tasks,
    }
    assert sum(total_matrix.values()) == totals["dual_valid"]
    write_json(output / "aggregate.json", report)
    write_report(output / "report.md", report)
    return report


def show_rate(value: float | None) -> str:
    return f"{value:.1%}" if value is not None else "N/A"


def write_report(path: Path, report: dict[str, Any]) -> None:
    c = report["cohorts"]
    lines = [f"# Stage 3 run report — {report['experiment_id']}", "",
             f"Generated: {report['generated_at']}", "",
             "## Two instruction cohorts", "",
             "| Measure | Original instruction | Converted instruction |",
             "|---|---:|---:|" ]
    measures = (("Planned", "planned"), ("Nonempty patches", "nonempty_patches"),
                ("Two valid verifier results", "dual_valid"),
                ("Original verifier PASS", "original_pass"),
                ("Functional verifier PASS", "functional_pass"),
                ("No patch", "no_patch"), ("Replay errors", "regrade_error"),
                ("Input tokens", "input_tokens"), ("Cache tokens", "cache_tokens"),
                ("Output tokens", "output_tokens"),
                ("Native vs regrade comparable", "native_original_comparable"),
                ("Native vs regrade disagreements", "native_original_disagree"))
    for label, key in measures:
        lines.append(f"| {label} | {c['original']['counts'][key]} | {c['converted']['counts'][key]} |")
    lines += ["", "## Paired verifier verdicts", ""]
    for cohort in COHORTS:
        matrix = c[cohort]["paired_verifier_matrix"]
        lines += [f"### {cohort}", "", "| Original verifier | Functional PASS | Functional FAIL |",
                  "|---|---:|---:|",
                  f"| PASS | {matrix['both_pass']} | {matrix['original_pass_functional_fail']} |",
                  f"| FAIL | {matrix['original_fail_functional_pass']} | {matrix['both_fail']} |", ""]
    lines += ["## Paired instruction comparison", "",
              "Only tasks with valid results for both instruction cohorts enter each comparison.", "",
              "| Verifier and task subset | Paired tasks | Original instruction PASS | Converted instruction PASS | Difference |",
              "|---|---:|---:|---:|---:|"]
    for name, row in report["paired_instruction"].items():
        lines.append(f"| {name} | {row['paired_tasks']} | {row['original_instruction_pass']} | "
                     f"{row['converted_instruction_pass']} | "
                     f"{show_rate(row['converted_minus_original_pass_rate'])} |")
    review = report["semantic_review"]
    lines += ["", "## Semantic review", "",
              f"- Disagreements: {review['candidate_disagreements']}",
              f"- Reviewed: {review['reviewed']}; unreviewed: {review['unreviewed']}; uncertain: {review['uncertain']}",
              f"- Confirmed rescues: {review['confirmed_rescues']}",
              f"- Confirmed false rejections: {review['confirmed_false_rejections']}", "",
              "Harbor reports zero USD for this custom model; actual API charges are unavailable.",
              "See `aggregate.json`, `semantic_review_queue.json`, per-task `analysis.json`, trajectories, patches, and replay logs.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
