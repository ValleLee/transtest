import json
from types import SimpleNamespace

from swepro_trans.agents import mini_swe_session


def test_missing_skeleton_reminds_without_blocking_evidence_inspection(tmp_path, monkeypatch):
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(stdout="evidence read\n", returncode=0)

    monkeypatch.setattr(mini_swe_session.subprocess, "run", run)
    environment = mini_swe_session.MiniSWEEnvironment.__new__(mini_swe_session.MiniSWEEnvironment)
    environment.role = "converter"
    environment.formal_output_root = tmp_path
    environment.required_f2p_count = 1
    environment.artifact_checkpoint_step = 12
    environment.artifact_finalization_step = None
    environment.repair_write_checkpoint_step = None
    environment.formal_output_baseline = None
    environment.action_count = 12
    environment.cwd = "."
    environment.timeout = 10
    environment.tools = SimpleNamespace(validate_bash=lambda *args, **kwargs: (None, None, 10))
    environment.started = True
    environment.container_name = "test-container"
    environment.sync_callback = None
    environment.progress_reminder_sent = True
    environment.progress_reminder_step = None

    result = environment.execute({"command": "cat evidence/problem_statement.md"})

    assert commands, "the requested evidence read must reach the container"
    assert result["returncode"] == 0
    assert "evidence read" in result["output"]
    assert "CONTROLLER ARTIFACT REMINDER" in result["output"]
    assert "conversion_trace.json" in result["output"]


def test_seeded_inventory_is_complete_but_semantically_unresolved(tmp_path):
    import json

    from swepro_trans.agents.runner import _seed_converter_inventory
    from swepro_trans.conversion_schema import REQUIRED_F2P_FIELDS, unresolved_trace_errors

    revision = tmp_path / "rev_001"
    revision.mkdir()
    selectors = ["historical::one", "historical::two"]

    assert _seed_converter_inventory(revision, selectors)
    trace = json.loads((revision / "conversion_trace.json").read_text())
    assert [row["source_f2p"] for row in trace["f2p_accounting"]] == selectors
    assert all(REQUIRED_F2P_FIELDS <= row.keys() for row in trace["f2p_accounting"])
    assert unresolved_trace_errors(trace), "a preseeded inventory must never pass semantic validation"
    assert not _seed_converter_inventory(revision, ["different"])
    assert json.loads((revision / "conversion_trace.json").read_text()) == trace


def test_seed_inventory_does_not_count_as_partial_solution(tmp_path) -> None:
    from swepro_trans.agents.runner import _is_seed_only_revision, _seed_converter_inventory

    revision = tmp_path / "rev_001"
    revision.mkdir()
    assert _seed_converter_inventory(revision, ["historical::one"])
    assert _is_seed_only_revision(revision)
    trace_path = revision / "conversion_trace.json"
    trace = json.loads(trace_path.read_text())
    trace["f2p_accounting"][0]["behavior_intent"] = "observable behavior"
    trace_path.write_text(json.dumps(trace))
    assert not _is_seed_only_revision(revision)


def test_finalization_reminder_keeps_evidence_read_available(tmp_path, monkeypatch) -> None:
    from swepro_trans.agents.runner import _seed_converter_inventory

    _seed_converter_inventory(tmp_path, ["historical::one"])
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(stdout="focused evidence\n", returncode=0)

    monkeypatch.setattr(mini_swe_session.subprocess, "run", run)
    environment = mini_swe_session.MiniSWEEnvironment.__new__(mini_swe_session.MiniSWEEnvironment)
    environment.role = "converter"
    environment.formal_output_root = tmp_path
    environment.required_f2p_count = 1
    environment.artifact_checkpoint_step = None
    environment.artifact_finalization_step = 40
    environment.repair_write_checkpoint_step = None
    environment.formal_output_baseline = None
    environment.action_count = 40
    environment.cwd = "."
    environment.timeout = 10
    environment.tools = SimpleNamespace(validate_bash=lambda *args, **kwargs: (None, None, 10))
    environment.started = True
    environment.container_name = "test-container"
    environment.sync_callback = None
    environment.progress_reminder_sent = True
    environment.progress_reminder_step = None

    result = environment.execute({"command": "cat evidence/problem_statement.md"})

    assert commands
    assert result["returncode"] == 0
    assert "focused evidence" in result["output"]
    assert "CONTROLLER FINALIZATION REMINDER" in result["output"]


def test_harbor_scaffold_reuses_safe_runner_files_without_historical_patch(tmp_path, monkeypatch) -> None:
    from swepro_trans.agents import runner

    original = tmp_path / "original"
    tests = original / "tests"
    tests.mkdir(parents=True)
    (tests / "run_script.sh").write_text("#!/bin/bash\npytest \"$@\"\n")
    (tests / "parser.py").write_text("print('parsed')\n")
    (tests / "config.json").write_text('{"fail_to_pass": ["historical::one"]}')
    (tests / "test.sh").write_text("cat /tests/test_patch.patch")
    (tests / "test_patch.patch").write_text("historical implementation binding")
    monkeypatch.setattr(runner, "resolve_task", lambda _: SimpleNamespace(original=original))
    revision = tmp_path / "rev_001"
    revision.mkdir()
    runner._seed_converter_inventory(revision, ["historical::one"])

    seeded = runner._seed_harbor_test_scaffold(tmp_path, revision)

    assert seeded == ["tests/run_script.sh", "tests/parser.py", "tests/config.json"]
    assert not (revision / "tests/test.sh").exists()
    assert not (revision / "tests/test_patch.patch").exists()
    assert runner._is_seed_only_revision(revision)


def test_container_tmp_is_valid_but_other_absolute_paths_and_traversal_rejected(tmp_path) -> None:
    from swepro_trans.agents.workspace_tools import WorkspaceTools

    tools = WorkspaceTools(tmp_path, visible=["."], writable=["."])
    command = "cd /app && echo /tmp/example > /tmp/jest.log"
    checked = mini_swe_session._docker_validation_command(command)
    tools.validate_bash({"command": checked})
    assert "/tmp/example" in command, "Docker executes the original command"

    for unsafe in ("cat /etc/passwd", "cat ../private", "cat /tmp/../etc/passwd"):
        checked = mini_swe_session._docker_validation_command(unsafe)
        try:
            tools.validate_bash({"command": checked})
        except PermissionError:
            pass
        else:
            raise AssertionError(f"unsafe command accepted: {unsafe}")


def test_submission_returns_obligation_count_feedback_instead_of_ending_session(tmp_path, monkeypatch):
    trace = {
        "f2p_accounting": [{
            "source_f2p": "historical::error",
            "behavioral_obligations": ["recognize failure", "allow recovery"],
            "obligation_accounting": [{"obligation": "recognize failure"}],
        }],
    }
    (tmp_path / "conversion_trace.json").write_text(json.dumps(trace), encoding="utf-8")
    for relative in mini_swe_session.CONVERTER_SKELETON_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("complete artifact\n", encoding="utf-8")
    monkeypatch.setattr(
        mini_swe_session.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout=mini_swe_session.SUBMIT_SENTINEL + "\n", returncode=0,
        ),
    )
    environment = mini_swe_session.MiniSWEEnvironment.__new__(mini_swe_session.MiniSWEEnvironment)
    environment.role = "converter"
    environment.formal_output_root = tmp_path
    environment.required_f2p_count = 1
    environment.artifact_checkpoint_step = None
    environment.artifact_finalization_step = None
    environment.repair_write_checkpoint_step = None
    environment.formal_output_baseline = None
    environment.action_count = 0
    environment.cwd = "."
    environment.timeout = 10
    environment.tools = SimpleNamespace(validate_bash=lambda *args, **kwargs: (None, None, 10))
    environment.started = True
    environment.container_name = "test-container"
    environment.sync_callback = None
    environment.progress_reminder_sent = True
    environment.progress_reminder_step = None

    result = environment.execute({"command": mini_swe_session.SUBMIT_SENTINEL})

    assert result["returncode"] == 2
    assert "historical::error" in result["output"]
    assert "1 entries for 2 behavioral_obligations" in result["output"]


def test_finalization_rejects_missing_preservation_evidence(tmp_path):
    """A missing required trace field must be repaired in the same agent session."""
    row = {field: "" for field in mini_swe_session.REQUIRED_F2P_FIELDS}
    row.update({
        "source_f2p": "historical::public_failure",
        "behavior_classification": "p_supported_behavior",
        "decision": "rewrite",
        "base_repo_observable": True,
        "gold_only_binding": False,
        "base_behavior_status": "changed_or_missing",
        "behavioral_obligations": ["recognize failure"],
        "obligation_accounting": [{
            "id": "obligation-1",
            "obligation": "recognize failure",
            "scope": "product_behavior",
            "disposition": "preserved",
            "emitted_tests": ["functional::failure"],
            "evidence": "public failure is observable",
            "rationale": "preserve the error outcome",
            "base_behavior_status": "changed_or_missing",
        }],
        "emitted_tests": ["functional::failure"],
    })
    del row["preservation_evidence"]
    (tmp_path / "conversion_trace.json").write_text(
        json.dumps({"f2p_accounting": [row]}), encoding="utf-8"
    )

    issues = mini_swe_session._converter_finalization_issues(tmp_path)

    assert any("historical::public_failure" in issue and "preservation_evidence" in issue for issue in issues)


def test_semantic_binding_repair_requires_verifier_change_after_checkpoint(tmp_path, monkeypatch):
    tests = tmp_path / "tests"
    tests.mkdir()
    verifier = tests / "test.sh"
    verifier.write_text("echo old\n", encoding="utf-8")
    baseline = mini_swe_session._verifier_test_digest(tests)
    (tmp_path / "self_review.md").write_text("new explanation\n", encoding="utf-8")
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(stdout="focused evidence\n", returncode=0)

    monkeypatch.setattr(mini_swe_session.subprocess, "run", run)
    environment = mini_swe_session.MiniSWEEnvironment.__new__(mini_swe_session.MiniSWEEnvironment)
    environment.role = "converter"
    environment.formal_output_root = tmp_path
    environment.required_f2p_count = None
    environment.artifact_checkpoint_step = None
    environment.artifact_finalization_step = None
    environment.repair_write_checkpoint_step = None
    environment.formal_output_baseline = None
    environment.verifier_write_checkpoint_step = 8
    environment.verifier_output_baseline = baseline
    environment.action_count = 8
    environment.cwd = "."
    environment.timeout = 10
    environment.tools = SimpleNamespace(validate_bash=lambda *args, **kwargs: (None, None, 10))
    environment.started = True
    environment.container_name = "test-container"
    environment.sync_callback = None
    environment.progress_reminder_sent = True
    environment.progress_reminder_step = None

    blocked = environment.execute({"command": "cat evidence/problem_statement.md"})
    assert blocked["returncode"] == 2
    assert "verifier tests are unchanged" in blocked["output"]
    assert not commands

    verifier.write_text("echo changed\n", encoding="utf-8")
    allowed = environment.execute({"command": "cat evidence/problem_statement.md"})
    assert allowed["returncode"] == 0
    assert commands


def test_seeded_repair_feedback_enters_partial_completion_mode(tmp_path) -> None:
    from swepro_trans.agents.runner import _requires_partial_completion, _seed_converter_inventory

    revision = tmp_path / "rev_002"
    revision.mkdir()
    _seed_converter_inventory(revision, ["historical::one"])
    assert not _requires_partial_completion(revision, 1, 8)
    (revision / "repair_feedback.json").write_text('{"failed_gate":"artifact_contract"}')
    assert _requires_partial_completion(revision, 1, 8)


def test_partial_checkpoint_requires_missing_file_progress(tmp_path, monkeypatch) -> None:
    from swepro_trans.agents.mini_swe_session import _missing_converter_skeleton

    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout="focused evidence\n", returncode=0)
    monkeypatch.setattr(mini_swe_session.subprocess, "run", run)
    environment = mini_swe_session.MiniSWEEnvironment.__new__(mini_swe_session.MiniSWEEnvironment)
    environment.role = "converter"
    environment.formal_output_root = tmp_path
    environment.required_f2p_count = None
    environment.artifact_checkpoint_step = None
    environment.artifact_finalization_step = None
    environment.repair_write_checkpoint_step = None
    environment.formal_output_baseline = None
    environment.partial_missing_baseline = set(_missing_converter_skeleton(tmp_path))
    environment.partial_progress_action = 0
    environment.partial_write_interval = 8
    environment.action_count = 8
    environment.cwd = "."
    environment.timeout = 10
    environment.tools = SimpleNamespace(validate_bash=lambda *args, **kwargs: (None, None, 10))
    environment.started = True
    environment.container_name = "test-container"
    environment.sync_callback = None
    environment.progress_reminder_sent = True
    environment.progress_reminder_step = None

    blocked = environment.execute({"command": "cat evidence/problem_statement.md"})
    assert blocked["returncode"] == 2
    assert "functional_specification.md" in blocked["output"]
    assert not calls

    (tmp_path / "functional_specification.md").write_text("draft")
    allowed = environment.execute({"command": "cat evidence/problem_statement.md"})
    assert allowed["returncode"] == 0
    assert calls
