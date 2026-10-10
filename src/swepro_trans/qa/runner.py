"""Run Positive or Negative QA with bounded mini-swe retries."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from ..agents.judge import judge, write_judgement
from ..paths import PROJECT_ROOT, canonical_path, resolve_task
from ..conversion_schema import has_functional_rows, replay_expectation
from ..validation.binding_signals import binding_signals as _binding_signals
from .session import _effective_problem_statement, run_candidate_agent



def env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip().upper()] = value.strip().strip("\"").strip("'")

    def get(name: str, default: str = "") -> str:
        return values.get(name, values.get(f"DEFAULT_{name}", default))

    return {
        "backend": get("BACKEND", "openai_compatible"),
        "base_url": get("BASE_URL"),
        "api_key": get("API_KEY"),
        "model": get("MODEL"),
        "request_timeout_seconds": get("REQUEST_TIMEOUT_SECONDS", "600"),
        "max_tokens": get("MAX_TOKENS", "8192"),
    }


def _json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _gate_precheck(paths, revision: Path) -> None:
    revision_rel = str(revision.relative_to(paths.run_root))
    contract = _json(paths.artifact_contract_path)
    hard = _json(paths.hard_replay_path)
    behavior_roles = _json(paths.behavior_role_audit_path)
    semantic = _json(paths.semantic_review_path)
    stability = _json(paths.stability_path)
    if not (contract and contract.get("status") == "PASS" and contract.get("revision_relative") == revision_rel):
        raise SystemExit("QA requires artifact contract PASS for this revision")
    if not (hard and hard.get("status") == "pass" and hard.get("revision") == revision_rel):
        raise SystemExit("QA requires hard replay pass for this revision")
    if not (behavior_roles and behavior_roles.get("status") == "PASS" and behavior_roles.get("revision") == revision_rel):
        raise SystemExit("QA requires behavior role audit PASS for this revision")
    if not (semantic and semantic.get("verdict") == "PASS" and semantic.get("revision") == revision_rel):
        raise SystemExit("QA requires semantic Judge PASS for this revision")
    if not (stability and stability.get("status") == "pass" and stability.get("revision") == revision_rel):
        raise SystemExit("QA requires stability/P2P replay PASS for this revision")


def _deterministic_candidate_fallback(*, paths, kind: str, patch: Path, metadata: dict[str, Any] | None, replay: dict[str, Any]) -> dict[str, Any]:
    """Record executable evidence without certifying semantic QA.

    A different patch and a passing verifier cannot establish that a positive
    solution satisfies P or differs materially from Gold. Likewise a failing
    verifier cannot establish that a negative mutant violates exactly one
    product behavior. Both cases require a fresh Solution/Mutation Judge.
    """
    rejected_verdict = "INVALID" if kind == "positive" else "OFF_TARGET"
    reasons = ["LLM QA Judge did not certify candidate semantics; replay and patch inequality are insufficient"]
    if replay.get("status") != "pass" or replay.get("patches_applied") is not True:
        reasons.append("candidate replay did not complete cleanly")
    return {
        "verdict": rejected_verdict,
        "review_mode": "deterministic_fallback_rejection",
        "judge_verdict": "FAIL",
        "reasons": reasons,
    }



def _ground_negative_verdict(verdict: dict[str, Any], effective_p: str) -> dict[str, Any]:
    """Reject a mutation verdict whose alleged defect is trace-only evidence."""
    if verdict.get("verdict") != "RELEVANT_NON_EQUIVALENT":
        return verdict
    quote = str(verdict.get("p_contract_quote", "")).strip()
    alternative = str(verdict.get("counterfactual_valid_alternative", "")).strip()
    if quote and quote in effective_p and alternative:
        return verdict
    return {
        "verdict": "OFF_TARGET", "review_mode": "p_grounding_protocol_rejection",
        "targeted_source_f2p": verdict.get("targeted_source_f2p", ""),
        "violated_behavior": verdict.get("violated_behavior", ""),
        "reasons": ["Mutation Judge did not supply an exact P quote and a concrete alternative-implementation counterfactual"],
    }


def _verifier_false_positive(kind: str, verdict: dict[str, Any], replay: dict[str, Any]) -> bool:
    """A P-valid implementation rejected by the verifier invalidates this revision.

    Such evidence must not be hidden by trying another QA candidate. Only a
    cleanly applied patch and a completed functional replay establish the
    conflict; transport or setup failures do not count.
    """
    if (replay.get("status") not in {"pass", "fail"} or replay.get("patches_applied") is not True
            or replay.get("infrastructure_failure") is True):
        return False
    functional = replay.get("functional")
    if not isinstance(functional, dict) or functional.get("pass") is not False:
        return False
    return (kind == "negative" and verdict.get("verdict") == "EQUIVALENT") or (
        kind == "positive" and verdict.get("verdict") == "VALID"
    )


def _candidate_judge_evidence(*, paths, revision: Path, patch: Path, replay: dict[str, Any]) -> dict[str, Any]:
    """Show the Judge the actual Gold patch and executable binding risks.

    Candidate metadata is the generating agent's claim; it cannot substitute
    for reference code when deciding whether a design is materially different.
    """
    tests_root = revision / "tests"
    tests = {
        str(file.relative_to(tests_root)): {"head": file.read_text(encoding="utf-8", errors="replace")[:20000]}
        for file in tests_root.rglob("*") if file.is_file()
    }
    gold = paths.original / "solution" / "gold_patch.diff"
    return {
        "problem_statement": _effective_problem_statement(paths),
        "candidate_patch": patch.read_text(encoding="utf-8", errors="replace")[:50000],
        "gold_patch": gold.read_text(encoding="utf-8", errors="replace")[:50000] if gold.is_file() else "",
        "candidate_metadata": _json(patch.parent / "candidate_metadata.json"),
        "replay": replay,
        "conversion_trace": _json(revision / "conversion_trace.json") or {},
        "verifier_binding_signals": _binding_signals(tests),
    }


def _evaluate_candidate(*, paths, revision: Path, kind: str, index: int, env_file: Path, config: dict[str, Any], prompt: Path, deterministic_only: bool = False) -> dict[str, Any]:
    """Generate, replay and judge one candidate; keep every artifact isolated."""
    candidate_dir = paths.qa_branch(kind) / "candidates" / f"{kind}_{index:03d}"
    existing_patch = candidate_dir / "candidate.patch"
    existing_metadata = candidate_dir / "candidate_metadata.json"
    if existing_patch.is_file() and existing_metadata.is_file():
        # Resume from a complete handoff left by an agent that hit a bounded
        # step/format limit after writing its artifacts. This makes QA
        # restartable and avoids throwing away an auditable candidate.
        generated = {
            "status": "resumed_artifacts",
            "kind": kind,
            "candidate": str(candidate_dir.relative_to(paths.run_root)),
            "patch": str(existing_patch.relative_to(paths.run_root)),
        }
    else:
        try:
            generated = run_candidate_agent(
                task_root=paths.run_root, revision=revision, kind=kind,
                env_file=env_file, config=config, prompt_path=prompt,
                candidate_index=index,
            )
        except Exception as exc:
            return {"status": "generation_error", "candidate_index": index, "error": repr(exc)}

    patch = paths.run_root / generated["patch"]
    replay_path = paths.qa_branch(kind) / "replay" / patch.parent.name / "replay_result.json"
    replay_cmd = [
        sys.executable, "-m", "swepro_trans.qa.replay",
        "--task-root", str(paths.run_root), "--revision", str(revision),
        "--patch", str(patch), "--kind", kind, "--output", str(replay_path),
    ]
    proc = subprocess.run(replay_cmd, cwd=PROJECT_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    replay = _json(replay_path) or {"status": "error", "raw": proc.stdout[-4000:]}
    if replay.get("infrastructure_failure") is True:
        return {
            "status": "infrastructure_failure",
            "candidate_index": index,
            "candidate": generated,
            "replay_status": replay.get("status"),
            "replay": str(replay_path.relative_to(paths.run_root)),
        }

    candidate_meta = patch.parent / "candidate_metadata.json"
    evidence = _candidate_judge_evidence(paths=paths, revision=revision, patch=patch, replay=replay)
    judge_name = "solution_judge" if kind == "positive" else "mutation_judge"
    judge_path = Path(config.get("prompts", {}).get(judge_name, f"prompts/judges/{kind}.md"))
    if not judge_path.is_absolute():
        judge_path = PROJECT_ROOT / judge_path
    judge_mode = "llm"
    judge_errors: list[str] = []
    verdict: dict[str, Any] | None = None
    qa_retries = max(1, int(config.get("experiment", {}).get("qa_protocol_retries", 2)))
    if not deterministic_only:
        for judge_attempt in range(qa_retries):
            try:
                candidate_verdict = judge(
                    config=config, credentials=env_values(env_file.resolve()),
                    role=f"{kind}_qa", system=judge_path.read_text(encoding="utf-8"),
                    evidence=evidence,
                )
                candidate_verdict.pop("raw_response", None)
                if candidate_verdict.get("verdict") != "UNCERTAIN":
                    verdict = candidate_verdict
                    break
                judge_errors.append(f"attempt_{judge_attempt + 1}: Judge returned disallowed UNCERTAIN")
            except Exception as exc:
                judge_errors.append(f"attempt_{judge_attempt + 1}: {exc!r}")
    if verdict is None:
        verdict = {"verdict": "FAIL", "reasons": judge_errors}
    if verdict.get("verdict") in {"UNCERTAIN", "FAIL"} and config.get("experiment", {}).get("qa_deterministic_fallback", True):
        fallback = _deterministic_candidate_fallback(
            paths=paths, kind=kind, patch=patch, metadata=_json(candidate_meta), replay=replay,
        )
        fallback["judge_protocol"] = judge_errors or verdict.get("reasons", [])
        verdict = fallback
        judge_mode = "deterministic_fallback"
    # No configuration switch may allow an unresolved business verdict to
    # reach the QA artifact.  Keep the provider result as a diagnostic while
    # recording the candidate as uncertified for this QA kind.
    if verdict.get("verdict") == "UNCERTAIN":
        verdict = {
            "verdict": "INVALID" if kind == "positive" else "OFF_TARGET",
            "review_mode": "protocol_rejection",
            "judge_verdict": "FAIL",
            "reasons": judge_errors or verdict.get("reasons", []) or ["Judge did not return a closed verdict"],
        }
        judge_mode = "protocol_rejection"
    if kind == "negative" and verdict.get("verdict") == "RELEVANT_NON_EQUIVALENT":
        verdict = _ground_negative_verdict(verdict, str(evidence["problem_statement"]))
    write_judgement(patch.parent / "judge.json", verdict)

    expected_judge = "VALID" if kind == "positive" else "RELEVANT_NON_EQUIVALENT"
    functional_pass = replay.get("functional", {}).get("pass") is True
    expected_replay = functional_pass if kind == "positive" else not functional_pass
    passed = (
        verdict.get("verdict") == expected_judge
        and expected_replay
        and replay.get("status") == "pass"
        and replay.get("patches_applied") is True
    )
    false_positive = _verifier_false_positive(kind, verdict, replay)
    return {
        "status": "verifier_false_positive" if false_positive else ("pass" if passed else "fail"),
        "candidate_index": index,
        "candidate": generated,
        "judge_verdict": verdict.get("verdict"),
        "judge_mode": judge_mode,
        "replay_status": replay.get("status"),
        "original_pass": replay.get("original", {}).get("pass") is True,
        "functional_pass": functional_pass,
        "judge": str((patch.parent / "judge.json").relative_to(paths.run_root)),
        "replay": str(replay_path.relative_to(paths.run_root)),
    }


def _collect_candidate_attempts(limit: int, evaluate, *, infrastructure_retries: int = 2) -> list[dict[str, Any]]:
    """Retry infrastructure-only replay failures without spending candidate slots."""
    attempts: list[dict[str, Any]] = []
    for index in range(1, limit + 1):
        retries = 0
        result = evaluate(index)
        while result.get("status") == "infrastructure_failure" and retries < infrastructure_retries:
            retries += 1
            result = evaluate(index)
        if retries:
            result["infrastructure_retries"] = retries
        attempts.append(result)
        if result.get("status") in {"pass", "verifier_false_positive", "infrastructure_failure"}:
            break
    return attempts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--revision", type=Path, required=True)
    parser.add_argument("--kind", choices=("positive", "negative"), required=True)
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs/experiment.yaml")
    parser.add_argument("--deterministic-only", action="store_true", help="run executable replay diagnostics without certifying QA")
    args = parser.parse_args(argv)
    args.task_root = canonical_path(args.task_root)
    args.revision = canonical_path(args.revision)
    args.env_file = canonical_path(args.env_file)
    args.config = canonical_path(args.config)

    paths = resolve_task(args.task_root)
    revision = args.revision.resolve()
    if not revision.is_relative_to(paths.revisions_root.resolve()):
        raise SystemExit("revision is outside run-root revisions")
    _gate_precheck(paths, revision)
    trace = _json(revision / "conversion_trace.json") or {}
    if args.kind == "positive" and replay_expectation(trace) == "base_pass_gold_pass":
        summary = {
            "status": "fail", "kind": args.kind,
            "revision": str(revision.relative_to(paths.run_root)),
            "mode": "non_discriminative_revision_rejected",
            "reason": "A revision whose retained functional behavior already passes on Base cannot enter QA or be published.",
            "attempt_limit": 0, "attempt_count": 0, "confirmed_valid_count": 0,
            "attempts": [], "selected_candidate": None,
        }
        output = paths.qa_branch(args.kind) / "summary.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1
    if not has_functional_rows(trace):
        # No functional behavior means there is no converted task to certify.
        summary = {
            "status": "fail", "kind": args.kind,
            "revision": str(revision.relative_to(paths.run_root)),
            "mode": "no_functional_scope_rejected",
            "reason": "No retained functional F2P behavior exists, so QA cannot certify a functional conversion.",
            "attempt_limit": 0, "attempt_count": 0, "confirmed_valid_count": 0,
            "attempts": [], "selected_candidate": None,
        }
        output = paths.qa_branch(args.kind) / "summary.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1
    config = yaml.safe_load(args.config.resolve().read_text(encoding="utf-8"))
    prompt_name = "positive_generator" if args.kind == "positive" else "negative_generator"
    prompt = Path(config.get("prompts", {}).get(prompt_name, f"prompts/qa/{args.kind}_generator.md"))
    if not prompt.is_absolute():
        prompt = PROJECT_ROOT / prompt
    limit_key = "max_positive_attempts" if args.kind == "positive" else "max_mutation_attempts"
    limit = max(1, int(config.get("experiment", {}).get(limit_key, 1)))

    infrastructure_retries = max(0, int(config.get("experiment", {}).get("qa_infrastructure_retries", 2)))
    attempts = _collect_candidate_attempts(
        limit,
        lambda index: _evaluate_candidate(
            paths=paths, revision=revision, kind=args.kind, index=index,
            env_file=args.env_file, config=config, prompt=prompt,
            deterministic_only=args.deterministic_only,
        ),
        infrastructure_retries=infrastructure_retries,
    )

    false_positive = next((item for item in attempts if item.get("status") == "verifier_false_positive"), None)
    infrastructure_failure = next((item for item in attempts if item.get("status") == "infrastructure_failure"), None)
    winner = None if false_positive else next((item for item in attempts if item.get("status") == "pass"), None)
    summary = {
        "status": "pass" if winner else "fail",
        "kind": args.kind,
        "revision": str(revision.relative_to(paths.run_root)),
        "attempt_limit": limit,
        "attempt_count": len(attempts),
        "confirmed_valid_count": 1 if winner and args.kind == "positive" else 0,
        "attempts": attempts,
        "selected_candidate": winner.get("candidate_index") if winner else None,
    }
    if false_positive:
        summary["mode"] = "verifier_false_positive"
        summary["reason"] = "A cleanly replayed P-valid candidate failed the functional verifier; this revision cannot be certified."
    elif infrastructure_failure:
        summary["mode"] = "replay_infrastructure_failure"
        summary["reason"] = (
            "Candidate replay did not complete because of an infrastructure or harness failure after "
            f"{infrastructure_failure.get('infrastructure_retries', 0)} bounded retries; no semantic verdict was assigned."
        )
    output = paths.qa_branch(args.kind) / "summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 10 if infrastructure_failure else (0 if winner else 1)


if __name__ == "__main__":
    raise SystemExit(main())
