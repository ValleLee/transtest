from pathlib import Path

from swepro_trans.layout import build_final_instruction


def test_final_instruction_is_p_plus_controller_audited_behavior_addendum(tmp_path: Path) -> None:
    problem = tmp_path / "problem_statement.md"
    addendum = tmp_path / "specification_addendum.md"
    problem.write_text("<pr_description>\nP behavior\n</pr_description>\n")
    addendum.write_text("## Behavior from historical F2P evidence\nObservable behavior\nusing historical F2P evidence\n")

    result = build_final_instruction(problem, addendum)

    assert "Requirements" not in result
    assert "New Interfaces" not in result
    assert "## Additional observable behavior" in result
    assert "using historical F2P evidence" not in result
    assert result.endswith("</pr_description>\n")
