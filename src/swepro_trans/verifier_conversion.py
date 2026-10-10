"""Public command line for the Harbor-to-Harbor conversion workflow.

The CLI is deliberately thin: domain implementations live in ``agents``,
``validation``, ``qa``, ``pipeline`` and ``reporting``.  The legacy scripts
remain wrappers around these same functions for existing batch commands.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from .layout import initialize_conversion_workspace, package_final
from .paths import PROJECT_ROOT, canonical_path


def _common_task_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--revision", type=Path, required=True)


def _stage_arguments(parser: argparse.ArgumentParser, *, revision: bool = True) -> None:
    _common_task_arguments(parser) if revision else parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs/experiment.yaml")


def _invoke(module: str, argv: list[str]) -> int:
    if module == "validation.revision":
        from .validation.revision import main
    elif module == "validation.semantic":
        from .validation.semantic import main
    elif module == "validation.acceptance":
        from .validation.acceptance import main
    elif module == "validation.stability":
        from .validation.stability import main
    elif module == "qa.runner":
        from .qa.runner import main
    elif module == "reporting.human_review":
        from .reporting.human_review import main
    elif module == "validation.final_audit":
        from .validation.final_audit import main
    elif module == "pipeline.orchestrator":
        from .pipeline.orchestrator import main
    else:  # pragma: no cover - parser only supplies known module names
        raise ValueError(module)
    return main(argv)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="swepro-trans")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="promote one Stage 1 READY task into runs/<id>")
    init.add_argument("--tasks-root", type=Path, default=Path("tasks"))
    init.add_argument("--instance-id", required=True)

    package = sub.add_parser("package", help="publish an accepted revision under runs/<id>/final")
    _common_task_arguments(package)

    agent = sub.add_parser("agent", help="run one mini-SWE converter session")
    _stage_arguments(agent)
    agent.add_argument("--dry-run", action="store_true")

    pipeline = sub.add_parser("pipeline", help="run semantic, deterministic, QA and packaging gates")
    _stage_arguments(pipeline)
    pipeline.add_argument("--no-qa", action="store_true")
    pipeline.add_argument("--no-auto-repair", action="store_true", help="stop on the first failed gate")
    pipeline.add_argument("--max-revisions", type=int, default=4)
    pipeline.add_argument("--repair-count", type=int, default=0, help=argparse.SUPPRESS)
    pipeline.add_argument("--agent-timeout-seconds", type=int, default=3600, help=argparse.SUPPRESS)

    validate = sub.add_parser("validate", help="validate one functional verifier revision")
    _stage_arguments(validate)
    validate.add_argument("--execute", action="store_true")

    semantic = sub.add_parser("semantic-review", help="run the semantic Judge and binding gate")
    _stage_arguments(semantic)

    qa = sub.add_parser("qa", help="generate and replay one QA branch")
    _stage_arguments(qa)
    qa.add_argument("--kind", choices=("positive", "negative"), required=True)

    stability = sub.add_parser("stability", help="repeat deterministic Base/Gold replay and record P2P/stability gates")
    _common_task_arguments(stability)
    stability.add_argument("--repeats", type=int, default=2)

    accept = sub.add_parser("accept", help="close a revision after all gates pass")
    _common_task_arguments(accept)

    review = sub.add_parser("review", help="materialize human review files")
    _common_task_arguments(review)

    audit = sub.add_parser("final-audit", help="audit published conversions and legacy runs")
    audit_group = audit.add_mutually_exclusive_group(required=True)
    audit_group.add_argument("--task-root", type=Path)
    audit_group.add_argument("--all-runs", action="store_true")
    audit.add_argument("--write", action="store_true")
    audit.add_argument("--allow-legacy", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "task_root", None) is not None:
        args.task_root = canonical_path(args.task_root)
    if getattr(args, "revision", None) is not None:
        args.revision = canonical_path(args.revision)
    if hasattr(args, "env_file"):
        args.env_file = canonical_path(args.env_file)
    if hasattr(args, "config"):
        args.config = canonical_path(args.config)
    if args.command == "init":
        result = initialize_conversion_workspace(args.tasks_root / args.instance_id)
        print(json.dumps({"count": 1, "results": [result]}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "package":
        result = package_final(args.task_root, args.revision)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "agent":
        from .agents.runner import main as run_agent
        forwarded = ["--task-root", str(args.task_root), "--revision", str(args.revision), "--env-file", str(args.env_file), "--config", str(args.config)]
        if args.dry_run:
            forwarded.append("--dry-run")
        return run_agent(forwarded)
    if args.command == "pipeline":
        forwarded = ["--task-root", str(args.task_root), "--revision", str(args.revision), "--env-file", str(args.env_file), "--config", str(args.config)]
        if args.no_qa:
            forwarded.append("--no-qa")
        if args.no_auto_repair:
            forwarded.append("--no-auto-repair")
        forwarded.extend(["--max-revisions", str(args.max_revisions)])
        forwarded.extend(["--repair-count", str(args.repair_count), "--agent-timeout-seconds", str(args.agent_timeout_seconds)])
        return _invoke("pipeline.orchestrator", forwarded)
    if args.command == "validate":
        forwarded = ["--task-root", str(args.task_root), "--revision", str(args.revision)]
        if args.execute:
            forwarded.append("--execute")
        return _invoke("validation.revision", forwarded)
    if args.command == "semantic-review":
        return _invoke("validation.semantic", ["--task-root", str(args.task_root), "--revision", str(args.revision), "--env-file", str(args.env_file), "--config", str(args.config)])
    if args.command == "qa":
        return _invoke("qa.runner", ["--task-root", str(args.task_root), "--revision", str(args.revision), "--kind", args.kind, "--env-file", str(args.env_file), "--config", str(args.config)])
    if args.command == "stability":
        forwarded = ["--task-root", str(args.task_root), "--revision", str(args.revision), "--repeats", str(args.repeats)]
        return _invoke("validation.stability", forwarded)
    if args.command == "accept":
        return _invoke("validation.acceptance", ["--task-root", str(args.task_root), "--revision", str(args.revision)])
    if args.command == "review":
        return _invoke("reporting.human_review", ["--task-root", str(args.task_root), "--revision", str(args.revision)])
    if args.command == "final-audit":
        forwarded = []
        if args.all_runs:
            forwarded.append("--all-runs")
        else:
            forwarded.extend(["--task-root", str(args.task_root)])
        if args.write:
            forwarded.append("--write")
        if args.allow_legacy:
            forwarded.append("--allow-legacy")
        return _invoke("validation.final_audit", forwarded)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
