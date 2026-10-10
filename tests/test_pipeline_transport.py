from pathlib import Path
from types import SimpleNamespace

from swepro_trans.pipeline import orchestrator


def test_semantic_judge_transport_does_not_spawn_converter_repair(monkeypatch) -> None:
    def finish(root, report, code, revision):
        assert report["status"] == "semantic_judge_unavailable"
        return code

    def unexpected_repair(*args, **kwargs):
        raise AssertionError("Judge transport failure must not become converter feedback")

    monkeypatch.setattr(orchestrator, "finish", finish)
    monkeypatch.setattr(orchestrator, "next_revision", unexpected_repair)
    report = {"status": "started", "semantic_review": {"failure_classification": "judge_transport"}}
    result = orchestrator._retry_or_finish(
        args=SimpleNamespace(auto_repair=True, repair_count=0, max_revisions=4),
        paths=SimpleNamespace(attempt_root=Path("/tmp/example")),
        root=Path("/tmp/example"), revision=Path("/tmp/example/rev_001"),
        report=report, code=3, gate="semantic_review",
    )
    assert result == 3


def test_mixed_semantic_feedback_keeps_existing_addendum_behavior() -> None:
    from swepro_trans.pipeline.repair import _repair_objectives

    objectives = _repair_objectives("semantic_review", {"semantic_review": {
        "findings": ["round-trip does not prove rendering"],
        "under_conversion": ["rendering assertion is too weak"],
        "specification_gaps": [{"detail": "accepted addendum already describes rendering"}],
    }})
    assert any("keep its rewrite/merge mapping" in item for item in objectives)
    assert any("strengthen the emitted test" in item for item in objectives)


def test_top_level_pipeline_forwards_resume_count_and_agent_timeout(monkeypatch, tmp_path) -> None:
    from swepro_trans import verifier_conversion

    called = {}
    def invoke(module, argv):
        called["module"] = module
        called["argv"] = argv
        return 0
    monkeypatch.setattr(verifier_conversion, "_invoke", invoke)
    assert verifier_conversion.main([
        "pipeline", "--task-root", str(tmp_path / "task"),
        "--revision", str(tmp_path / "rev_002"),
        "--repair-count", "1", "--agent-timeout-seconds", "3600",
    ]) == 0
    assert called["module"] == "pipeline.orchestrator"
    assert called["argv"][-4:] == ["--repair-count", "1", "--agent-timeout-seconds", "3600"]


def test_qa_replay_infrastructure_failure_does_not_spawn_converter_repair(monkeypatch) -> None:
    def finish(root, report, code, revision):
        assert report["status"] == "qa_infrastructure_failure"
        assert "converter was not asked" in report["terminal_reason"]
        assert code == 10
        return code

    def unexpected_repair(*args, **kwargs):
        raise AssertionError("QA replay infrastructure failure must not become converter feedback")

    monkeypatch.setattr(orchestrator, "finish", finish)
    monkeypatch.setattr(orchestrator, "next_revision", unexpected_repair)
    report = {
        "status": "rejected_positive_qa",
        "positive_qa": {"mode": "replay_infrastructure_failure"},
    }
    result = orchestrator._retry_or_finish(
        args=SimpleNamespace(auto_repair=True, repair_count=0, max_revisions=4),
        paths=SimpleNamespace(attempt_root=Path("/tmp/example")),
        root=Path("/tmp/example"), revision=Path("/tmp/example/rev_001"),
        report=report, code=5, gate="positive_qa",
    )
    assert result == 10
