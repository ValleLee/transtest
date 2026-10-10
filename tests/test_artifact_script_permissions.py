from pathlib import Path

from swepro_trans.validation.revision import _script_permission_errors


def test_runner_must_be_executable(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    runner = tests / "run_script.sh"
    runner.write_text("#!/bin/sh\nexit 0\n")
    runner.chmod(0o644)

    assert _script_permission_errors(tests) == [
        "tests/run_script.sh must be executable (chmod +x)"
    ]

    runner.chmod(0o755)
    assert _script_permission_errors(tests) == []
