from pathlib import Path

from swepro_trans.validation.acceptance import semantic_evidence_matches
from swepro_trans.validation.binding_signals import revision_evidence_fingerprint


def test_acceptance_rejects_semantic_verdict_for_changed_verifier(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    verifier = tests / "functional_test.ts"
    verifier.write_text("await expectRejects(PublicError, () => decrypt(saved))\n")
    review = {"verifier_evidence_fingerprint": revision_evidence_fingerprint(tests)}
    assert semantic_evidence_matches(review, tmp_path)

    verifier.write_text("await decrypt(saved)\n")
    assert not semantic_evidence_matches(review, tmp_path)
    assert not semantic_evidence_matches({}, tmp_path)
