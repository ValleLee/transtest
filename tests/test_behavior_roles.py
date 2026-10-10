import json
from types import SimpleNamespace

from swepro_trans.validation import behavior_roles


def _paths(tmp_path):
    run = tmp_path / "run"
    revision = run / "attempts" / "attempt_001" / "intermediate" / "converter" / "revisions" / "rev_001"
    replay = run / "attempts" / "attempt_001" / "intermediate" / "validation" / "hard_replay"
    validation = run / "attempts" / "attempt_001" / "intermediate" / "validation"
    revision.mkdir(parents=True)
    for label in ("base", "gold"):
        (replay / "docker" / label).mkdir(parents=True)
    return SimpleNamespace(
        run_root=run,
        hard_replay_root=replay,
        hard_replay_path=replay / "result.json",
        validation_root=validation,
    ), revision


def _write_output(path, statuses):
    path.write_text(json.dumps({"tests": [
        {"name": selector, "status": status} for selector, status in statuses.items()
    ]}))


def test_audit_separates_delta_and_converted_regression(tmp_path, monkeypatch):
    paths, revision = _paths(tmp_path)
    trace = {
        "task_disposition": "convertible",
        "f2p_accounting": [
            {
                "source_f2p": "historical::delta",
                "behavior_classification": "p_supported_behavior",
                "base_behavior_status": "changed_or_missing",
                "decision": "rewrite",
                "emitted_tests": ["functional::delta"],
            },
            {
                "source_f2p": "historical::regression",
                "behavior_classification": "base_regression_behavior",
                "base_behavior_status": "already_satisfies",
                "decision": "rewrite",
                "emitted_tests": ["functional::regression"],
            },
        ],
    }
    (revision / "conversion_trace.json").write_text(json.dumps(trace))
    _write_output(paths.hard_replay_root / "docker/base/output.json", {
        "functional::delta": "FAILED",
        "functional::regression": "PASSED",
    })
    _write_output(paths.hard_replay_root / "docker/gold/output.json", {
        "functional::delta": "PASSED",
        "functional::regression": "PASSED",
    })
    monkeypatch.setattr(behavior_roles, "resolve_task", lambda _: paths)

    result = behavior_roles.audit(tmp_path, revision)

    assert result["status"] == "PASS"
    assert result["role_counts"]["functional_delta"] == 1
    assert result["role_counts"]["converted_regression"] == 1


def test_audit_rejects_selector_shared_across_roles(tmp_path, monkeypatch):
    paths, revision = _paths(tmp_path)
    trace = {
        "task_disposition": "convertible",
        "f2p_accounting": [
            {
                "source_f2p": "historical::delta",
                "behavior_classification": "p_supported_behavior",
                "base_behavior_status": "changed_or_missing",
                "decision": "merge",
                "emitted_tests": ["functional::shared"],
            },
            {
                "source_f2p": "historical::regression",
                "behavior_classification": "base_regression_behavior",
                "base_behavior_status": "already_satisfies",
                "decision": "merge",
                "emitted_tests": ["functional::shared"],
            },
        ],
    }
    (revision / "conversion_trace.json").write_text(json.dumps(trace))
    _write_output(paths.hard_replay_root / "docker/base/output.json", {"functional::shared": "FAILED"})
    _write_output(paths.hard_replay_root / "docker/gold/output.json", {"functional::shared": "PASSED"})
    monkeypatch.setattr(behavior_roles, "resolve_task", lambda _: paths)

    result = behavior_roles.audit(tmp_path, revision)

    assert result["status"] == "FAIL"
    assert any("shared by Base-existing and changed/missing" in error for error in result["errors"])


def test_audit_normalizes_cross_language_pass_fail_statuses(tmp_path, monkeypatch):
    paths, revision = _paths(tmp_path)
    trace = {
        "task_disposition": "convertible",
        "f2p_accounting": [
            {
                "source_f2p": "historical::delta",
                "behavior_classification": "p_supported_behavior",
                "base_behavior_status": "changed_or_missing",
                "decision": "rewrite",
                "emitted_tests": ["functional::delta"],
            },
            {
                "source_f2p": "historical::regression",
                "behavior_classification": "base_regression_behavior",
                "base_behavior_status": "already_satisfies",
                "decision": "rewrite",
                "emitted_tests": ["functional::regression"],
            },
        ],
    }
    (revision / "conversion_trace.json").write_text(json.dumps(trace))
    _write_output(paths.hard_replay_root / "docker/base/output.json", {
        "functional::delta": "FAIL",
        "functional::regression": "PASS",
    })
    _write_output(paths.hard_replay_root / "docker/gold/output.json", {
        "functional::delta": "OK",
        "functional::regression": "PASSED",
    })
    monkeypatch.setattr(behavior_roles, "resolve_task", lambda _: paths)

    result = behavior_roles.audit(tmp_path, revision)

    assert result["status"] == "PASS"
    assert result["rows"][0]["base_selector_statuses"]["functional::delta"] == "FAILED"
    assert result["rows"][1]["base_selector_statuses"]["functional::regression"] == "PASSED"


def test_base_regression_never_triggers_specification_enrichment():
    from swepro_trans.pipeline.orchestrator import _row_requires_specification_enrichment

    row = {
        "behavior_classification": "base_regression_behavior",
        "decision": "rewrite",
        "problem_statement_support": "The Problem Statement does not state serialization.",
    }
    assert not _row_requires_specification_enrichment(row, addendum_text="")


def test_missing_product_behavior_triggers_specification_enrichment():
    from swepro_trans.pipeline.orchestrator import _row_requires_specification_enrichment

    row = {
        "behavior_classification": "missing_product_behavior",
        "decision": "specification_gap",
        "problem_statement_support": "The Problem Statement does not state the observable outcome.",
        "specification_proposal": "Show the updated value in the public output.",
    }
    assert _row_requires_specification_enrichment(row, addendum_text="")
    assert not _row_requires_specification_enrichment(
        row, addendum_text="## Additional observable behavior\n\nShow the updated value in the public output.\n"
    )


def test_audit_splits_mixed_obligations_by_selector(tmp_path, monkeypatch):
    paths, revision = _paths(tmp_path)
    trace = {"task_disposition": "convertible", "f2p_accounting": [{
        "source_f2p": "historical::mixed",
        "behavior_classification": "p_supported_behavior",
        "base_behavior_status": "changed_or_missing",
        "decision": "rewrite",
        "emitted_tests": ["functional::delta", "functional::regression"],
        "obligation_accounting": [
            {"scope": "product_behavior", "disposition": "preserved",
             "base_behavior_status": "changed_or_missing", "emitted_tests": ["functional::delta"]},
            {"scope": "product_behavior", "disposition": "preserved",
             "base_behavior_status": "already_satisfies", "emitted_tests": ["functional::regression"]},
        ],
    }]}
    (revision / "conversion_trace.json").write_text(json.dumps(trace))
    _write_output(paths.hard_replay_root / "docker/base/output.json", {
        "functional::delta": "FAILED", "functional::regression": "PASSED",
    })
    _write_output(paths.hard_replay_root / "docker/gold/output.json", {
        "functional::delta": "PASSED", "functional::regression": "PASSED",
    })
    monkeypatch.setattr(behavior_roles, "resolve_task", lambda _: paths)

    result = behavior_roles.audit(tmp_path, revision)

    assert result["status"] == "PASS"
    assert result["rows"][0]["verification_role"] == "mixed"
    assert result["role_counts"]["functional_delta"] == 1
    assert result["role_counts"]["converted_regression"] == 1


def test_audit_reads_top_level_harbor_result_arrays(tmp_path, monkeypatch):
    paths, revision = _paths(tmp_path)
    selector = "functional::delta"
    trace = {"task_disposition": "convertible", "f2p_accounting": [{
        "source_f2p": "historical::delta",
        "behavior_classification": "p_supported_behavior",
        "base_behavior_status": "changed_or_missing",
        "decision": "rewrite",
        "emitted_tests": [selector],
    }]}
    (revision / "conversion_trace.json").write_text(json.dumps(trace))
    for label, status in (("base", "FAILED"), ("gold", "PASSED")):
        (paths.hard_replay_root / "docker" / label / "output.json").write_text(
            json.dumps([{"name": selector, "status": status}])
        )
    monkeypatch.setattr(behavior_roles, "resolve_task", lambda _: paths)

    result = behavior_roles.audit(tmp_path, revision)

    assert result["status"] == "PASS"
    assert result["base_output_source"].endswith("base/output.json")
    assert result["gold_output_source"].endswith("gold/output.json")
    assert result["rows"][0]["base_selector_statuses"][selector] == "FAILED"


def test_audit_reads_harbor_results_json(tmp_path, monkeypatch):
    paths, revision = _paths(tmp_path)
    trace = {"task_disposition": "convertible", "f2p_accounting": [{
        "source_f2p": "historical::delta",
        "behavior_classification": "p_supported_behavior",
        "base_behavior_status": "changed_or_missing",
        "decision": "rewrite",
        "emitted_tests": ["functional::delta"],
    }]}
    (revision / "conversion_trace.json").write_text(json.dumps(trace))
    _write_output(paths.hard_replay_root / "docker/base/results.json", {"functional::delta": "FAILED"})
    _write_output(paths.hard_replay_root / "docker/gold/results.json", {"functional::delta": "PASSED"})
    monkeypatch.setattr(behavior_roles, "resolve_task", lambda _: paths)

    result = behavior_roles.audit(tmp_path, revision)

    assert result["status"] == "PASS"
    assert result["base_output_source"].endswith("results.json")

def test_missing_public_method_on_base_is_a_delta_when_compile_diagnostic_maps_to_selector(tmp_path, monkeypatch):
    paths, revision = _paths(tmp_path)
    selector = "TestFilterByCvssOver"
    trace = {"task_disposition": "convertible", "f2p_accounting": [{
        "source_f2p": "historical::FilterByCvssOver",
        "behavior_classification": "p_supported_behavior",
        "base_behavior_status": "changed_or_missing",
        "decision": "rewrite",
        "emitted_tests": [selector],
    }]}
    (revision / "conversion_trace.json").write_text(json.dumps(trace))
    test_source = revision / "tests" / "verifier_test.go"
    test_source.parent.mkdir()
    test_source.write_text(
        "package models\n"
        "func TestFilterByCvssOver(t *testing.T) {\n"
        "    _ = input.FilterByCvssOver(7.0)\n"
        "}\n"
    )
    _write_output(paths.hard_replay_root / "docker/base/output.json", {selector: "ERROR"})
    _write_output(paths.hard_replay_root / "docker/gold/output.json", {selector: "PASSED"})
    paths.hard_replay_path.write_text(json.dumps({"runs": {"base": {
        "returncode": 1,
        "output": "models/verifier_test.go:3:11: input.FilterByCvssOver undefined "
                  "(type VulnInfos has no field or method FilterByCvssOver)\n",
    }}}))
    monkeypatch.setattr(behavior_roles, "resolve_task", lambda _: paths)

    result = behavior_roles.audit(tmp_path, revision)

    assert result["status"] == "PASS"
    assert result["rows"][0]["base_selector_statuses_raw"][selector] == "ERROR"
    assert result["rows"][0]["base_selector_statuses"][selector] == "MISSING_PUBLIC_API"
    assert result["missing_public_api_evidence"][selector]["symbol"] == "FilterByCvssOver"


def test_unrelated_base_compile_error_does_not_count_as_delta(tmp_path, monkeypatch):
    paths, revision = _paths(tmp_path)
    selector = "TestFilterByCvssOver"
    trace = {"task_disposition": "convertible", "f2p_accounting": [{
        "source_f2p": "historical::FilterByCvssOver",
        "behavior_classification": "p_supported_behavior",
        "base_behavior_status": "changed_or_missing",
        "decision": "rewrite",
        "emitted_tests": [selector],
    }]}
    (revision / "conversion_trace.json").write_text(json.dumps(trace))
    test_source = revision / "tests" / "verifier_test.go"
    test_source.parent.mkdir()
    test_source.write_text(
        "package models\n"
        "func TestDifferentBehavior(t *testing.T) {\n"
        "    _ = input.FilterByCvssOver(7.0)\n"
        "}\n"
    )
    _write_output(paths.hard_replay_root / "docker/base/output.json", {selector: "ERROR"})
    _write_output(paths.hard_replay_root / "docker/gold/output.json", {selector: "PASSED"})
    paths.hard_replay_path.write_text(json.dumps({"runs": {"base": {
        "returncode": 1,
        "output": "models/verifier_test.go:3:11: input.FilterByCvssOver undefined "
                  "(type VulnInfos has no field or method FilterByCvssOver)\n",
    }}}))
    monkeypatch.setattr(behavior_roles, "resolve_task", lambda _: paths)

    result = behavior_roles.audit(tmp_path, revision)

    assert result["status"] == "FAIL"
    assert result["rows"][0]["base_selector_statuses"][selector] == "ERROR"
    assert not result["missing_public_api_evidence"]


def test_base_environment_error_does_not_count_as_missing_public_api(tmp_path, monkeypatch):
    paths, revision = _paths(tmp_path)
    selector = "functional::delta"
    trace = {"task_disposition": "convertible", "f2p_accounting": [{
        "source_f2p": "historical::delta",
        "behavior_classification": "p_supported_behavior",
        "base_behavior_status": "changed_or_missing",
        "decision": "rewrite",
        "emitted_tests": [selector],
    }]}
    (revision / "conversion_trace.json").write_text(json.dumps(trace))
    _write_output(paths.hard_replay_root / "docker/base/output.json", {selector: "ERROR"})
    _write_output(paths.hard_replay_root / "docker/gold/output.json", {selector: "PASSED"})
    paths.hard_replay_path.write_text(json.dumps({"runs": {"base": {
        "returncode": 1,
        "output": "failed to connect to Docker daemon\n",
    }}}))
    monkeypatch.setattr(behavior_roles, "resolve_task", lambda _: paths)

    result = behavior_roles.audit(tmp_path, revision)

    assert result["status"] == "FAIL"
    assert result["rows"][0]["base_selector_statuses"][selector] == "ERROR"
    assert not result["missing_public_api_evidence"]
