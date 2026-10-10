"""A replay result cannot replace the semantic Solution/Mutation Judge."""
from swepro_trans.qa.runner import _deterministic_candidate_fallback


def test_positive_replay_cannot_certify_solution_without_judge(tmp_path):
    patch = tmp_path / "candidate.patch"
    patch.write_text("diff --git a/a b/a\n", encoding="utf-8")
    result = _deterministic_candidate_fallback(
        paths=None,
        kind="positive",
        patch=patch,
        metadata={"explanation": "Different from Gold"},
        replay={
            "status": "pass",
            "patches_applied": True,
            "original": {"pass": True},
            "functional": {"pass": True},
        },
    )
    assert result["verdict"] == "INVALID"
    assert result["review_mode"] == "deterministic_fallback_rejection"


def test_negative_replay_cannot_certify_single_semantic_mutation_without_judge(tmp_path):
    patch = tmp_path / "candidate.patch"
    patch.write_text("diff --git a/a b/a\n", encoding="utf-8")
    result = _deterministic_candidate_fallback(
        paths=None,
        kind="negative",
        patch=patch,
        metadata={"candidate_type": "semantic_mutation", "violated_behavior": "wrong output"},
        replay={"status": "pass", "patches_applied": True, "functional": {"pass": False}},
    )
    assert result["verdict"] == "OFF_TARGET"
    assert result["review_mode"] == "deterministic_fallback_rejection"


def test_negative_judge_must_ground_mutation_in_p_not_trace():
    from swepro_trans.qa.runner import _ground_negative_verdict

    verdict = {
        "verdict": "RELEVANT_NON_EQUIVALENT",
        "targeted_source_f2p": "test_parse_metadata",
        "violated_behavior": "Rejects a historical whitespace variant",
        "p_contract_quote": "historical whitespace variant",
        "counterfactual_valid_alternative": "Own canonical format still round-trips",
    }
    p = "Metadata must survive a stable editable Markdown round trip."
    assert _ground_negative_verdict(verdict, p)["verdict"] == "OFF_TARGET"
    verdict["p_contract_quote"] = "Metadata must survive"
    assert _ground_negative_verdict(verdict, p)["verdict"] == "RELEVANT_NON_EQUIVALENT"


def test_p_valid_negative_rejected_by_verifier_stops_candidate_search():
    from swepro_trans.qa.runner import _collect_candidate_attempts, _verifier_false_positive

    clean_replay = {
        "status": "pass", "patches_applied": True,
        "infrastructure_failure": False, "functional": {"pass": False},
    }
    assert _verifier_false_positive("negative", {"verdict": "EQUIVALENT"}, clean_replay)
    assert not _verifier_false_positive("negative", {"verdict": "RELEVANT_NON_EQUIVALENT"}, clean_replay)
    assert not _verifier_false_positive("negative", {"verdict": "EQUIVALENT"}, {**clean_replay, "infrastructure_failure": True})

    evaluated = []
    def evaluate(index):
        evaluated.append(index)
        return {"status": "verifier_false_positive" if index == 1 else "pass"}
    assert _collect_candidate_attempts(5, evaluate) == [{"status": "verifier_false_positive"}]
    assert evaluated == [1]


def test_p_valid_positive_rejected_by_verifier_is_false_positive():
    from swepro_trans.qa.runner import _verifier_false_positive

    replay = {"status": "fail", "patches_applied": True, "infrastructure_failure": False, "functional": {"pass": False}}
    assert _verifier_false_positive("positive", {"verdict": "VALID"}, replay)
    assert not _verifier_false_positive("positive", {"verdict": "INVALID"}, replay)
    assert not _verifier_false_positive("positive", {"verdict": "VALID"}, {**replay, "patches_applied": False})


def test_infrastructure_replays_retry_same_candidate_without_spending_candidate_slots():
    from swepro_trans.qa.runner import _collect_candidate_attempts

    calls = []
    def evaluate(index):
        calls.append(index)
        if len(calls) < 3:
            return {"status": "infrastructure_failure", "candidate_index": index}
        return {"status": "pass", "candidate_index": index}

    attempts = _collect_candidate_attempts(3, evaluate, infrastructure_retries=2)
    assert calls == [1, 1, 1]
    assert attempts == [{"status": "pass", "candidate_index": 1, "infrastructure_retries": 2}]


def test_persistent_infrastructure_failure_stops_without_spending_more_candidates():
    from swepro_trans.qa.runner import _collect_candidate_attempts

    calls = []
    def evaluate(index):
        calls.append(index)
        return {"status": "infrastructure_failure", "candidate_index": index}

    attempts = _collect_candidate_attempts(5, evaluate, infrastructure_retries=2)
    assert calls == [1, 1, 1]
    assert attempts == [{"status": "infrastructure_failure", "candidate_index": 1, "infrastructure_retries": 2}]
