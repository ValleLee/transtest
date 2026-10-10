#!/usr/bin/env python3
"""Materialize compact human-review records for one Stage 2 run."""
from __future__ import annotations
import argparse, csv, json
from datetime import datetime, timezone
from pathlib import Path
import sys
from swepro_trans.paths import PROJECT_ROOT, resolve_task


def load(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-root", type=Path, required=True)
    ap.add_argument("--revision", type=Path, required=True)
    args = ap.parse_args(argv)
    paths = resolve_task(args.task_root)
    run, revision = paths.run_root, args.revision.resolve()
    if not revision.is_relative_to(paths.revisions_root.resolve()):
        raise SystemExit("revision is outside run-root revisions")
    review = paths.review_root
    review.mkdir(parents=True, exist_ok=True)
    trace = load(revision / "conversion_trace.json") or {}
    rows = trace.get("f2p_accounting", []) if isinstance(trace, dict) else []
    decisions = {}
    emitted = 0
    for row in rows:
        decision = str(row.get("decision", "unknown"))
        decisions[decision] = decisions.get(decision, 0) + 1
        emitted += len(row.get("emitted_tests", []) or [])
    pipeline = load(paths.pipeline_report_path) or {}
    semantic = load(paths.semantic_review_path) or {}
    hard = load(paths.hard_replay_path) or {}
    behavior_roles = load(paths.behavior_role_audit_path) or {}
    stability = load(paths.stability_path) or {}
    positive = load(paths.qa_branch("positive") / "summary.json") or {}
    negative = load(paths.qa_branch("negative") / "summary.json") or {}
    acceptance = load(paths.acceptance_path) or {}
    package = load(paths.package_report_path) or {}
    state = load(paths.state_path) or {}
    independent = load(review / "independent_audit.json") or {}
    final_exists = paths.final_root.is_dir() and any(paths.final_root.iterdir())
    revision_rel = str(revision.relative_to(run))
    # Acceptance/package are authoritative when a run was resumed after a
    # recoverable script failure; the stage report may still contain the
    # earlier stop status from that interrupted attempt.
    run_status = "complete" if acceptance.get("status") == "accepted" and final_exists and package.get("status") == "packaged" else pipeline.get("status", acceptance.get("status", "unknown"))
    if state.get("status") == "audit_rejected" or independent.get("status") == "FAIL":
        run_status = "audit_rejected"
    metrics = {
        "instance_id": paths.instance_id,
        "revision": revision_rel,
        "status": run_status,
        "f2p_count": len(rows),
        "emitted_test_count": emitted,
        "decision_counts": decisions,
        "rewrite_count": decisions.get("rewrite", 0),
        "merge_count": decisions.get("merge", 0),
        "specification_gap_count": decisions.get("specification_gap", 0),
        "drop_count": decisions.get("drop", 0),
        "manual_review_count": decisions.get("manual_review", 0),
        "justified_drop_count": sum(1 for row in rows if isinstance(row, dict) and row.get("decision") == "drop" and row.get("drop_justification") and row.get("drop_evidence")),
        "semantic_verdict": semantic.get("verdict"),
        "deterministic_binding_gate": semantic.get("deterministic_binding_gate", {}).get("status"),
        "hard_replay": hard.get("status"),
        "behavior_role_audit": behavior_roles.get("status"),
        "behavior_role_counts": behavior_roles.get("role_counts", {}),
        "stability": stability.get("status"),
        "p2p_count": (stability.get("candidate_counts") or {}).get("p2p_count"),
        "stability_repeat_count": stability.get("repeat_count"),
        "positive_qa": positive.get("status"),
        "negative_qa": negative.get("status"),
        "acceptance": acceptance.get("status"),
        "independent_audit": independent.get("status", "not_run"),
        "final_packaged": final_exists and package.get("status") == "packaged",
        "certified_final": run_status == "complete" and state.get("status") == "accepted",
        "generated_at_utc": now(),
    }
    (review / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (review / "summary.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = ["source_f2p", "historical_behavior", "problem_statement_support", "behavior_classification", "base_behavior_status", "verification_role", "binding_detected", "base_repo_observable", "gold_only_binding", "decision", "emitted_tests", "specification_gap", "specification_proposal", "planned_observable_surface", "drop_justification", "drop_evidence", "rationale"]
    role_by_source = {
        str(item.get("source_f2p")): item.get("verification_role", "")
        for item in behavior_roles.get("rows", []) if isinstance(item, dict)
    }
    with (review / "f2p_mapping.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            output_row = dict(row)
            output_row["verification_role"] = role_by_source.get(str(row.get("source_f2p")), "")
            writer.writerow({key: json.dumps(output_row.get(key, ""), ensure_ascii=False) if isinstance(output_row.get(key), (list, dict)) else output_row.get(key, "") for key in fields})
    findings = semantic.get("findings", []) or []
    lines = [
        "# Functional Verifier Conversion Report", "",
        f"- Instance: `{paths.instance_id}`", f"- Revision: `{revision_rel}`",
        f"- Pipeline status: **{metrics['status']}**", f"- Final packaged: **{metrics['final_packaged']}**",
        f"- Independent audit: **{metrics['independent_audit']}**", f"- Certified final: **{metrics['certified_final']}**", "",
        "## Gate summary", "",
        "| Gate | Result |", "|---|---|",
        f"| Artifact contract | `{(pipeline.get('artifact_contract') or {}).get('status', 'unknown')}` |",
        f"| Semantic Judge | `{metrics['semantic_verdict'] or 'not_run'}` |",
        f"| Deterministic binding gate | `{metrics['deterministic_binding_gate'] or 'not_run'}` |",
        f"| Hard replay | `{metrics['hard_replay'] or 'not_run'}` |",
        f"| Functional delta / converted regression audit | `{metrics['behavior_role_audit'] or 'not_run'}` |",
        f"| Stability / retained P2P | `{metrics['stability'] or 'not_run'}` |",
        f"| Positive QA | `{metrics['positive_qa'] or 'not_run'}` |",
        f"| Negative QA | `{metrics['negative_qa'] or 'not_run'}` |",
        f"| Acceptance | `{metrics['acceptance'] or 'not_run'}` |", "",
        "## Conversion accounting", "",
        f"- Historical F2P rows: **{len(rows)}**", f"- Emitted functional tests: **{emitted}**",
        f"- Decisions: `{json.dumps(decisions, ensure_ascii=False, sort_keys=True)}`",
        f"- Replay-proven roles: `{json.dumps(metrics['behavior_role_counts'], ensure_ascii=False, sort_keys=True)}`", "",
        "### Conversion completeness", "",
        "## Specification gaps", "",
        "## Semantic findings", "",
    ]
    incomplete = [row for row in rows if isinstance(row, dict) and ((row.get("decision") in {"rewrite", "merge"} and not row.get("emitted_tests")) or (row.get("decision") == "drop" and not (row.get("drop_justification") and row.get("drop_evidence"))) or row.get("decision") not in {"rewrite", "merge", "drop"})]
    gaps = [row for row in rows if isinstance(row, dict) and row.get("decision") == "specification_gap"]
    if incomplete:
        lines.extend([f"- Incomplete: `{row.get('source_f2p', '<unknown>')}`" for row in incomplete])
    else:
        lines.append("- Every historical F2P has an emitted functional test mapping.")
    if gaps:
        for row in gaps:
            lines.append(f"- `{row.get('source_f2p', '<unknown>')}`: {row.get('specification_gap', '')}")
            lines.append(f"  - Proposed P text: {row.get('specification_proposal', '')}")
            lines.append(f"  - Planned observable surface: {row.get('planned_observable_surface', '')}")
    else:
        lines.append("- No unresolved specification gaps.")
    lines.extend([f"- {item}" for item in findings] or ["- No semantic findings recorded."])
    lines.extend(["", "## Files", "", f"- Revision: `../intermediate/converter/revisions/{revision.name}/`", "- Metrics: `metrics.json`", "- F2P mapping: `f2p_mapping.csv`", "- Stage report: `../intermediate/validation/stage2_pipeline.json`", "- Stability report: `../intermediate/validation/stability/result.json`"])
    (review / "conversion_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "written", "review": str(review), "metrics": metrics}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
