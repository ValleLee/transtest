"""Judge list fields must not crash the semantic gate on text responses."""
import pytest

from swepro_trans.validation.semantic import _normalize_judge_lists, scope_review_findings


def test_text_findings_are_normalized_for_followup_audits():
    result = _normalize_judge_lists(
        {"verdict": "FAIL", "findings": "Unexpected binding", "binding_risks": None},
        "findings", "binding_risks",
    )
    result["findings"].append("Counterfactual failure")
    result["binding_risks"].extend(["private entrypoint"])
    assert result["findings"] == ["Unexpected binding", "Counterfactual failure"]
    assert result["binding_risks"] == ["private entrypoint"]


def test_malformed_list_shape_fails_as_protocol_error():
    with pytest.raises(ValueError, match="findings must be an array or text"):
        _normalize_judge_lists({"verdict": "PASS", "findings": {"bad": "shape"}}, "findings")


def test_p_only_under_conversion_without_historical_f2p_selector_is_nonblocking():
    result = {
        "verdict": "FAIL",
        "findings": ["P-only request outcome is not verified"],
        "unsupported_requirements": [], "binding_risks": [],
        "mapping_gaps": ["P requires requests not be blocked after recovery"],
        "under_conversion": ["The emitted test does not assert request.is_blocked"],
        "hidden_contracts": [], "unjustified_drops": [],
        "specification_gaps": [{"gap": "P requests should not be blocked"}],
        "rationale": "A P-only outcome is missing.",
    }
    scoped = scope_review_findings(result, [{"source_f2p": "tests/unit/test_cache.py::test_bad_cache"}])
    assert scoped["verdict"] == "PASS"
    assert scoped["mapping_gaps"] == []
    assert scoped["under_conversion"] == []
    assert scoped["specification_gaps"] == []
    assert len(scoped["out_of_scope_review_findings"]) == 3


def test_under_conversion_with_historical_f2p_selector_still_blocks():
    selector = "tests/unit/test_cache.py::test_bad_cache"
    result = {
        "verdict": "FAIL", "findings": [f"{selector} misses the assertion"],
        "mapping_gaps": [f"{selector} assertion is absent from emitted test"],
        "under_conversion": [], "unsupported_requirements": [],
        "binding_risks": [], "hidden_contracts": [],
        "unjustified_drops": [], "specification_gaps": [],
    }
    scoped = scope_review_findings(result, [{"source_f2p": selector}])
    assert scoped["verdict"] == "FAIL"
    assert scoped["mapping_gaps"]
    assert "out_of_scope_review_findings" not in scoped
