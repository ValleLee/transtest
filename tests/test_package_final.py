from __future__ import annotations

import json
from pathlib import Path
import subprocess

from swepro_trans import layout, paths


def test_package_final_writes_report_and_reconciles_attempt(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "project"
    instance_id = "instance_package_report_regression"
    task = project / "tasks" / instance_id
    original = task / "original"
    run = project / "runs" / instance_id
    attempt = run / "attempts" / "attempt_001"
    revision = attempt / "intermediate" / "converter" / "revisions" / "rev_001"

    (original / "environment").mkdir(parents=True)
    (original / "solution").mkdir()
    (original / "tests").mkdir()
    (original / "task.toml").write_text("[task]\n")
    (original / "environment" / "Dockerfile").write_text("FROM scratch\n")
    (original / "solution" / "solve.sh").write_text("#!/bin/sh\n")
    (original / "tests" / "config.json").write_text("{}\n")

    (run / "source").mkdir(parents=True)
    (run / "source" / "problem_statement.md").write_text("<pr_description>\nP only\n</pr_description>\n")
    (revision / "tests").mkdir(parents=True)
    (revision / "tests" / "test.sh").write_text("#!/bin/bash\nexit 0\n")
    (revision / "functional_specification.md").write_text("audit record\n")
    (attempt / "intermediate" / "validation").mkdir(parents=True)
    (attempt / "intermediate" / "validation" / "acceptance.json").write_text(json.dumps({
        "status": "accepted",
        "revision": "attempts/attempt_001/intermediate/converter/revisions/rev_001",
    }))
    (attempt / "intermediate" / "control").mkdir()
    (attempt / "intermediate" / "control" / "state.json").write_text(json.dumps({"status": "accepted_pending_package"}))
    (attempt / "intermediate" / "validation" / "stage2_pipeline.json").write_text(json.dumps({"status": "rejected_package"}))

    monkeypatch.setattr(paths, "PROJECT_ROOT", project)
    monkeypatch.setattr(layout, "PROJECT_ROOT", project)
    monkeypatch.setattr(layout.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0))

    report = layout.package_final(task, revision)

    package_report = attempt / "intermediate" / "packaging" / "package_report.json"
    assert report["status"] == "packaged"
    assert json.loads(package_report.read_text())["instruction_source"] == ["source/problem_statement.md"]
    assert (attempt / "final" / "instruction.md").read_text() == (run / "source" / "problem_statement.md").read_text()
    assert json.loads((attempt / "intermediate" / "control" / "state.json").read_text())["status"] == "accepted"
    assert json.loads((attempt / "intermediate" / "validation" / "stage2_pipeline.json").read_text())["status"] == "complete"
