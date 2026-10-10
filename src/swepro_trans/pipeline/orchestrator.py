#!/usr/bin/env python3
"""Run the ordered Stage 2 gates with bounded controller-owned repair."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from ..paths import PROJECT_ROOT, canonical_path, resolve_task
from ..conversion_schema import specification_proposal_is_meta
from .repair import next_revision, seed_revision, write_feedback

ROOT = PROJECT_ROOT

IMMUTABLE_ATTEMPT_STATUSES = frozenset({
    "complete",
    "non_discriminative_task",
})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_object(path: Path, value: dict[str, Any]) -> None:
    """Atomically replace one controller-owned JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _update_attempt_state(paths, *, status: str, revision: str, **fields: Any) -> None:
    """Keep the attempt index aligned with the latest pipeline invocation."""
    state = _load_object(paths.state_path)
    state.update({
        "status": status,
        "attempt": paths.attempt_root.name if paths.attempt_root else None,
        "revision": revision,
        "updated_at_utc": _utc_now(),
        **fields,
    })
    _write_object(paths.state_path, state)


def _attempt_is_immutable(paths, state: dict[str, Any]) -> bool:
    """A published or disposition-closed attempt cannot be repurposed."""
    status = str(state.get("status", ""))
    if status in IMMUTABLE_ATTEMPT_STATUSES:
        return True
    if status != "accepted":
        return False
    package = _load_object(paths.package_report_path)
    return package.get("status") == "packaged" and paths.final_root.is_dir() and any(paths.final_root.iterdir())


def run(cmd: list[str], cwd: Path, *, timeout: int | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    source_root = str(ROOT / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = source_root + (os.pathsep + existing if existing else "")
    try:
        proc = subprocess.run(cmd, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, check=False, timeout=timeout)
        return proc.returncode, proc.stdout
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return 124, output + "\n[controller] child process timed out\n"


def _revision_contract_is_complete(revision: Path) -> bool:
    """Check only presence; validation.revision remains the content authority."""
    required = (
        revision / "conversion_trace.json",
        revision / "functional_specification.md",
        revision / "self_review.md",
        revision / "manifest.json",
        revision / "tests" / "test.sh",
        revision / "tests" / "run_script.sh",
        revision / "tests" / "parser.py",
        revision / "tests" / "config.json",
    )
    return all(path.is_file() and path.stat().st_size > 0 for path in required)


def _parse_output(output: str, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(output[output.index("{"):])
    except (ValueError, json.JSONDecodeError):
        return {**fallback, "raw": output[-4000:]}


def finish(root: Path, report: dict[str, Any], code: int, revision: Path | None = None) -> int:
    paths = resolve_task(root)
    out = paths.pipeline_report_path
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    out.write_text(text, encoding="utf-8")
    revision_rel = (
        str(revision.relative_to(paths.run_root))
        if revision is not None and revision.is_relative_to(paths.run_root)
        else str(report.get("revision", ""))
    )
    state_status = "accepted" if report.get("status") == "complete" else str(report.get("status", "unknown"))
    _update_attempt_state(
        paths,
        status=state_status,
        revision=revision_rel,
        terminal_reason=str(report.get("terminal_reason", "")),
        last_pipeline_report=str(out.relative_to(paths.run_root)),
        last_pipeline_exit_code=code,
    )
    if revision is not None and revision.is_dir():
        paths.pipeline_history_root.mkdir(parents=True, exist_ok=True)
        (paths.pipeline_history_root / f"{revision.name}.json").write_text(text, encoding="utf-8")
        subprocess.run(
            [sys.executable, "-m", "swepro_trans.reporting.human_review", "--task-root", str(root), "--revision", str(revision)],
            cwd=ROOT, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


def _normalized_proposal(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip())


def _recorded_specification_proposals(text: str) -> set[str]:
    """Read behavior sections already promoted to the solver addendum."""
    marker = "## Additional observable behavior"
    return {
        _normalized_proposal(section)
        for section in str(text).split(marker)[1:]
        if _normalized_proposal(section)
    }


def _row_requires_specification_enrichment(row: dict[str, Any], *, addendum_text: str) -> bool:
    """Promote each new behavior once, even when an addendum already exists.

    Base regressions are executable historical coverage and never extend P.
    An unresolved row whose proposal is already in the addendum must instead
    go through semantic review and Converter repair to emit the promised test.
    """
    classification = row.get("behavior_classification")
    is_gap = row.get("decision") == "specification_gap" or classification == "missing_product_behavior"
    if not is_gap:
        return False
    # The validated classification and explicit proposal are authoritative.
    # Free-form provenance prose can discuss what P omits without authorizing
    # promotion of a test description into the solver instruction.
    proposal = str(row.get("specification_proposal") or "").strip()
    return bool(proposal and _normalized_proposal(proposal) not in _recorded_specification_proposals(addendum_text))


def _write_specification_addendum(paths, gaps: list[dict[str, Any]]) -> Path:
    """Append only new behavior-level proposals to a controller-owned addendum."""
    path = paths.specification_addendum_path
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    seen = _recorded_specification_proposals(existing)
    sections: list[str] = []
    for item in gaps:
        proposal = str(item.get("proposal", "")).strip()
        normalized = _normalized_proposal(proposal)
        if not normalized or normalized in seen:
            continue
        if specification_proposal_is_meta(proposal):
            raise ValueError(
                "refusing to write meta-language into specification addendum; "
                "the proposal must state one chosen observable behavior"
            )
        seen.add(normalized)
        sections.extend(["## Additional observable behavior", "", proposal, ""])
    if not sections:
        return path
    if existing.strip():
        content = existing.rstrip() + "\n\n" + "\n".join(sections).rstrip() + "\n"
    else:
        header = [
            "# Functional behavior clarification",
            "",
            "The following observable behaviors are part of this task's functional",
            "contract. They clarify the Problem Statement at the behavior level;",
            "they do not prescribe a class, method, module, signature, or",
            "specific implementation design.",
            "",
        ]
        content = "\n".join(header + sections).rstrip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _retry_or_finish(*, args, paths, root: Path, revision: Path, report: dict[str, Any], code: int, gate: str) -> int:
    """Route candidate defects to repair; keep infrastructure failures distinct."""
    semantic = report.get("semantic_review")
    qa_summary = report.get(gate) if gate in {"positive_qa", "negative_qa"} else None
    if isinstance(qa_summary, dict) and qa_summary.get("mode") == "replay_infrastructure_failure":
        report["status"] = "qa_infrastructure_failure"
        report["terminal_reason"] = (
            f"{gate} replay could not complete after bounded infrastructure retries; "
            "the converter was not asked to change its verifier"
        )
        return finish(paths.attempt_root or root, report, 10, revision)
    if gate == "semantic_review" and isinstance(semantic, dict) and semantic.get("failure_classification") == "judge_transport":
        report["status"] = "semantic_judge_unavailable"
        return finish(paths.attempt_root or root, report, code, revision)
    if not args.auto_repair or args.repair_count >= args.max_revisions:
        # All protocol failures and semantic failures are terminally recorded
        # as automatic rejection after the bounded repair budget. There is no
        # human-only branch in the execution pipeline.
        if report.get("status") == "started":
            report["status"] = f"rejected_{gate}"
        return finish(paths.attempt_root or root, report, code, revision)
    try:
        next_rev = next_revision(paths)
        seed_revision(revision, next_rev)
        feedback = write_feedback(paths, revision, gate, report, next_rev)
        agent_cmd = [
            sys.executable, "-m", "swepro_trans", "agent",
            "--task-root", str(paths.attempt_root or root), "--revision", str(next_rev),
            "--env-file", str(args.env_file), "--config", str(args.config),
        ]
        agent_timeout = int(args.agent_timeout_seconds)
        agent_code, agent_output = run(agent_cmd, ROOT, timeout=agent_timeout)
        report["repair"] = {
            "failed_gate": gate,
            "feedback": str(feedback.relative_to(root)),
            "next_revision": str(next_rev.relative_to(root)),
            "agent_status": "submitted" if agent_code == 0 else "failed",
            "agent_output": agent_output[-4000:],
        }
        if agent_code != 0:
            # Docker cleanup can outlive a successfully written revision. Do
            # not discard complete artifacts; the next revision contract gate
            # still validates their schema and content before replay.
            if _revision_contract_is_complete(next_rev):
                report["repair"]["agent_status"] = "completed_artifacts_after_timeout"
            else:
                report["status"] = "repair_agent_failed"
                return finish(paths.attempt_root or root, report, 8, revision)
        next_args = [
            "--task-root", str(paths.attempt_root or root), "--revision", str(next_rev),
            "--env-file", str(args.env_file), "--config", str(args.config),
            "--max-revisions", str(args.max_revisions), "--repair-count", str(args.repair_count + 1),
            "--agent-timeout-seconds", str(args.agent_timeout_seconds),
        ]
        if args.no_qa:
            next_args.append("--no-qa")
        return main(next_args)
    except Exception as exc:
        report["repair"] = {"failed_gate": gate, "status": "controller_error", "error": repr(exc)}
        report["status"] = "repair_controller_failed"
        return finish(paths.attempt_root or root, report, 8, revision)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--revision", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs/experiment.yaml")
    parser.add_argument("--no-qa", action="store_true", help="stop after stability replay")
    parser.add_argument("--auto-repair", dest="auto_repair", action="store_true", default=True, help="repair failed gates with a new mini-swe revision")
    parser.add_argument("--no-auto-repair", dest="auto_repair", action="store_false")
    parser.add_argument("--max-revisions", type=int, default=4)
    parser.add_argument("--repair-count", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--agent-timeout-seconds", type=int, default=3600, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    args.task_root = canonical_path(args.task_root)
    args.revision = canonical_path(args.revision)
    args.env_file = canonical_path(args.env_file)
    args.config = canonical_path(args.config)

    paths = resolve_task(args.task_root)
    root = paths.run_root
    task_context = paths.attempt_root or root
    revision = args.revision.resolve()
    if not paths.original.is_dir():
        return finish(task_context, {"status": "invalid_task_root", "task_root": str(paths.original_root), "error": "immutable task original/ is missing"}, 2, revision)
    if not revision.is_dir() or not revision.is_relative_to(paths.revisions_root):
        return finish(task_context, {"status": "invalid_revision", "revision": str(revision), "error": "revision must exist under the task revision root"}, 2, revision)

    previous_state = _load_object(paths.state_path)
    previous_status = str(previous_state.get("status", ""))
    if _attempt_is_immutable(paths, previous_state):
        refusal = {
            "status": "immutable_attempt",
            "attempt": paths.attempt_root.name if paths.attempt_root else None,
            "existing_status": previous_status,
            "existing_revision": previous_state.get("revision") or previous_state.get("accepted_revision"),
            "requested_revision": str(revision.relative_to(root)),
            "error": "terminal attempts are immutable; allocate a new attempt for another conversion experiment",
        }
        print(json.dumps(refusal, ensure_ascii=False, indent=2))
        return 12

    py = sys.executable
    revision_rel = str(revision.relative_to(root))
    report: dict[str, Any] = {
        "status": "started", "revision": revision_rel,
        "repair_count": args.repair_count,
        "order": ["artifact_contract", "semantic_review", "hard_replay", "behavior_role_audit", "stability", "positive_qa", "negative_qa", "accept", "package"],
    }
    _update_attempt_state(
        paths,
        status="pipeline_running",
        revision=revision_rel,
        repair_count=args.repair_count,
        terminal_reason="",
        last_pipeline_exit_code=None,
    )
    reset = {
        paths.semantic_review_path: {"verdict": "NOT_RUN", "revision": revision_rel, "reason": "semantic gate has not run for this revision"},
        paths.hard_replay_path: {"status": "not_run", "revision": revision_rel, "reason": "semantic gate has not passed for this revision"},
        paths.behavior_role_audit_path: {"status": "not_run", "revision": revision_rel, "reason": "hard replay has not passed for this revision"},
        paths.stability_path: {"status": "not_run", "revision": revision_rel, "reason": "hard replay has not passed for this revision"},
        paths.qa_branch("positive") / "summary.json": {"status": "not_run", "revision": revision_rel, "reason": "deterministic gates have not passed"},
        paths.qa_branch("negative") / "summary.json": {"status": "not_run", "revision": revision_rel, "reason": "deterministic gates have not passed"},
        paths.acceptance_path: {"status": "not_run", "revision": revision_rel, "reason": "pipeline has not reached acceptance"},
    }
    for path, payload in reset.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    code, output = run([py, "-m", "swepro_trans.validation.revision", "--task-root", str(task_context), "--revision", str(revision)], ROOT)
    contract = _parse_output(output, {"status": "error"})
    report["artifact_contract"] = contract
    if code or contract.get("status") != "PASS":
        report["status"] = "rejected_artifact"
        return _retry_or_finish(args=args, paths=paths, root=root, revision=revision, report=report, code=2, gate="artifact_contract")

    # Important behavior gaps are promoted automatically into an explicit,
    # behavior-only instruction addendum. The next mini-swe revision must use
    # that addendum to emit public/observable tests; it may not invent an API.
    try:
        trace_payload = json.loads((revision / "conversion_trace.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        trace_payload = {}
    non_discriminative = trace_payload.get("task_disposition") == "non_discriminative"
    addendum_text = (
        paths.specification_addendum_path.read_text(encoding="utf-8", errors="replace")
        if paths.specification_addendum_path.is_file() else ""
    )
    specification_gaps = []
    for row in trace_payload.get("f2p_accounting", []):
        if not isinstance(row, dict):
            continue
        if _row_requires_specification_enrichment(row, addendum_text=addendum_text):
            proposal = str(row.get("specification_proposal", "")).strip()
            specification_gaps.append({
                "source_f2p": row.get("source_f2p", "<unknown>"),
                "gap": row.get("specification_gap", "") or "Problem Statement does not state this product behavior",
                "proposal": proposal,
                "planned_observable_surface": row.get("planned_observable_surface", "") or row.get("functional_surface", ""),
            })
    if specification_gaps:
        report["specification_gaps"] = specification_gaps
        try:
            addendum = _write_specification_addendum(paths, specification_gaps)
        except ValueError as exc:
            # Proposals are untrusted Converter output. Keep meta commentary out
            # of the solver instruction and feed the defect back as a revision
            # error rather than terminating the controller with an exception.
            report["artifact_contract"] = {
                "status": "FAIL",
                "contract": {"status": "FAIL", "errors": [str(exc)]},
            }
            report["status"] = "rejected_specification_proposal"
            return _retry_or_finish(
                args=args, paths=paths, root=root, revision=revision,
                report=report, code=2, gate="artifact_contract",
            )
        report["specification_addendum"] = str(addendum.relative_to(root))
        report["status"] = "specification_enrichment"
        review_path = paths.validation_root / "specification_review.json"
        review_path.write_text(json.dumps({
            "status": "auto_enrichment",
            "revision": revision_rel,
            "gaps": specification_gaps,
            "addendum": str(addendum.relative_to(root)),
            "instruction": "The controller promoted behavior-level proposals into the addendum; the next Converter revision must emit public/observable tests or classify pure implementation details as justified drops.",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        state = {}
        if paths.state_path.is_file():
            try:
                state = json.loads(paths.state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                state = {}
        state.update({"status": "specification_enrichment", "attempt": paths.attempt_root.name, "revision": revision_rel, "specification_gaps": specification_gaps, "specification_addendum": str(addendum.relative_to(root))})
        paths.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return _retry_or_finish(args=args, paths=paths, root=root, revision=revision, report=report, code=9, gate="specification_enrichment")

    # A provider/protocol failure is retried for the same revision. Starting a
    # new Converter revision cannot repair a missing Judge response and only
    # multiplies API cost and stale artifacts. Semantic FAIL with actual
    # findings still follows the normal Converter REPAIR route.
    try:
        pipeline_config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    except Exception:
        pipeline_config = {}
    transport_retries = max(0, int(pipeline_config.get("experiment", {}).get("semantic_transport_retries", 1)))
    review = {"verdict": "ERROR", "review_mode": "protocol_failure"}
    output = ""
    for semantic_attempt in range(transport_retries + 1):
        code, output = run([py, "-m", "swepro_trans.validation.semantic", "--task-root", str(task_context), "--revision", str(revision), "--env-file", str(args.env_file), "--config", str(args.config)], ROOT)
        review = _parse_output(output, {"verdict": "ERROR", "review_mode": "protocol_failure"})
        if review.get("verdict") == "PASS":
            break
        if review.get("review_mode") != "protocol_failure":
            break
    report["semantic_review"] = {key: value for key, value in review.items() if key != "raw_response"}
    if review.get("verdict") == "UNCERTAIN":
        review["verdict"] = "FAIL"
        review["review_mode"] = "protocol_failure"
        review.setdefault("findings", []).append("Semantic Judge did not return a usable verdict")
        report["semantic_review"] = review
    if review.get("verdict") != "PASS":
        report["status"] = "rejected_semantic_provider" if review.get("review_mode") == "protocol_failure" else "rejected_semantic"
        # Do not manufacture a new semantic revision for an unavailable
        # provider. The attempt remains resumable after the endpoint recovers.
        if review.get("review_mode") == "protocol_failure":
            return finish(task_context, report, 10, revision)
        return _retry_or_finish(args=args, paths=paths, root=root, revision=revision, report=report, code=3, gate="semantic_review")

    code, output = run([py, "-m", "swepro_trans.validation.revision", "--task-root", str(task_context), "--revision", str(revision), "--execute"], ROOT)
    hard = _parse_output(output, {"status": "error"})
    report["hard_replay"] = hard
    report["status"] = "hard_pass" if code == 0 and hard.get("status") == "PASS" else "rejected_hard"
    if report["status"] != "hard_pass":
        return _retry_or_finish(args=args, paths=paths, root=root, revision=revision, report=report, code=4, gate="hard_replay")

    code, output = run([
        py, "-m", "swepro_trans.validation.behavior_roles",
        "--task-root", str(task_context), "--revision", str(revision),
    ], ROOT)
    role_audit = _parse_output(output, {"status": "error"})
    report["behavior_role_audit"] = role_audit
    if code != 0 or role_audit.get("status") != "PASS":
        report["status"] = "rejected_behavior_roles"
        return _retry_or_finish(
            args=args, paths=paths, root=root, revision=revision,
            report=report, code=4, gate="behavior_role_audit",
        )

    code, output = run([py, "-m", "swepro_trans.validation.stability", "--task-root", str(task_context), "--revision", str(revision), "--repeats", "2"], ROOT)
    stability = _parse_output(output, {"status": "error"})
    report["stability"] = stability
    report["status"] = "stability_pass" if code == 0 and stability.get("status") == "pass" else "rejected_stability"
    if report["status"] != "stability_pass":
        # Stability failures are verifier defects or replay-contract failures;
        # route them through the same bounded mini-SWE repair loop as the
        # earlier gates instead of silently terminating the conversion.
        return _retry_or_finish(args=args, paths=paths, root=root, revision=revision, report=report, code=4, gate="stability")
    # A non-discriminative task still needs executable proof. Semantic review
    # establishes mapping equivalence; hard and stability replay establish that
    # all converted behavior and Base-native P2P pass on both Base and Gold.
    # Only after those gates may the controller stop without QA or publication.
    if non_discriminative:
        disposition = {
            "status": "non_discriminative_task",
            "revision": revision_rel,
            "reason": trace_payload.get("task_disposition_reason", ""),
            "semantic_review": "PASS",
            "hard_replay": "PASS",
            "stability": "PASS",
            "instruction": (
                "No final Harbor task was published because the retained public behavior does not "
                "distinguish Base from Gold. Reclassify only if evidence identifies a changed or missing "
                "observable product behavior; do not manufacture a Gold-only contract."
            ),
        }
        out = paths.validation_root / "non_discriminative_task.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(disposition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        state = {}
        if paths.state_path.is_file():
            try:
                state = json.loads(paths.state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                state = {}
        state.update({
            "status": "non_discriminative_task",
            "attempt": paths.attempt_root.name if paths.attempt_root else None,
            "revision": revision_rel,
            "terminal_reason": disposition["reason"],
        })
        paths.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report["task_disposition"] = disposition
        report["status"] = "non_discriminative_task"
        return finish(task_context, report, 11, revision)

    if args.no_qa:
        return finish(task_context, report, 0, revision)

    for kind in ("positive", "negative"):
        code, output = run([py, "-m", "swepro_trans.qa.runner", "--task-root", str(task_context), "--revision", str(revision), "--kind", kind, "--env-file", str(args.env_file), "--config", str(args.config)], ROOT)
        summary_path = paths.qa_branch(kind) / "summary.json"
        summary = _load_summary(summary_path, output)
        report[f"{kind}_qa"] = summary
        if code or summary.get("status") != "pass":
            report["status"] = f"rejected_{kind}_qa"
            return _retry_or_finish(args=args, paths=paths, root=root, revision=revision, report=report, code=5, gate=f"{kind}_qa")

    code, output = run([py, "-m", "swepro_trans.validation.acceptance", "--task-root", str(task_context), "--revision", str(revision)], ROOT)
    acceptance_path = paths.acceptance_path
    acceptance = _load_summary(acceptance_path, output)
    report["acceptance"] = acceptance
    if code or acceptance.get("status") != "accepted":
        report["status"] = "rejected_acceptance"
        return _retry_or_finish(args=args, paths=paths, root=root, revision=revision, report=report, code=6, gate="acceptance")

    code, output = run([py, "-m", "swepro_trans", "package", "--task-root", str(task_context), "--revision", str(revision)], ROOT)
    report["package"] = _parse_output(output, {"status": "error"})
    report["status"] = "complete" if code == 0 and report["package"].get("status") == "packaged" else "rejected_package"
    if report["status"] != "complete":
        return _retry_or_finish(args=args, paths=paths, root=root, revision=revision, report=report, code=7, gate="package")
    return finish(task_context, report, 0, revision)


def _load_summary(path: Path, output: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except json.JSONDecodeError:
        value = None
    return value if isinstance(value, dict) else {"status": "error", "raw": output[-4000:]}


if __name__ == "__main__":
    raise SystemExit(main())
