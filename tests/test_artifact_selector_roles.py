from swepro_trans.validation.revision import _selector_role_errors


def _obligation(status: str, selector: str) -> dict:
    return {
        "scope": "product_behavior",
        "disposition": "preserved",
        "base_behavior_status": status,
        "emitted_tests": [selector],
    }


def test_rejects_selector_assigned_to_both_base_roles() -> None:
    trace = {
        "f2p_accounting": [{
            "decision": "rewrite",
            "obligation_accounting": [
                _obligation("changed_or_missing", "TestMigration/AdminRoleMigrated"),
                _obligation("already_satisfies", "TestMigration/AdminRoleMigrated"),
            ],
        }]
    }

    assert _selector_role_errors(trace) == [
        "converted selector cannot serve both functional-delta and Base-regression roles: "
        "TestMigration/AdminRoleMigrated"
    ]


def test_accepts_separate_selectors_for_each_base_role() -> None:
    trace = {
        "f2p_accounting": [{
            "decision": "rewrite",
            "obligation_accounting": [
                _obligation("changed_or_missing", "TestMigration/AdminRoleMigrated"),
                _obligation("already_satisfies", "TestMigration/TrustedClusterMigrated"),
            ],
        }]
    }

    assert _selector_role_errors(trace) == []
