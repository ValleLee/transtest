import json
from types import SimpleNamespace

from swepro_trans.pipeline.repair import _repair_objectives, _selector_name_diagnostics


def test_missing_p2p_selector_feedback_names_executed_native_candidate(tmp_path):
    revision = tmp_path / "rev_001"
    tests = revision / "tests"
    tests.mkdir(parents=True)
    canonical = "/app/test/session-test.tsx | Session | current section | opens setup dialog"
    observed = "/app/test/session-test.tsx | Session | opens setup dialog"
    (tests / "config.json").write_text(json.dumps({"pass_to_pass": [canonical]}))
    hard = tmp_path / "hard_replay"
    for side in ("base", "gold"):
        output = hard / "docker" / side / "output.json"
        output.parent.mkdir(parents=True)
        output.write_text(json.dumps({"tests": [{"name": observed, "status": "PASSED"}]}))
    paths = SimpleNamespace(hard_replay_root=hard)

    diagnostics = _selector_name_diagnostics(paths, revision)
    assert len(diagnostics) == 2
    assert {item["side"] for item in diagnostics} == {"base", "gold"}
    assert all(item["observed_same_file_and_leaf"] == [{"name": observed, "status": "PASSED"}] for item in diagnostics)
    objectives = _repair_objectives("stability", {"selector_name_diagnostics": diagnostics})
    assert "never fabricate a PASS" in objectives[-1]
    assert canonical in objectives[-1]


def test_semantic_repair_uses_current_gate_and_focused_counterfactual(tmp_path):
    from swepro_trans.pipeline.repair import build_feedback

    revision = tmp_path / "revisions/rev_003"
    revision.mkdir(parents=True)
    earlier = revision.parent / "rev_002"
    earlier.mkdir()
    (earlier / "repair_feedback.json").write_text(json.dumps({
        "revision": "revisions/rev_001", "failed_gate": "semantic_review",
        "repair_objectives": ["Avoid exact intermediate return assertions"],
    }))
    (revision / "repair_feedback.json").write_text(json.dumps({
        "revision": "revisions/rev_002", "failed_gate": "semantic_review",
        "repair_objectives": ["Keep a real Python-family interpreter probe"],
    }))
    report = {"semantic_review": {
        "verdict": "FAIL", "findings": ["Current sentinel is constant"],
        "focused_counterfactual_audit": {
            "verdict": "FAIL", "assessments": [{"kind": "exact_observation_count"}],
        },
    }}
    feedback = build_feedback(SimpleNamespace(run_root=tmp_path), revision, "semantic_review", report)
    assert "prior_repair_findings" not in feedback
    assert feedback["gate_evidence"]["semantic_review"]["focused_counterfactual_audit"]["verdict"] == "FAIL"
    assert "Earlier gates have already passed on this revision" in feedback["instruction"]
    assert "Preserve the validated behavior already present in the seeded artifacts" in feedback["instruction"]


def test_replay_feedback_keeps_early_failure_after_later_success_output():
    from swepro_trans.pipeline.repair import _compact_replay_feedback

    output = (
        "===== SELECTOR: tests/test_a.py::test_failure =====\n"
        "AssertionError: specific product failure\n"
        "FAILED tests/test_a.py::test_failure\n"
        + "===== SELECTOR: tests/test_pass.py::test_ok =====\nPASSED\n" * 1200
    )
    compact = _compact_replay_feedback(output, "output")
    assert "specific product failure" in compact
    assert len(compact) < len(output) // 2



def test_hard_replay_feedback_marks_setup_hook_failure_as_non_behavioral():
    replay = {
        "status": "FAIL",
        "hard_replay": {
            "runs": {
                "base": {
                    "execution_diagnosis": {
                        "classification": "setup_failure_before_leaf_tests",
                        "failed_setup_hooks": ["test/topics/thumbs.js before all hook"],
                    }
                },
                "gold": {"execution_diagnosis": {"classification": "leaf_test_results_reported"}},
            }
        },
    }
    objectives = _repair_objectives("hard_replay", {"hard_replay": replay})
    diagnosis = next(item for item in objectives if "before any leaf tests ran" in item)
    assert "not evidence that Base violates or Gold satisfies" in diagnosis
    assert "keep the task unaccepted" in diagnosis
    assert "original P2P tests" in diagnosis
