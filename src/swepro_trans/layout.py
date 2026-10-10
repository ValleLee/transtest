"""Canonical Stage 2 run layout and packaging."""
from __future__ import annotations
import hashlib, json, re, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from .paths import PROJECT_ROOT, allocate_attempt, resolve_task


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(path)


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def initialize_conversion_workspace(task_root: Path, run_root: Path | None = None) -> dict:
    """Promote source evidence and allocate one isolated conversion attempt."""
    base = resolve_task(task_root, run_root)
    original, run = base.original, base.run_root
    if not original.is_dir():
        raise FileNotFoundError(f"missing Stage 1 original task: {original}")

    problem = base.source / "problem_statement.md"
    if not problem.is_file():
        stage1_source = PROJECT_ROOT / "data" / "stage1" / base.instance_id / "source"
        if (stage1_source / "problem_statement.md").is_file():
            base.source.parent.mkdir(parents=True, exist_ok=True)
            # Stage 1 evidence has one owner at a time: promote it into this
            # selected run instead of retaining an identical second copy.
            shutil.move(str(stage1_source), str(base.source))
            problem = base.source / "problem_statement.md"
        else:
            raise FileNotFoundError(
                f"missing problem statement evidence: {problem} "
                f"(and no Stage 1 source at {stage1_source})"
            )

    # A run may have been initialized by an older framework version before
    # attempts were introduced. Preserve files if present; refuse to silently
    # reinterpret a non-empty legacy attempt.
    legacy_intermediate = run / "intermediate"
    if legacy_intermediate.is_dir() and any(legacy_intermediate.rglob("*")):
        files = [path for path in legacy_intermediate.rglob("*") if path.is_file()]
        if files:
            raise FileExistsError(
                f"run contains legacy artifacts outside attempts: {legacy_intermediate}"
            )
        shutil.rmtree(legacy_intermediate)
    legacy_manifest = run / "layout_manifest.json"
    if legacy_manifest.exists():
        legacy_manifest.unlink()

    attempt_root = allocate_attempt(run)
    paths = base.for_attempt(attempt_root)
    dirs = (
        paths.revisions_root,
        paths.trajectory_root,
        paths.validation_root / "sanity",
        paths.validation_root / "semantic",
        paths.hard_replay_root,
        paths.stability_root,
        paths.qa_branch("positive"),
        paths.qa_branch("negative"),
        paths.packaging_root,
        paths.control_root,
        paths.review_root,
    )
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)

    write_json(paths.layout_manifest_path, {
        "schema_version": "3.0",
        "layout": "harbor_to_harbor_stage2_attempt",
        "instance_id": paths.instance_id,
        "attempt": attempt_root.name,
        "source": str(paths.source.relative_to(run)),
        "artifact_root": str(paths.artifact_root.relative_to(run)),
        "intermediate": str(paths.intermediate.relative_to(run)),
        "review": str(paths.review_root.relative_to(run)),
        "final": str(paths.final_root.relative_to(run)),
        "ownership": {
            "original": "tasks/<instance_id>/original (immutable)",
            "source": "runs/<instance_id>/source (shared selected Stage 1 evidence)",
            "attempt": "runs/<instance_id>/attempts/attempt_NNN (isolated derived artifacts)",
            "final": "attempt_NNN/final (published only after acceptance)",
        },
        "created_at_utc": now(),
    })
    previous_manifest = load_json(paths.run_manifest_path)
    previous_attempts = previous_manifest.get("attempts", [])
    if not isinstance(previous_attempts, list):
        previous_attempts = []
    attempts = [str(item) for item in previous_attempts if str(item) != attempt_root.name]
    attempts.append(attempt_root.name)
    write_json(paths.run_manifest_path, {
        "schema_version": "3.0",
        "instance_id": paths.instance_id,
        "source": "source",
        "latest_attempt": attempt_root.name,
        "attempts": attempts,
        "created_at_utc": now(),
    })
    write_json(paths.latest_attempt_path, {
        "schema_version": "1.0",
        "instance_id": paths.instance_id,
        "attempt": attempt_root.name,
        "path": str(attempt_root.relative_to(run)),
        "created_at_utc": now(),
    })

    trace = paths.conversion_trace_path
    write_json(trace, {
        "schema_version": "1.0", "status": "pending",
        "specification_source": "source/problem_statement.md",
        "evidence_sources": ["source/requirements.md", "source/interface.md",
                             "original/tests/test_patch.patch", "original/tests/config.json",
                             "original/solution/gold_patch.diff"],
        "f2p_accounting": [], "revisions": [], "created_at_utc": now(),
    })
    paths.events_path.touch(exist_ok=True)
    write_json(paths.state_path, {
        "schema_version": "1.0", "workflow": "verifier_conversion", "status": "initialized",
        "instance_id": paths.instance_id, "attempt": attempt_root.name,
        "instruction_policy": "problem_statement_only_with_audited_addendum",
        "final_task": None, "created_at_utc": now(),
    })
    return {
        "instance_id": paths.instance_id,
        "attempt": attempt_root.name,
        "status": "initialized",
        "original_root": str(paths.original_root),
        "run_root": str(run),
        "attempt_root": str(attempt_root),
        "trace": str(trace),
        "state": str(paths.state_path),
    }


def build_final_instruction(problem: Path, addendum: Path | None = None) -> str:
    """Build the solver instruction from P plus an optional audited addendum."""
    instruction = problem.read_text(encoding="utf-8").rstrip()
    if addendum is not None and addendum.is_file() and addendum.read_text(encoding="utf-8").strip():
        supplement = addendum.read_text(encoding="utf-8").strip()
        supplement = re.sub(r"(?m)^## Behavior from .*\s*$", "## Additional observable behavior", supplement)
        supplement = supplement.replace("using historical F2P evidence", "at the behavior level")
        close = "</pr_description>"
        if close in instruction:
            instruction = instruction.replace(close, "\n\n" + supplement + "\n\n" + close, 1)
        else:
            instruction += "\n\n" + supplement
    return instruction + "\n"


def package_final(task_root: Path, revision: Path, run_root: Path | None = None) -> dict:
    """Package an accepted revision under ``runs/<id>/attempts/attempt_NNN/final``."""
    paths = resolve_task(task_root, run_root)
    run, original, problem = paths.run_root, paths.original, paths.source / 'problem_statement.md'
    verifier_tests = revision.resolve() / 'tests'
    acceptance_path = paths.acceptance_path
    if not problem.is_file() or not verifier_tests.is_dir():
        raise ValueError('accepted revision must contain tests/ and source problem_statement')
    if not acceptance_path.is_file():
        raise ValueError('missing intermediate/validation/acceptance.json; run acceptance gate first')
    try:
        acceptance = json.loads(acceptance_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError('invalid acceptance.json') from exc
    expected_revision = str(revision.resolve().relative_to(run))
    if acceptance.get('status') != 'accepted' or acceptance.get('revision') != expected_revision:
        raise ValueError(f'revision is not accepted: expected {expected_revision}')
    final = paths.final_root
    if final.exists() and any(final.iterdir()):
        # A later repair or a deterministic packaging-policy change may
        # supersede an already packaged artifact, including a rebuild of the
        # same accepted revision. Preserve the previous package explicitly so
        # publication is repeatable without silently mutating the old output.
        previous = load_json(paths.package_report_path)
        previous_revision = str(previous.get("revision", ""))
        label = (previous_revision or "stale").replace("/", "_").replace(":", "-")
        archive = run / "archived" / f"final_{label}"
        suffix = 2
        while archive.exists():
            archive = run / "archived" / f"final_{label}_{suffix}"
            suffix += 1
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(final), str(archive))
        write_json(archive / "archive_manifest.json", {
            "status": "superseded",
            "previous_revision": previous_revision or None,
            "superseded_by": expected_revision,
            "archived_final": str(archive.relative_to(run)),
            "created_at_utc": now(),
        })
    final.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original / 'task.toml', final / 'task.toml')
    # The converter's functional_specification.md is an audit record. Only a
    # controller-owned, behavior-level addendum that passed the complete gate
    # sequence may extend the retained Problem Statement in the instruction.
    proposal = revision.resolve() / 'functional_specification.md'
    if not proposal.is_file():
        raise ValueError('accepted revision must contain the specification proposal record')
    addendum = paths.specification_addendum_path
    instruction = build_final_instruction(problem, addendum)
    (final / 'instruction.md').write_text(instruction, encoding='utf-8')
    for name in ('environment', 'solution'):
        shutil.copytree(original / name, final / name)
    shutil.copytree(
        verifier_tests, final / 'tests',
        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo', '.pytest_cache'),
    )
    report = {'status': 'packaged', 'instance_id': paths.instance_id,
              'instruction_sha256': sha256(final / 'instruction.md'),
              'instruction_source': ['source/problem_statement.md'] + ([str(addendum.relative_to(run))] if addendum.is_file() else []),
              'proposal_record': str((revision / 'functional_specification.md').relative_to(run)),
              'excluded_fields': ['requirements', 'interface', 'functional_specification.md'],
              'specification_addendum': str(addendum.relative_to(run)) if addendum.is_file() else None,
              'revision': expected_revision, 'final_root': str(final),
              'acceptance': str(acceptance_path.relative_to(run)), 'created_at_utc': now()}
    write_json(paths.package_report_path, report)
    # A resumed run may have an earlier rejected stage report. Packaging is
    # only reachable after acceptance, so reconcile that audit record here.
    pipeline_path = paths.pipeline_report_path
    if pipeline_path.is_file():
        pipeline = load_json(pipeline_path)
        pipeline['status'] = 'complete'
        pipeline['package'] = report
        write_json(pipeline_path, pipeline)
    state_path = paths.state_path
    if state_path.is_file():
        state = load_json(state_path)
        state['status'] = 'accepted'
        state['accepted_revision'] = expected_revision
        state['final_task'] = str(final.relative_to(run))
        state['terminal_reason'] = 'All automatic artifact, semantic, replay, stability, and QA gates passed.'
        state.pop('manual_review_reason', None)
        write_json(state_path, state)
    # Rebuild the human-review artifacts after package/state reconciliation.
    # Otherwise a resumed run can be packaged successfully while its review
    # files still describe the earlier pre-package rejection.
    subprocess.run(
        [
            sys.executable,
            "-m",
            "swepro_trans.reporting.human_review",
            "--task-root",
            str(run),
            "--revision",
            str(revision),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return report
