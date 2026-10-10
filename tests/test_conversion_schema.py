from swepro_trans.conversion_schema import coerce_boolean_literal


def test_coerce_boolean_literal_accepts_only_unambiguous_literals() -> None:
    assert coerce_boolean_literal("true") is True
    assert coerce_boolean_literal(" YES ") is True
    assert coerce_boolean_literal("1") is True
    assert coerce_boolean_literal("false") is False
    assert coerce_boolean_literal("No") is False
    assert coerce_boolean_literal("0") is False
    assert coerce_boolean_literal(True) is True

    uncertain = "probably false because Gold differs"
    assert coerce_boolean_literal(uncertain) == uncertain


def test_converted_selector_groups_separates_final_harbor_roles() -> None:
    from swepro_trans.conversion_schema import converted_selector_groups

    trace = {"f2p_accounting": [
        {"decision": "rewrite", "behavior_classification": "p_supported_behavior",
         "base_behavior_status": "changed_or_missing", "emitted_tests": ["delta::one"]},
        {"decision": "merge", "behavior_classification": "base_regression_behavior",
         "base_behavior_status": "already_satisfies", "emitted_tests": ["regression::one"]},
        {"decision": "drop", "emitted_tests": []},
    ]}
    assert converted_selector_groups(trace) == (["delta::one"], ["regression::one"])


def test_p_supported_new_public_surface_may_be_missing_in_base() -> None:
    from swepro_trans.conversion_schema import classification_errors

    row = {
        "source_f2p": "historical::new_public_type",
        "behavior_classification": "p_supported_behavior",
        "problem_statement_quotes": ["Switch to a `WidgetFamilies` class for consistent parsing."],
        "decision": "rewrite",
        "rationale": "P names a public type and this selector tests its behavior.",
        "base_behavior_status": "changed_or_missing",
        "base_repo_observable": False,
        "gold_only_binding": False,
        "observable_surface": "P-named public type",
        "preservation_evidence": "The emitted selector exercises its behavior.",
        "behavioral_obligations": ["ordered parsing"],
        "obligation_accounting": [{
            "id": "O1", "obligation": "ordered parsing",
            "scope": "product_behavior", "disposition": "preserved",
            "base_behavior_status": "changed_or_missing",
            "emitted_tests": ["converted::ordered_parsing"],
            "evidence": "P names the type and ordered parsing behavior.",
            "rationale": "The type is new in this task.",
        }],
        "emitted_tests": ["converted::ordered_parsing"],
    }
    assert classification_errors(row) == []
    row["rationale"] = ""
    assert any("rationale is empty" in error for error in classification_errors(row))
    row["rationale"] = "P names a public type and this selector tests its behavior."
    row["base_behavior_status"] = "already_satisfies"
    assert any("existing Base" in error for error in classification_errors(row))


def test_product_obligation_requires_own_base_behavior_status() -> None:
    from swepro_trans.conversion_schema import classification_errors

    row = {
        "source_f2p": "historical::mixed",
        "behavior_classification": "p_supported_behavior",
        "decision": "rewrite",
        "rationale": "The source test covers a changed product field.",
        "base_behavior_status": "changed_or_missing",
        "base_repo_observable": True,
        "gold_only_binding": False,
        "observable_surface": "public database configuration",
        "preservation_evidence": "The emitted test checks both changed and existing fields.",
        "behavioral_obligations": ["new cloud fields", "existing global fields"],
        "obligation_accounting": [{
            "id": "O1", "obligation": "existing global fields",
            "scope": "product_behavior", "disposition": "preserved",
            "emitted_tests": ["converted::global_fields"],
            "evidence": "The source F2P assertion reads the global fields.",
            "rationale": "This case is Base-existing.",
        }],
        "emitted_tests": ["converted::global_fields"],
    }
    errors = classification_errors(row)
    assert any("base_behavior_status must be explicit" in error for error in errors)
    row["obligation_accounting"][0]["base_behavior_status"] = "already_satisfies"
    assert not any("base_behavior_status must be explicit" in error for error in classification_errors(row))


def test_converted_selector_groups_split_mixed_obligations_in_one_historical_test() -> None:
    from swepro_trans.conversion_schema import converted_selector_groups

    trace = {"f2p_accounting": [{
        "source_f2p": "historical::mixed",
        "decision": "rewrite",
        "behavior_classification": "p_supported_behavior",
        "base_behavior_status": "changed_or_missing",
        "emitted_tests": ["functional::delta", "functional::regression"],
        "obligation_accounting": [
            {"scope": "product_behavior", "disposition": "preserved",
             "base_behavior_status": "changed_or_missing", "emitted_tests": ["functional::delta"]},
            {"scope": "product_behavior", "disposition": "preserved",
             "base_behavior_status": "already_satisfies", "emitted_tests": ["functional::regression"]},
        ],
    }]}
    assert converted_selector_groups(trace) == (["functional::delta"], ["functional::regression"])


def test_converted_selector_groups_uses_only_f2p_accounting() -> None:
    from swepro_trans.conversion_schema import converted_selector_groups

    trace = {
        "f2p_accounting": [{
            "decision": "rewrite", "base_behavior_status": "changed_or_missing",
            "emitted_tests": ["delta::new"],
        }],
        "p2p_accounting": {
            "converted_to_regression": [{"emitted_tests": ["p2p::must_not_be_added"]}],
            "excluded": [{"selector": "p2p::must_not_be_removed", "preserved_by": "delta::new"}],
        },
    }
    assert converted_selector_groups(trace) == (["delta::new"], [])


def test_converted_selector_groups_ignores_p2p_accounting_aliases() -> None:
    from swepro_trans.conversion_schema import converted_selector_groups

    trace = {
        "f2p_accounting": [],
        "p2p_accounting": {
            "excluded": [{"selector": "old::one", "converted_regression": "new::one"}],
            "converted_regressions": [{"original": "old::one", "converted": "new::one"}],
        },
    }
    assert converted_selector_groups(trace) == ([], [])
