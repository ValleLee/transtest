"""Mini-SWE candidate generators for Stage 2 Positive/Negative QA."""
from __future__ import annotations
import json, shutil, tempfile, tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from minisweagent.agents.default import DefaultAgent

from ..agents.mini_swe_session import MiniSWEEnvironment, OpenAICompatibleMiniModel, SUBMIT_SENTINEL, _write_workspace_layout
from ..agents.runner import _load_env
from ..paths import resolve_task
from ..validation.binding_signals import binding_signals


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _effective_problem_statement(paths) -> str:
    """Return the solver contract: base P plus any controller-approved supplement."""
    base = (paths.source / "problem_statement.md").read_text(encoding="utf-8").rstrip()
    addendum_path = getattr(paths, "specification_addendum_path", None)
    if addendum_path is not None and addendum_path.is_file():
        addendum = addendum_path.read_text(encoding="utf-8").strip()
        if addendum:
            return base + "\n\n" + addendum + "\n"
    return base + "\n"


def _image(root: Path) -> str:
    paths = resolve_task(root)
    data = tomllib.loads((paths.original / "task.toml").read_text(encoding="utf-8"))
    return str(data["environment"]["docker_image"])


def _previous_candidate_feedback(qa_root: Path, kind: str, candidate_index: int) -> list[dict[str, Any]]:
    """Summarize earlier QA attempts for the next independent mini-SWE session."""
    feedback: list[dict[str, Any]] = []
    for index in range(1, candidate_index):
        candidate = qa_root / "candidates" / f"{kind}_{index:03d}"
        replay = qa_root / "replay" / candidate.name / "replay_result.json"
        def read(path: Path) -> dict[str, Any]:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                return value if isinstance(value, dict) else {}
            except (OSError, json.JSONDecodeError):
                return {}
        metadata = read(candidate / "candidate_metadata.json")
        judgement = read(candidate / "judge.json")
        replay_result = read(replay)
        if not (metadata or judgement or replay_result):
            continue
        feedback.append({
            "candidate_index": index,
            "design_axis": str(metadata.get("design_axis", ""))[:1000],
            "explanation": str(metadata.get("explanation", ""))[:2000],
            "judge_verdict": judgement.get("verdict"),
            "judge_reasons": [str(reason)[:1200] for reason in judgement.get("reasons", [])[:8]]
                if isinstance(judgement.get("reasons"), list) else [],
            "original_pass": replay_result.get("original", {}).get("pass")
                if isinstance(replay_result.get("original"), dict) else None,
            "functional_pass": replay_result.get("functional", {}).get("pass")
                if isinstance(replay_result.get("functional"), dict) else None,
        })
    return feedback


def _candidate_step_limit(kind: str, config: dict[str, Any]) -> int:
    """Use the configured budget for this QA role, falling back compatibly."""
    role_budget = "solver_turns" if kind == "positive" else "mutation_turns"
    agent_config = config.get("agent", {})
    return int(agent_config.get(role_budget, agent_config.get("max_turns", 160)))


def run_candidate_agent(*, task_root: Path, revision: Path, kind: str, env_file: Path, config: dict[str, Any], prompt_path: Path, candidate_index: int = 1) -> dict[str, Any]:
    if kind not in {"positive", "negative"}:
        raise ValueError(f"unknown QA kind: {kind}")
    credentials = _load_env(env_file.resolve())
    if not all(credentials.get(key) for key in ("base_url", "api_key", "model")):
        raise ValueError("QA generator requires DEFAULT_BASE_URL, DEFAULT_MODEL and DEFAULT_API_KEY")
    paths = resolve_task(task_root)
    task_root = paths.run_root
    qa_root = paths.qa_branch(kind)
    session_root = qa_root / "sessions"
    session_root.mkdir(parents=True, exist_ok=True)
    sandbox = Path(tempfile.mkdtemp(prefix=f"{kind}_", dir=session_root))
    candidate = qa_root / "candidates" / f"{kind}_{candidate_index:03d}"
    candidate.mkdir(parents=True, exist_ok=True)
    (sandbox / "evidence").mkdir(); (sandbox / "reference").mkdir(); (sandbox / "run").mkdir(); (sandbox / "scratch").mkdir()
    base_problem = (paths.source / "problem_statement.md").read_text(encoding="utf-8")
    (sandbox / "evidence/base_problem_statement.md").write_text(base_problem, encoding="utf-8")
    (sandbox / "evidence/problem_statement.md").write_text(
        _effective_problem_statement(paths), encoding="utf-8"
    )
    shutil.copy2(revision / "functional_specification.md", sandbox / "evidence/functional_specification.md")
    shutil.copy2(paths.original / "solution/gold_patch.diff", sandbox / "reference/gold.patch")
    # QA mutations must target behavior represented by this revision, not an
    # arbitrary requirement discovered elsewhere in the repository.
    shutil.copy2(revision / "conversion_trace.json", sandbox / "reference/conversion_trace.json")
    shutil.copytree(revision / "tests", sandbox / "reference/functional_tests", dirs_exist_ok=True)
    if kind == "positive":
        verifier_sources = {
            str(file.relative_to(revision)): {"head": file.read_text(encoding="utf-8", errors="replace")[:20000]}
            for file in (revision / "tests").rglob("*") if file.is_file()
        }
        (sandbox / "reference/binding_risks.json").write_text(
            json.dumps(binding_signals(verifier_sources), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    prior_feedback = _previous_candidate_feedback(qa_root, kind, candidate_index)
    if prior_feedback:
        (sandbox / "reference/previous_attempt_feedback.json").write_text(
            json.dumps(prior_feedback, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    parent = paths.qa_branch("positive") / "candidates" / "positive_001" / "candidate.patch"
    if kind == "negative" and parent.is_file():
        shutil.copy2(parent, sandbox / "reference/positive.patch")
    (sandbox / "run/metadata.json").write_text(json.dumps({"docker_image": _image(task_root), "kind": kind}, indent=2) + "\n")
    _write_workspace_layout(sandbox, kind)
    mounts = [
        (sandbox / "evidence", "/workspace/evidence", "ro"),
        (sandbox / "reference", "/workspace/reference", "ro"),
        (sandbox / "run", "/workspace/run", "ro"),
        (sandbox / "scratch", "/workspace/scratch", "rw"),
        (candidate, "/solution", "rw"),
        (sandbox / "WORKSPACE_LAYOUT.md", "/workspace/WORKSPACE_LAYOUT.md", "ro"),
    ]
    image = _image(task_root)
    trajectory = qa_root / "trajectories" / f"{kind}_{candidate_index:03d}.json"
    trajectory.parent.mkdir(parents=True, exist_ok=True)
    environment: MiniSWEEnvironment | None = None
    try:
        model = OpenAICompatibleMiniModel(
            base_url=credentials["base_url"], api_key=credentials["api_key"], model=credentials["model"],
            timeout=int(credentials["request_timeout_seconds"]), max_tokens=int(credentials["max_tokens"]),
        )
        environment = MiniSWEEnvironment(
            sandbox, image, mounts, timeout=int(config["agent"].get("tool_timeout_seconds", 180)),
            role=kind, run_as_root=True,
        )
        prompt = prompt_path.read_text(encoding="utf-8")
        system = prompt + "\n\nEvery response must contain one bash tool call. When complete, execute " + SUBMIT_SENTINEL + " as a standalone command."
        if kind == "positive":
            task = (
                "Construct one materially different implementation that satisfies only the effective evidence/problem_statement.md (the base Problem Statement plus any controller-approved behavior addendum). The functional_specification.md file is a non-normative proposal record and must not add solver requirements. "
                "The repository is in /app; Gold is only construction evidence at /workspace/reference/gold.patch. "
                "Do not modify verifier files. After testing, write a repository-relative patch to "
                "/solution/candidate.patch using git diff, and /solution/candidate_metadata.json with a short explanation. "
                "The patch must apply cleanly to the Base image."
            )
        else:
            task = (
                "Construct one runnable near-correct mutant. First read /workspace/reference/conversion_trace.json "
                "and /workspace/reference/functional_tests to select one p_supported_behavior row whose base_behavior_status is changed_or_missing; the mutation must "
                "make one of that row's functional tests fail while preserving the other represented behaviors. Start by "
                "applying /workspace/reference/gold.patch or the confirmed positive patch when available, then change "
                "exactly one Problem Statement behavior. "
                "Do not break syntax, dependencies, or unrelated behavior. Write the resulting repository-relative patch "
                "to /solution/candidate.patch and explain target_behavior in /solution/candidate_metadata.json."
            )
        if prior_feedback:
            task += (
                " Read /workspace/reference/previous_attempt_feedback.json before choosing a design. "
                "Address the previous Judge's reasons and vary the failed design axis; "
                "do not resubmit the same strategy with only cosmetic changes."
            )
        environment.start()
        result = DefaultAgent(
            model, environment, system_template=system, instance_template="{{task}}",
            step_limit=_candidate_step_limit(kind, config), cost_limit=0.0,
            max_consecutive_format_errors=int(config["agent"].get("max_consecutive_format_errors", 6)),
            output_path=trajectory,
        ).run(task=task)
        submitted = result.get("exit_status") == "Submitted"
        patch_exists = (candidate / "candidate.patch").is_file()
        metadata_exists = (candidate / "candidate_metadata.json").is_file()
        # A bounded agent may write both required artifacts and then hit its
        # step/format limit before issuing the sentinel command. The artifacts
        # are the authoritative handoff; do not discard a complete candidate.
        if not submitted and patch_exists and metadata_exists:
            submitted = True
            submission_status = "submitted_after_agent_limit"
        else:
            submission_status = "submitted"
        if not submitted:
            raise RuntimeError(f"{kind} QA generator did not submit: {result.get('exit_status')!r}")
        if not patch_exists:
            raise RuntimeError(f"{kind} QA generator submitted without candidate.patch")
        report = {
            "status": submission_status, "kind": kind, "candidate": str(candidate.relative_to(task_root)),
            "trajectory": str(trajectory.relative_to(task_root)), "submitted_at_utc": _now(),
            "patch": str((candidate / "candidate.patch").relative_to(task_root)),
        }
        (candidate / "generator_report.json").write_text(json.dumps(report, indent=2) + "\n")
        return report
    finally:
        if environment is not None:
            environment.close()
        shutil.rmtree(sandbox, ignore_errors=True)
        if session_root.is_dir() and not any(session_root.iterdir()):
            session_root.rmdir()
