from pathlib import Path
from types import SimpleNamespace

from swepro_trans.qa.runner import _candidate_judge_evidence


def test_positive_judge_sees_actual_gold_patch_and_wrapped_error_assertion(tmp_path: Path) -> None:
    original = tmp_path / "original"
    source = tmp_path / "source"
    revision = tmp_path / "revision"
    candidate = tmp_path / "candidate"
    for directory in (original / "solution", source, revision / "tests", candidate):
        directory.mkdir(parents=True)
    (original / "solution/gold_patch.diff").write_text("diff --git a/domain.ts b/domain.ts\n+throw new DomainError()\n")
    (source / "problem_statement.md").write_text("Recover after a saved value cannot be decrypted.\n")
    addendum = source / "specification_addendum.md"
    addendum.write_text("After recovery, preserve the user-supplied account label.\n")
    (revision / "tests/functional_test.ts").write_text("await expectRejects(DomainError, () => decrypt(saved))\n")
    (revision / "conversion_trace.json").write_text("{}\n")
    patch = candidate / "candidate.patch"
    patch.write_text("diff --git a/domain.ts b/domain.ts\n+return recover()\n")
    evidence = _candidate_judge_evidence(
        paths=SimpleNamespace(original=original, source=source, specification_addendum_path=addendum),
        revision=revision, patch=patch, replay={"status": "pass"},
    )
    assert "throw new DomainError" in evidence["gold_patch"]
    assert "return recover()" in evidence["candidate_patch"]
    assert "preserve the user-supplied account label" in evidence["problem_statement"]
    assert any(item["kind"] == "exact_exception_type" for item in evidence["verifier_binding_signals"])
