import json
from pathlib import Path
from types import SimpleNamespace

from swepro_trans.validation import stability


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _output(root: Path, *, p2p_status: str = "PASSED") -> None:
    for side in ("base", "gold"):
        _write(root / side / "output.json", {"tests": [
            {"name": "native::one", "status": p2p_status},
            {"name": "converted::regression", "status": "PASSED"},
            {"name": "converted::delta", "status": "FAILED" if side == "base" else "PASSED"},
        ]})


def test_p2p_evidence_uses_candidate_parser_results(tmp_path):
    _output(tmp_path)
    result = stability._p2p_selector_evidence(
        tmp_path, {}, ["native::one", "converted::regression"],
    )
    assert result["status"] == "pass"
    assert result["base"]["output_source"] == str(tmp_path / "base" / "output.json")

    _output(tmp_path, p2p_status="FAILED")
    result = stability._p2p_selector_evidence(tmp_path, {}, ["native::one"])
    assert result["status"] == "fail"
    assert result["base"]["not_passed"] == {"native::one": "FAILED"}

    result = stability._p2p_selector_evidence(tmp_path, {}, ["native::one", "missing::selector"])
    assert result["status"] == "fail"
    assert result["gold"]["missing_selectors"] == ["missing::selector"]


def test_p2p_evidence_normalizes_runner_trimmed_selector_whitespace(tmp_path):
    selectors = ["native::trailing space "]
    for side in ("base", "gold"):
        _write(tmp_path / side / "output.json", {"tests": [
            {"name": "native::trailing space", "status": "PASSED"},
        ]})

    result = stability._p2p_selector_evidence(tmp_path, {}, selectors)

    assert result["status"] == "pass"
    assert result["base"]["missing_selectors"] == []
    assert result["gold"]["missing_selectors"] == []


def test_stability_reuses_complete_candidate_runs_for_p2p(monkeypatch, tmp_path):
    root = tmp_path / "run"
    revision = root / "intermediate" / "converter" / "revisions" / "rev_001"
    candidate = revision / "tests"
    original = root / "original"
    source = root / "source"
    hard_root = root / "intermediate" / "validation" / "hard_replay"
    stability_root = root / "intermediate" / "validation" / "stability"
    revision_rel = str(revision.relative_to(root))
    _write(candidate / "config.json", {
        "fail_to_pass": ["converted::delta"],
        "pass_to_pass": ["native::one", "converted::regression"],
    })
    _write(revision / "conversion_trace.json", {"task_disposition": "convertible"})
    _write(original / "tests" / "config.json", {
        "fail_to_pass": ["historical::delta"], "pass_to_pass": ["native::one"],
    })
    _write(source / "dataset_row.json", {})
    contract = root / "intermediate" / "validation" / "sanity" / "revision_contract.json"
    _write(contract, {"status": "PASS", "revision_relative": revision_rel})
    hard_result = hard_root / "result.json"
    _write(hard_result, {"status": "pass", "revision": revision_rel})
    _output(hard_root / "docker")
    paths = SimpleNamespace(
        run_root=root, original=original, source=source,
        artifact_contract_path=contract, hard_replay_path=hard_result,
        validation_root=root / "intermediate" / "validation",
        hard_replay_root=hard_root, stability_root=stability_root,
        stability_path=stability_root / "result.json",
    )
    monkeypatch.setattr(stability, "resolve_task", lambda _: paths)
    monkeypatch.setattr(stability, "image_name", lambda *_: "test-image")
    calls = []

    def replay(*args, **kwargs):
        calls.append(kwargs["tests_dir"])
        _output(kwargs["log_root"])
        return {"status": "pass", "revision": revision_rel}

    monkeypatch.setattr(stability, "run_docker_preflight", replay)
    result = stability.run_stability(root, revision, repeats=2)
    assert result["status"] == "pass"
    assert calls == [candidate]
    assert [item["status"] for item in result["p2p_runs"]] == ["pass", "pass"]
    assert len(result["f2p_runs"]) == 2
