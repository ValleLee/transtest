"""QA retries carry the previous semantic rejection into the next session."""
import json

from swepro_trans.qa.session import _previous_candidate_feedback


def test_retry_feedback_includes_judge_reason_and_replay(tmp_path):
    candidate = tmp_path / "candidates" / "positive_001"
    replay = tmp_path / "replay" / "positive_001"
    candidate.mkdir(parents=True)
    replay.mkdir(parents=True)
    (candidate / "candidate_metadata.json").write_text(json.dumps({
        "design_axis": "error recognition predicate",
        "explanation": "Uses an error name instead of instanceof",
    }))
    (candidate / "judge.json").write_text(json.dumps({
        "verdict": "INVALID",
        "reasons": ["same error propagation layer as the reference"],
    }))
    (replay / "replay_result.json").write_text(json.dumps({
        "original": {"pass": True},
        "functional": {"pass": True},
    }))

    feedback = _previous_candidate_feedback(tmp_path, "positive", 2)

    assert feedback == [{
        "candidate_index": 1,
        "design_axis": "error recognition predicate",
        "explanation": "Uses an error name instead of instanceof",
        "judge_verdict": "INVALID",
        "judge_reasons": ["same error propagation layer as the reference"],
        "original_pass": True,
        "functional_pass": True,
    }]


def test_candidate_step_limit_uses_role_specific_budget_with_legacy_fallback():
    from swepro_trans.qa.session import _candidate_step_limit

    config = {"agent": {"max_turns": 80, "solver_turns": 100, "mutation_turns": 120}}
    assert _candidate_step_limit("positive", config) == 100
    assert _candidate_step_limit("negative", config) == 120
    assert _candidate_step_limit("positive", {"agent": {"max_turns": 80}}) == 80
