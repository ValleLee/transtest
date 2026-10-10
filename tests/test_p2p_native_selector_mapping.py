"""Original P2P selectors are preserved exactly; only F2P is converted."""
from swepro_trans.conversion_schema import canonical_retained_p2p


def test_original_p2p_selector_order_and_spelling_are_preserved():
    original = ["test/play.py::test_first", "test/play.py::TestPlay::test_second"]
    assert canonical_retained_p2p(original, {"excluded": []}) == (original, [])


def test_p2p_renaming_and_exclusion_are_rejected():
    original = ["test/play.py::test_first"]
    mapped, mapping_errors = canonical_retained_p2p(
        original, {"retained": ["test/play.py::TestPlay::test_first"], "excluded": []}
    )
    excluded, exclusion_errors = canonical_retained_p2p(
        original, {"excluded": [{"selector": original[0]}]}
    )
    assert mapped == original and mapping_errors
    assert excluded == original and exclusion_errors


def test_p2p_accounting_cannot_add_regressions_from_p2p():
    original = ["test/play.py::test_first"]
    result, errors = canonical_retained_p2p(
        original, {"excluded": [], "converted_regressions": [{"original": "x", "converted": "y"}]}
    )
    assert result == original and errors


def test_appended_f2p_regressions_leave_original_p2p_prefix_untouched():
    from swepro_trans.conversion_schema import append_f2p_regressions

    original = ["test/a.py::test_x", "test/a.py::test_x", "test/b.py::TestB::test_y"]
    assert append_f2p_regressions(original, ["converted::baseline", original[0]]) == [
        *original, "converted::baseline"
    ]


def test_active_prompts_use_verbatim_p2p_policy():
    from pathlib import Path

    converter = Path("prompts/converter.md").read_text()
    focused = Path("prompts/converter_focused.md").read_text()
    semantic = Path("prompts/judges/semantic.md").read_text()
    assert "preserve_original_verbatim" in converter
    assert '"policy": "preserve_original_verbatim"' in converter
    assert "preserve_original_verbatim" in semantic
    assert "controller stages the original `test_patch.patch`" in converter
    assert "Preserve the complete original P2P selector list" in focused
    assert "exclude only those that cannot run in Base" not in focused
    assert "controller may stage the original `test_patch.patch`" in semantic
    assert "base_native_only" not in converter
    assert "base_native_only" not in semantic
