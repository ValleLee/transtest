from types import SimpleNamespace

from swepro_trans.pipeline.orchestrator import (
    _row_requires_specification_enrichment,
    _write_specification_addendum,
)


def _gap(proposal):
    return {
        "behavior_classification": "missing_product_behavior",
        "decision": "specification_gap",
        "specification_proposal": proposal,
    }


def test_later_gap_appends_without_replacing_or_duplicating_prior_behavior(tmp_path):
    path = tmp_path / "specification_addendum.md"
    paths = SimpleNamespace(specification_addendum_path=path)
    first = "While loading, the current-session actions are unavailable."
    second = "When there is only one session, sign out other sessions is unavailable."

    assert _row_requires_specification_enrichment(_gap(first), addendum_text="")
    _write_specification_addendum(paths, [{"proposal": first}])
    original = path.read_text()
    assert not _row_requires_specification_enrichment(_gap(first), addendum_text=original)
    assert _row_requires_specification_enrichment(_gap(second), addendum_text=original)

    _write_specification_addendum(paths, [{"proposal": first}, {"proposal": second}])
    combined = path.read_text()
    assert combined.startswith(original.rstrip())
    assert combined.count(first) == 1
    assert combined.count(second) == 1
    assert combined.count("## Additional observable behavior") == 2
    assert not _row_requires_specification_enrichment(_gap(second), addendum_text=combined)


def test_base_regression_does_not_expand_specification(tmp_path):
    row = {
        "behavior_classification": "base_regression_behavior",
        "decision": "rewrite",
        "problem_statement_support": "P does not state this existing behavior",
        "specification_proposal": "Existing output stays the same.",
    }
    assert not _row_requires_specification_enrichment(row, addendum_text="")


def test_addendum_rejects_historical_test_commentary(tmp_path):
    import pytest
    from swepro_trans.conversion_schema import specification_addendum_errors

    path = tmp_path / "specification_addendum.md"
    paths = SimpleNamespace(specification_addendum_path=path)
    commentary = (
        "Historical Hypothesis property for the P-named parser. "
        "The old str(parsed) check is an internal robustness probe with no independent product outcome."
    )
    with pytest.raises(ValueError, match="meta-language"):
        _write_specification_addendum(paths, [{"proposal": commentary}])
    assert not path.exists()

    valid = "A font family collection renders family names in order, separated by a comma and a space."
    _write_specification_addendum(paths, [{"proposal": valid}])
    assert specification_addendum_errors(path.read_text()) == []


def test_rejected_meta_addendum_proposal_has_actionable_repair_feedback(tmp_path):
    from swepro_trans.pipeline.repair import build_feedback

    revision = tmp_path / "rev_001"
    feedback = build_feedback(
        SimpleNamespace(run_root=tmp_path), revision, "artifact_contract",
        {"artifact_contract": {"status": "FAIL", "contract": {
            "status": "FAIL",
            "errors": ["refusing to write meta-language into specification addendum"],
        }}},
    )
    assert feedback["failed_gate"] == "artifact_contract"
    assert any("product behavior" in objective for objective in feedback["repair_objectives"])
    assert any("internal-probe" in objective for objective in feedback["repair_objectives"])


def test_provenance_prose_cannot_promote_p_supported_test_description():
    row = {
        "behavior_classification": "p_supported_behavior",
        "decision": "rewrite",
        "problem_statement_support": "The property smoke check is not explicit in P, while parsing behavior is.",
        "behavior_intent": "Verify that parsing yields non-empty family entries.",
        "specification_proposal": None,
    }
    assert not _row_requires_specification_enrichment(row, addendum_text="")
