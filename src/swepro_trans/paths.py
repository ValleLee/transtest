"""Canonical filesystem contract for Stage 2 runs and attempts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def canonical_path(value: str | Path, *, base: Path | None = None) -> Path:
    """Resolve a user or subprocess path exactly once at the command boundary."""
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (base or Path.cwd()).joinpath(path).resolve()


def project_file(value: str | Path) -> Path:
    """Resolve config/prompt files relative to the project root when relative."""
    return canonical_path(value, base=PROJECT_ROOT)


def validate_instance_id(instance_id: str) -> str:
    value = str(instance_id).strip()
    if not value or value in {".", ".."}:
        raise ValueError("instance_id must be non-empty")
    if "/" in value or "\\" in value or Path(value).name != value:
        raise ValueError(f"instance_id contains a path separator: {value!r}")
    return value


def _attempt_number(path: Path) -> int:
    try:
        return int(path.name.removeprefix("attempt_"))
    except ValueError:
        return -1


def latest_attempt(run_root: Path) -> Path | None:
    attempts = run_root / "attempts"
    candidates = [
        path for path in attempts.glob("attempt_[0-9][0-9][0-9]")
        if path.is_dir() and _attempt_number(path) >= 0
    ]
    return max(candidates, key=_attempt_number) if candidates else None


def allocate_attempt(run_root: Path) -> Path:
    attempts = run_root / "attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    number = max((_attempt_number(path) for path in attempts.glob("attempt_[0-9][0-9][0-9]")), default=0) + 1
    path = attempts / f"attempt_{number:03d}"
    path.mkdir(parents=True, exist_ok=False)
    return path


@dataclass(frozen=True)
class TaskPaths:
    """Paths shared by one task and one immutable conversion attempt.

    ``run_root/source`` is shared input evidence. All generated artifacts are
    scoped to ``run_root/attempts/attempt_NNN``. For backward compatibility, a
    run without an attempts directory uses the run root as its artifact root.
    """

    instance_id: str
    original_root: Path
    run_root: Path
    attempt_root: Path | None = None

    @property
    def artifact_root(self) -> Path:
        return self.attempt_root or self.run_root

    @property
    def source(self) -> Path:
        return self.run_root / "source"

    @property
    def intermediate(self) -> Path:
        return self.artifact_root / "intermediate"

    @property
    def attempts_root(self) -> Path:
        return self.run_root / "attempts"

    @property
    def latest_attempt_path(self) -> Path:
        return self.run_root / "latest_attempt.json"

    @property
    def converter_root(self) -> Path:
        return self.intermediate / "converter"

    @property
    def trajectory_root(self) -> Path:
        return self.converter_root / "trajectory"

    @property
    def original(self) -> Path:
        return self.original_root / "original"

    @property
    def revisions_root(self) -> Path:
        return self.converter_root / "revisions"

    @property
    def validation_root(self) -> Path:
        return self.intermediate / "validation"

    @property
    def artifact_contract_path(self) -> Path:
        return self.validation_root / "sanity" / "revision_contract.json"

    @property
    def semantic_review_path(self) -> Path:
        return self.validation_root / "semantic" / "review.json"

    @property
    def hard_replay_root(self) -> Path:
        return self.validation_root / "hard_replay"

    @property
    def hard_replay_path(self) -> Path:
        return self.hard_replay_root / "result.json"

    @property
    def behavior_role_audit_path(self) -> Path:
        return self.validation_root / "behavior_roles" / "audit.json"

    @property
    def stability_root(self) -> Path:
        return self.validation_root / "stability"

    @property
    def stability_path(self) -> Path:
        return self.stability_root / "result.json"

    @property
    def acceptance_path(self) -> Path:
        return self.validation_root / "acceptance.json"

    @property
    def specification_addendum_path(self) -> Path:
        """Controller-generated behavior supplement for the next revision."""
        return self.intermediate / "specification_addendum.md"

    @property
    def qa_root(self) -> Path:
        return self.intermediate / "qa"

    def qa_branch(self, kind: str) -> Path:
        if kind not in {"positive", "negative"}:
            raise ValueError(f"unknown QA branch: {kind!r}")
        return self.qa_root / kind

    @property
    def packaging_root(self) -> Path:
        return self.intermediate / "packaging"

    @property
    def package_report_path(self) -> Path:
        return self.packaging_root / "package_report.json"

    @property
    def control_root(self) -> Path:
        return self.intermediate / "control"

    @property
    def state_path(self) -> Path:
        return self.control_root / "state.json"

    @property
    def events_path(self) -> Path:
        return self.control_root / "events.jsonl"

    @property
    def conversion_trace_path(self) -> Path:
        return self.converter_root / "conversion_trace.json"

    @property
    def pipeline_report_path(self) -> Path:
        return self.validation_root / "stage2_pipeline.json"

    @property
    def pipeline_history_root(self) -> Path:
        return self.validation_root / "pipeline_runs"

    @property
    def layout_manifest_path(self) -> Path:
        return self.artifact_root / "layout_manifest.json"

    @property
    def run_manifest_path(self) -> Path:
        return self.run_root / "run_manifest.json"

    @property
    def final_root(self) -> Path:
        return self.artifact_root / "final"

    @property
    def review_root(self) -> Path:
        return self.artifact_root / "review"

    def for_attempt(self, attempt_root: Path) -> "TaskPaths":
        return TaskPaths(self.instance_id, self.original_root, self.run_root, attempt_root.resolve())


def resolve_task(task_root: Path, run_root: Path | None = None) -> TaskPaths:
    """Resolve original and run roots from the canonical project layout.

    ``tasks/<id>`` is the immutable Harbor task; ``runs/<id>`` and its
    ``attempts/`` children are derived artifacts. Prefer these structural
    locations over the presence of an ``original/`` directory: Docker mounts
    and old runs can leave a same-named directory under ``runs`` and must not
    change the source-of-truth selection.
    """
    supplied = task_root.resolve()
    tasks_root = (PROJECT_ROOT / "tasks").resolve()
    runs_root = (PROJECT_ROOT / "runs").resolve()

    if supplied.parent == tasks_root:
        original_root = supplied
        instance_id = supplied.name
        resolved_run = (run_root or runs_root / instance_id).resolve()
        attempt = latest_attempt(resolved_run)
    elif supplied.parent == runs_root:
        resolved_run = supplied if run_root is None else run_root.resolve()
        instance_id = supplied.name
        original_root = (tasks_root / instance_id).resolve()
        attempt = latest_attempt(resolved_run)
    elif supplied.parent.name == "attempts" and supplied.name.startswith("attempt_"):
        resolved_run = supplied.parents[1]
        instance_id = resolved_run.name
        original_root = (tasks_root / instance_id).resolve()
        attempt = supplied
    elif supplied.name == "original" and supplied.parent.parent == tasks_root:
        original_root = supplied.parent
        instance_id = supplied.parent.name
        resolved_run = (run_root or runs_root / instance_id).resolve()
        attempt = latest_attempt(resolved_run)
    elif (supplied / "original").is_dir():
        # Compatibility for an external checkout that predates the canonical
        # tasks/runs roots. This branch is intentionally last.
        original_root = supplied
        instance_id = supplied.name
        resolved_run = (run_root or runs_root / instance_id).resolve()
        attempt = latest_attempt(resolved_run)
    else:
        resolved_run = supplied if run_root is None else run_root.resolve()
        instance_id = resolved_run.name
        original_root = (tasks_root / instance_id).resolve()
        attempt = latest_attempt(resolved_run)

    if not (original_root / "original").is_dir():
        raise FileNotFoundError(f"missing immutable Harbor task: {original_root / 'original'}")
    return TaskPaths(validate_instance_id(instance_id), original_root, resolved_run, attempt)
