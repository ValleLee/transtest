from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from dataprepare import prepare_swebench_pro_v2 as stage1
from swepro_trans.qa import replay as qa_replay


def _task(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "run"
    original = root / "original"
    (original / "tests").mkdir(parents=True)
    (original / "solution").mkdir(parents=True)
    (original / "tests" / "test_patch.patch").write_text("test patch\n")
    (original / "tests" / "config.json").write_text(json.dumps({"pass_to_pass": ["tests/test.py::test_existing"]}))
    (original / "solution" / "gold_patch.diff").write_text("gold patch\n")
    tests = root / "candidate" / "tests"
    tests.mkdir(parents=True)
    (tests / "test.sh").write_text("#!/bin/bash\nexit 0\n")
    return root, original, tests


def test_stage2_preflight_stages_p2p_sources_after_gold_only_in_disposable_container(monkeypatch, tmp_path):
    root, original, tests = _task(tmp_path)
    calls = []
    timeouts = []
    monkeypatch.setattr(stage1.shutil, "which", lambda _: "/usr/bin/docker")

    def fake_run(command, **kwargs):
        calls.append(command)
        timeouts.append(kwargs.get("timeout"))
        return subprocess.CompletedProcess(command, 0, "ok")

    monkeypatch.setattr(stage1, "run", fake_run)

    result = stage1.run_docker_preflight(
        root, "image", tests_dir=tests, original_root=original,
        evidence_root=root / "evidence", log_root=root / "replay",
        write_compat_results=False, expectation="base_pass_gold_pass",
        stage_original_test_patch=True,
    )

    assert result["status"] == "pass"
    assert result["original_test_patch_staged"] is True
    assert len(calls) == 2
    for command in calls:
        assert f"{original / 'tests' / 'test_patch.patch'}:/original_test_patch.patch:ro" in command
        script = command[-1]
        assert "git apply /original_test_patch.patch && bash /tests/test.sh" in script
    assert "git apply /solution/gold_patch.diff && git apply /original_test_patch.patch" in calls[1][-1]
    assert "git apply /solution/gold_patch.diff" not in calls[0][-1]
    assert timeouts == [7200, 7200]


def test_stage2_preflight_does_not_stage_historical_patch_when_no_p2p(monkeypatch, tmp_path):
    root, original, tests = _task(tmp_path)
    (original / "tests" / "config.json").write_text(json.dumps({"fail_to_pass": ["TestNewFeature"], "pass_to_pass": []}))
    calls = []
    timeouts = []
    monkeypatch.setattr(stage1.shutil, "which", lambda _: "/usr/bin/docker")

    def fake_run(command, **kwargs):
        calls.append(command)
        timeouts.append(kwargs.get("timeout"))
        return subprocess.CompletedProcess(command, 0, "ok")

    monkeypatch.setattr(stage1, "run", fake_run)
    result = stage1.run_docker_preflight(
        root, "image", tests_dir=tests, original_root=original,
        evidence_root=root / "evidence", log_root=root / "replay",
        write_compat_results=False, expectation="base_pass_gold_pass",
        stage_original_test_patch=False,
    )
    assert result["status"] == "pass"
    assert result["original_test_patch_staged"] is False
    assert len(calls) == 2
    assert all("/original_test_patch.patch" not in " ".join(command) for command in calls)
    assert all("git apply /original_test_patch.patch" not in command[-1] for command in calls)
    assert timeouts == [3600, 3600]


def test_stage2_timeout_force_removes_named_docker_container(monkeypatch, tmp_path):
    root, original, tests = _task(tmp_path)
    calls = []
    monkeypatch.setattr(stage1.shutil, "which", lambda _: "/usr/bin/docker")

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[1] == "run" and "base" in command[command.index("--name") + 1]:
            raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))
        return subprocess.CompletedProcess(command, 0, "removed or gold passed")

    monkeypatch.setattr(stage1, "run", fake_run)
    result = stage1.run_docker_preflight(
        root, "image", tests_dir=tests, original_root=original,
        evidence_root=root / "evidence", log_root=root / "replay",
        write_compat_results=False, expectation="base_fail_gold_pass",
        stage_original_test_patch=True,
    )

    base_run = next(command for command in calls if command[1] == "run" and "base" in command[command.index("--name") + 1])
    cleanup = next(command for command in calls if command[1:3] == ["rm", "--force"])
    base_name = base_run[base_run.index("--name") + 1]
    assert cleanup == ["/usr/bin/docker", "rm", "--force", base_name]
    assert result["runs"]["base"]["container_cleanup"]["returncode"] == 0
    assert result["runs"]["base"]["timeout"] is True


def test_functional_qa_skips_historical_patch_when_no_original_p2p(monkeypatch, tmp_path):
    root, original, tests = _task(tmp_path)
    (original / "tests" / "config.json").write_text(json.dumps({"fail_to_pass": ["TestNewFeature"], "pass_to_pass": []}))
    candidate_patch = root / "candidate.patch"
    candidate_patch.write_text("candidate patch\n")
    logs = root / "logs"
    monkeypatch.setattr(qa_replay, "resolve_task", lambda _: SimpleNamespace(original=original))
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, "__PATCH_APPLIED__\n")

    monkeypatch.setattr(qa_replay.subprocess, "run", fake_run)
    result = qa_replay.run(
        root, candidate_patch, tests, "none", logs, "image",
        enforce_clean_verifier=True, stage_original_test_patch=True,
    )
    command = captured["command"]
    assert result["returncode"] == 0
    assert result["original_test_patch_staged"] is False
    assert result["test_patch_applied"] is False
    assert "/original_test_patch.patch" not in " ".join(command)
    assert "git apply /original_test_patch.patch" not in command[-1]


def test_stage1_default_does_not_add_a_second_test_patch_application(monkeypatch, tmp_path):
    root, original, tests = _task(tmp_path)
    calls = []
    timeouts = []
    monkeypatch.setattr(stage1.shutil, "which", lambda _: "/usr/bin/docker")

    def fake_run(command, **kwargs):
        calls.append(command)
        timeouts.append(kwargs.get("timeout"))
        return subprocess.CompletedProcess(command, 0, "ok")

    monkeypatch.setattr(stage1, "run", fake_run)

    stage1.run_docker_preflight(
        root, "image", tests_dir=tests, original_root=original,
        evidence_root=root / "evidence", log_root=root / "replay",
        write_compat_results=False, expectation="base_pass_gold_pass",
    )

    assert len(calls) == 2
    assert all("/original_test_patch.patch" not in " ".join(command) for command in calls)
    assert timeouts == [3600, 3600]


def test_functional_qa_replay_stages_original_patch_outside_verifier_bundle(monkeypatch, tmp_path):
    root, original, tests = _task(tmp_path)
    candidate_patch = root / "candidate.patch"
    candidate_patch.write_text("candidate patch\n")
    logs = root / "logs"
    monkeypatch.setattr(qa_replay, "resolve_task", lambda _: SimpleNamespace(original=original))
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, "__PATCH_APPLIED__\n")

    monkeypatch.setattr(qa_replay.subprocess, "run", fake_run)
    result = qa_replay.run(
        root, candidate_patch, tests, "none", logs, "image",
        enforce_clean_verifier=True, stage_original_test_patch=True,
    )

    command = captured["command"]
    assert result["returncode"] == 0
    assert command[command.index("image") + 1:command.index("image") + 3] == ["bash", "-c"]
    assert f"{original / 'tests' / 'test_patch.patch'}:/original_test_patch.patch:ro" in command
    script = command[-1]
    assert script.index("git apply /candidate.patch") < script.index("git apply /original_test_patch.patch")
    assert script.index("git apply /original_test_patch.patch") < script.index("before=/tmp/swepro_repo_before.")
    assert "/original_test_patch.patch" not in str(tests)
    assert json.loads((logs / "result.json").read_text())["patch_applied"] is True



def test_replay_diagnosis_distinguishes_setup_hooks_from_leaf_failures():
    result = {
        "diagnostic_artifacts": {
            "output.json": json.dumps({"tests": [
                {"name": "suite before all hook", "status": "FAILED"},
                {"name": "other before all hook", "status": "FAILED"},
            ]})
        }
    }
    diagnosis = stage1._test_execution_diagnosis(result)
    assert diagnosis["classification"] == "setup_failure_before_leaf_tests"
    assert diagnosis["leaf_test_rows"] == 0
    assert diagnosis["setup_hook_rows"] == 2
    assert len(diagnosis["failed_setup_hooks"]) == 2


def test_replay_diagnosis_does_not_hide_executed_leaf_tests():
    result = {
        "diagnostic_artifacts": {
            "output.json": json.dumps({"tests": [
                {"name": "suite before all hook", "status": "PASSED"},
                {"name": "suite does requested behavior", "status": "FAILED"},
            ]})
        }
    }
    diagnosis = stage1._test_execution_diagnosis(result)
    assert diagnosis["classification"] == "leaf_test_results_reported"
    assert diagnosis["leaf_test_rows"] == 1
    assert diagnosis["failed_setup_hooks"] == []
