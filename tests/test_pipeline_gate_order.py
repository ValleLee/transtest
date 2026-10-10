import json
from pathlib import Path
from types import SimpleNamespace

from swepro_trans.pipeline import orchestrator


def test_non_discriminative_semantic_failure_precedes_docker_replay(tmp_path, monkeypatch) -> None:
    """An invalid semantic mapping must not spend revisions fixing its Docker fixture."""
    original = tmp_path / "original"
    original.mkdir()
    revisions = tmp_path / "intermediate" / "converter" / "revisions"
    revision = revisions / "rev_001"
    revision.mkdir(parents=True)
    (revision / "conversion_trace.json").write_text(
        json.dumps({"task_disposition": "non_discriminative", "f2p_accounting": []})
    )
    config = tmp_path / "config.yaml"
    config.write_text("{}\n")
    validation = tmp_path / "intermediate" / "validation"
    paths = SimpleNamespace(
        original=original,
        revisions_root=revisions,
        run_root=tmp_path,
        attempt_root=tmp_path,
        state_path=tmp_path / "state.json",
        semantic_review_path=validation / "semantic" / "review.json",
        hard_replay_path=validation / "hard_replay" / "result.json",
        behavior_role_audit_path=validation / "behavior_roles" / "audit.json",
        stability_path=validation / "stability" / "result.json",
        acceptance_path=validation / "acceptance.json",
        specification_addendum_path=tmp_path / "source" / "specification_addendum.md",
        validation_root=validation,
        qa_branch=lambda role: tmp_path / "intermediate" / "qa" / role,
    )
    calls = []

    def fake_run(command, cwd, **kwargs):
        calls.append(command)
        if "swepro_trans.validation.revision" in command:
            if "--execute" in command:
                raise AssertionError("Docker replay ran before semantic review")
            return 0, json.dumps({"status": "PASS"})
        if "swepro_trans.validation.semantic" in command:
            return 3, json.dumps({"verdict": "FAIL", "review_mode": "semantic", "findings": ["causal trigger bypassed"]})
        raise AssertionError(command)

    monkeypatch.setattr(orchestrator, "canonical_path", Path)
    monkeypatch.setattr(orchestrator, "resolve_task", lambda _: paths)
    monkeypatch.setattr(orchestrator, "_attempt_is_immutable", lambda *_: False)
    monkeypatch.setattr(orchestrator, "_update_attempt_state", lambda *_, **__: None)
    monkeypatch.setattr(orchestrator, "run", fake_run)
    monkeypatch.setattr(orchestrator, "_retry_or_finish", lambda **kwargs: kwargs["code"])

    result = orchestrator.main([
        "--task-root", str(tmp_path), "--revision", str(revision),
        "--config", str(config), "--no-auto-repair",
    ])
    assert result == 3
    assert [command[2] for command in calls] == [
        "swepro_trans.validation.revision", "swepro_trans.validation.semantic",
    ]
