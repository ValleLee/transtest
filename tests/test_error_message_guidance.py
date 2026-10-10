from pathlib import Path

from swepro_trans.validation.counterfactual import SYSTEM


def test_modal_prohibition_is_valid_error_message_counterfactual():
    required_examples = ("Hosts must not be empty", "Hosts are not empty")
    for path in (
        Path("prompts/converter.md"),
        Path("prompts/converter_focused.md"),
        Path("prompts/judges/semantic.md"),
        Path("docs/optimize_rule.md"),
    ):
        text = " ".join(path.read_text(encoding="utf-8").split())
        assert all(term in text for term in required_examples), path
    assert "modal prohibition" in SYSTEM
    semantic_text = " ".join(
        Path("prompts/judges/semantic.md").read_text(encoding="utf-8").split()
    ).lower()
    assert "modal prohibitions" in semantic_text
