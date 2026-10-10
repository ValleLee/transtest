import json
from pathlib import Path
from types import SimpleNamespace

from swepro_trans.validation import final_audit


def test_published_bundle_cannot_pass_after_independent_audit_rejects_it(tmp_path: Path, monkeypatch) -> None:
    run = tmp_path / "run"
    attempt = run / "attempts" / "attempt_001"
    original = tmp_path / "original"
    (attempt / "intermediate/control").mkdir(parents=True)
    (attempt / "review").mkdir()
    (original / "tests").mkdir(parents=True)
    (original / "tests/config.json").write_text('{"fail_to_pass": []}\n')
    (attempt / "intermediate/control/state.json").write_text(json.dumps({"status": "audit_rejected"}))
    (attempt / "review/independent_audit.json").write_text(json.dumps({"status": "FAIL"}))
    source = run / "source"
    source.mkdir(parents=True)
    (source / "problem_statement.md").write_text("P only\n")
    monkeypatch.setattr(final_audit, "resolve_task", lambda _root: SimpleNamespace(
        run_root=run, original=original, instance_id="example", source=source,
        specification_addendum_path=source / "specification_addendum.md",
    ))
    monkeypatch.setattr(final_audit, "latest_attempt", lambda _root: attempt)

    result = final_audit.audit_task(run)
    assert result["status"] == "FAIL"
    assert result["checks"]["attempt_status"] == "audit_rejected"
    assert result["checks"]["independent_audit"] == "FAIL"
    assert "latest attempt is not certified accepted" in result["errors"]
    assert "independent audit rejected this published revision" in result["errors"]


def test_final_audit_rejects_instruction_that_differs_from_p_only_source(tmp_path: Path, monkeypatch) -> None:
    run = tmp_path / "run"
    attempt = run / "attempts" / "attempt_001"
    original = tmp_path / "original"
    source = run / "source"
    final = attempt / "final"
    (attempt / "intermediate/control").mkdir(parents=True)
    (attempt / "review").mkdir()
    (original / "tests").mkdir(parents=True)
    (final / "tests").mkdir(parents=True)
    source.mkdir(parents=True)
    (original / "tests/config.json").write_text('{"fail_to_pass": []}\n')
    (source / "problem_statement.md").write_text("P only\n")
    (final / "instruction.md").write_text("P only\n\n## Requirements\nleaked construction text\n")
    (attempt / "intermediate/control/state.json").write_text(json.dumps({"status": "accepted"}))
    monkeypatch.setattr(final_audit, "resolve_task", lambda _root: SimpleNamespace(
        run_root=run, original=original, instance_id="example", source=source,
        specification_addendum_path=source / "specification_addendum.md",
    ))
    monkeypatch.setattr(final_audit, "latest_attempt", lambda _root: attempt)

    result = final_audit.audit_task(run)
    assert result["checks"]["instruction_matches_p_only_source"] == "FAIL"
    assert result["checks"]["instruction_leakage"]["status"] == "FAIL"
    assert "final instruction differs from P-only source plus audited addendum" in result["errors"]
