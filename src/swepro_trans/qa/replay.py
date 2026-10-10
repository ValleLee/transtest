#!/usr/bin/env python3
"""Replay one Positive/Negative QA patch against original and functional tests."""
from __future__ import annotations
import argparse, ast, json, shutil, subprocess, tomllib
from pathlib import Path
from ..runtime.stage1 import verifier_network_mode
from swepro_trans.paths import resolve_task


def image(root: Path) -> str:
    paths = resolve_task(root)
    return str(tomllib.loads((paths.original / "task.toml").read_text())["environment"]["docker_image"])


def _has_original_p2p(root: Path) -> bool:
    """The historical test patch is needed only to execute retained P2P tests."""
    config = resolve_task(root).original / "tests" / "config.json"
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    raw = data.get("pass_to_pass", data.get("pass_to_pass_tests", []))
    if isinstance(raw, list):
        return bool(raw)
    if isinstance(raw, str):
        for parser in (json.loads, ast.literal_eval):
            try:
                value = parser(raw)
            except (ValueError, SyntaxError, TypeError):
                continue
            if isinstance(value, (list, tuple)):
                return bool(value)
    return False


def run(
    root: Path,
    patch: Path,
    tests: Path,
    network: str,
    log: Path,
    image_name: str,
    *,
    enforce_clean_verifier: bool,
    stage_original_test_patch: bool = False,
    original_test_patch_path: Path | None = None,
    reset_original_test_space: bool = False,
) -> dict:
    requested_test_patch = stage_original_test_patch
    stage_original_test_patch = stage_original_test_patch and _has_original_p2p(root)
    log.mkdir(parents=True, exist_ok=True)
    command = ["docker", "run", "--rm", "--network", network,
               "-v", f"{patch.resolve()}:/candidate.patch:ro",
               "-v", f"{tests.resolve()}:/tests:ro",
               "-v", f"{log.resolve()}:/logs/verifier",
               # Keep the Docker image's configured PATH and toolchain. A
               # login shell can replace PATH from profile files (e.g. hide
               # /usr/local/go/bin), making QA replay fail even when the same
               # verifier passes under the normal non-login container shell.
               image_name, "bash", "-c",
               "cd /app 2>/dev/null || cd /testbed 2>/dev/null || exit 91; "
               "trap 'chmod -R a+rX /logs/verifier 2>/dev/null || true' EXIT; "]
    if stage_original_test_patch:
        task_paths = resolve_task(root)
        original_test_patch = original_test_patch_path or task_paths.original / "tests" / "test_patch.patch"
        if not original_test_patch.is_file():
            raise FileNotFoundError(f"missing original test patch for P2P replay: {original_test_patch}")
        insert_at = command.index(image_name)
        command[insert_at:insert_at] = [
            "-v", f"{original_test_patch.resolve()}:/original_test_patch.patch:ro",
        ]
        if reset_original_test_space:
            reset_script = Path(__file__).with_name("stage3_p2p_reset.py")
            insert_at = command.index(image_name)
            command[insert_at:insert_at] = [
                "-v", f"{reset_script.resolve()}:/stage3_p2p_reset.py:ro",
            ]
    command[-1] += "set -e; git apply /candidate.patch; printf '__PATCH_APPLIED__\\n'; "
    if stage_original_test_patch:
        if reset_original_test_space:
            command[-1] += "python3 /stage3_p2p_reset.py /original_test_patch.patch; "
        command[-1] += "git apply /original_test_patch.patch; printf '__TEST_PATCH_APPLIED__\\n'; "
    if enforce_clean_verifier:
        command[-1] += (
            "before=/tmp/swepro_repo_before.$$; after=/tmp/swepro_repo_after.$$; "
            'git status --porcelain=v1 --untracked-files=all >"$before"; '
            "set +e; bash /tests/test.sh; verifier_rc=$?; set -e; "
            'git status --porcelain=v1 --untracked-files=all >"$after"; '
            'if ! cmp -s "$before" "$after"; then '
            "echo 'ERROR: verifier modified the repository working tree' >&2; "
            'diff -u "$before" "$after" >&2 || true; exit 92; fi; '
            'exit "$verifier_rc"'
        )
    else:
        # The historical verifier is evidence and may legitimately use the
        # repository as scratch space. Its result remains useful for paired
        # comparison, but only the generated functional verifier must satisfy
        # the no-side-effect contract.
        command[-1] += "bash /tests/test.sh"
    try:
        p = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=3600, check=False)
        result = {"returncode": p.returncode, "output": p.stdout[-30000:],
                  "patch_applied": '__PATCH_APPLIED__' in p.stdout,
                  "test_patch_applied": '__TEST_PATCH_APPLIED__' in p.stdout if stage_original_test_patch else (False if requested_test_patch else None),
                  "original_test_patch_staged": stage_original_test_patch,
                  "command": command}
    except subprocess.TimeoutExpired as exc:
        result = {"returncode": None, "output": str(exc), "patch_applied": False,
                  "test_patch_applied": False if (stage_original_test_patch or requested_test_patch) else None,
                  "original_test_patch_staged": stage_original_test_patch,
                  "timeout": True, "command": command}
    (log / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def main(argv=None) -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--task-root",type=Path,required=True); ap.add_argument("--revision",type=Path,required=True); ap.add_argument("--patch",type=Path,required=True); ap.add_argument("--kind",choices=("positive","negative"),required=True); ap.add_argument("--output",type=Path)
    a=ap.parse_args(argv); paths=resolve_task(a.task_root); root=paths.run_root; rev=a.revision.resolve(); patch=a.patch.resolve()
    if not patch.is_file(): raise SystemExit(f"missing candidate patch: {patch}")
    network, harbor = verifier_network_mode(root)
    image_name=image(root); log_root=paths.qa_branch(a.kind) / "replay" / patch.parent.name
    original=run(
        root, patch, paths.original/"tests", network, log_root/"original", image_name,
        enforce_clean_verifier=False,
    )
    functional=run(
        root, patch, rev/"tests", network, log_root/"functional", image_name,
        enforce_clean_verifier=True, stage_original_test_patch=True,
    )
    functional_pass=functional.get("returncode")==0
    patches_applied = original.get('patch_applied') is True and functional.get('patch_applied') is True
    infrastructure_failure = (
        original.get("returncode") in {None, 91}
        or functional.get("returncode") in {None, 91, 92}
    )
    expected=(
        patches_applied
        and not infrastructure_failure
        and (functional_pass if a.kind=="positive" else not functional_pass)
    )
    result={"status":"pass" if expected else "fail","kind":a.kind,"revision":str(rev.relative_to(root)) if rev.is_relative_to(root) else str(rev),"network":{"harbor":harbor,"docker":network},"candidate_patch":str(patch.relative_to(root)) if patch.is_relative_to(root) else str(patch),"original":{"pass":original.get("returncode")==0,"returncode":original.get("returncode")},"functional":{"pass":functional_pass,"returncode":functional.get("returncode")},"expected_functional_pass":a.kind=="positive","patches_applied":patches_applied,"infrastructure_failure":infrastructure_failure,"runs":{"original":original,"functional":functional}}
    out=(a.output or (paths.qa_branch(a.kind) / "replay_result.json")).resolve(); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if expected else 1
if __name__=='__main__': raise SystemExit(main())
