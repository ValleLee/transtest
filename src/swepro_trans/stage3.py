"""Stage 3 paired solver and verifier evaluation for the qualified 20-task cohort."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COHORT_FILE = PROJECT_ROOT / "check" / "qualified_tasks.txt"
DEFAULT_OUTPUT = PROJECT_ROOT / "check" / "stage3" / "rerun_20"
DEFAULT_HARBOR = Path(shutil.which("harbor") or PROJECT_ROOT / ".venv/bin/harbor")
AGENT_VERSION = "2.4.6"
LITELLM_VERSION = "1.83.0"
CONSTRAINT_CONTAINER = "/stage3/constraints.txt"
AGENT_NAME = "mini-swe-agent"
CONCURRENCY = 10
ROLLOUTS_PER_CONDITION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(file.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(file)))
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_qualified_tasks(path: Path = COHORT_FILE) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        instance = re.match(r"^\d+\. (instance_\S+)$", line)
        attempt = re.match(r"^\s+attempt: (attempt_\d+)", line)
        if instance:
            if current is not None:
                rows.append(current)
            current = {"instance_id": instance.group(1)}
        elif attempt and current is not None:
            current["attempt"] = attempt.group(1)
    if current is not None:
        rows.append(current)
    if len(rows) != 20 or len({x["instance_id"] for x in rows}) != 20:
        raise ValueError(f"qualified_tasks.txt must contain 20 unique instances; found {len(rows)}")
    if any("attempt" not in row for row in rows):
        raise ValueError("qualified_tasks.txt has an instance without an accepted attempt")
    return rows


def task_config(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def classify_instruction_change(original: str, converted: str) -> str:
    base = original.split("## Requirements", 1)[0].rstrip()
    converted_body = converted.split("</pr_description>", 1)[0].rstrip()
    if base == converted_body:
        return "deletion_only"
    marker = "# Functional behavior clarification"
    if marker in converted_body and base == converted_body.split(marker, 1)[0].rstrip():
        return "deletion_plus_behavior_clarification"
    return "additional_or_modified_behavior"


def local_image_identity(image_name: str) -> dict[str, Any]:
    check = subprocess.run(
        ["docker", "image", "inspect", image_name, "--format", "{{.Id}}|{{json .RepoDigests}}"],
        capture_output=True, text=True, check=False,
    )
    if check.returncode != 0:
        raise RuntimeError(f"Docker image unavailable: {image_name}")
    image_id, digests = check.stdout.strip().split("|", 1)
    return {"image_id": image_id, "repo_digests": json.loads(digests)}


def rewrite_task_name(task_toml: str, new_name: str) -> str:
    match = re.search(r"(?ms)^\[task\]\s*\n(.*?)(?=^\[|\Z)", task_toml)
    if not match:
        raise ValueError("task.toml has no [task] section")
    section = match.group(0)
    updated, count = re.subn(r'(?m)^name\s*=\s*"[^"]*"\s*$', f'name = "swepro-stage3/{new_name}"', section, count=1)
    if count != 1:
        raise ValueError("task.toml [task] section has no simple name field")
    return task_toml[: match.start()] + updated + task_toml[match.end() :]


def patch_capture_script(instance_id: str, cohort: str) -> str:
    metadata = json.dumps({"instance_id": instance_id, "cohort": cohort, "rollout": 1})
    return f'''#!/usr/bin/env bash
set +e
cd /app 2>/dev/null || cd /testbed 2>/dev/null || exit 91
mkdir -p /logs/verifier
printf '%s\\n' '{metadata}' > /logs/verifier/stage3_metadata.json
git ls-files --others --exclude-standard -z | xargs -0 -r git add -N -- >/dev/null 2>&1
git diff --binary --no-ext-diff HEAD -- > /logs/verifier/candidate.patch
printf '__STAGE3_PATCH_CAPTURED__\\n'
exec /tests/.stage3_original_test.sh "$@"
'''


def materialize_task(source: Path, instruction: Path, destination: Path, instance_id: str, cohort: str, index: int) -> None:
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copytree(source, destination)
    tests = destination / "tests"
    test_script = tests / "test.sh"
    if not test_script.is_file():
        raise FileNotFoundError(test_script)
    saved_test = tests / ".stage3_original_test.sh"
    shutil.copy2(test_script, saved_test)
    saved_test.chmod(saved_test.stat().st_mode | 0o111)
    test_script.write_text(patch_capture_script(instance_id, cohort), encoding="utf-8")
    test_script.chmod(0o755)
    (destination / "instruction.md").write_bytes(instruction.read_bytes())
    task_toml = destination / "task.toml"
    config_text = rewrite_task_name(
        task_toml.read_text(encoding="utf-8"),
        f"stage3-{index:02d}-{cohort}-{instance_id[-8:]}",
    )
    marker = "[environment.env]\n"
    if marker not in config_text or "UV_CONSTRAINT" in config_text:
        raise ValueError("task.toml requires an empty [environment.env] for the pinned agent dependency")
    config_text = config_text.replace(
        marker, marker + f'UV_CONSTRAINT = "{CONSTRAINT_CONTAINER}"\n', 1
    )
    task_toml.write_text(config_text, encoding="utf-8")


def accepted_evidence(attempt_root: Path) -> dict[str, Any]:
    candidates = [
        attempt_root / "review" / "final_audit.json",
        attempt_root / "intermediate" / "validation" / "acceptance.json",
        attempt_root / "intermediate" / "packaging" / "package_report.json",
    ]
    return {path.relative_to(attempt_root).as_posix(): read_json(path) for path in candidates if path.is_file()}


def prepare(output: Path, harbor_bin: Path, concurrency: int, rollouts: int) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"experiment output already exists and is not empty: {output}")
    rows = parse_qualified_tasks()
    tasks_root = output / "materialized_tasks"
    frozen_verifiers = output / "frozen_verifiers"
    tasks_root.mkdir(parents=True, exist_ok=True)
    frozen_verifiers.mkdir(parents=True, exist_ok=True)
    constraint_file = output / "runtime" / "constraints.txt"
    constraint_file.parent.mkdir(parents=True, exist_ok=True)
    constraint_file.write_text(f"litellm=={LITELLM_VERSION}\n", encoding="utf-8")
    manifest_rows: list[dict[str, Any]] = []
    notices: list[str] = []

    for index, row in enumerate(rows, start=1):
        instance_id, attempt = row["instance_id"], row["attempt"]
        original = PROJECT_ROOT / "tasks" / instance_id / "original"
        attempt_root = PROJECT_ROOT / "runs" / instance_id / "attempts" / attempt
        final = attempt_root / "final"
        required = [original / "task.toml", original / "instruction.md", original / "tests" / "test.sh",
                    final / "task.toml", final / "instruction.md", final / "tests" / "test.sh"]
        missing = [str(p) for p in required if not p.is_file()]
        if missing:
            raise FileNotFoundError(f"{instance_id}: missing {missing}")

        original_config = task_config(original / "task.toml")
        final_config = task_config(final / "task.toml")
        original_image = original_config["environment"]["docker_image"]
        final_image = final_config["environment"]["docker_image"]
        if original_image != final_image:
            notices.append(f"{instance_id}: image differs between original and accepted final")
        original_instruction = (original / "instruction.md").read_text(encoding="utf-8")
        final_instruction = (final / "instruction.md").read_text(encoding="utf-8")
        original_variant = tasks_root / f"{index:02d}-{instance_id}-original"
        converted_variant = tasks_root / f"{index:02d}-{instance_id}-converted"
        materialize_task(original, original / "instruction.md", original_variant, instance_id, "original", index)
        materialize_task(original, final / "instruction.md", converted_variant, instance_id, "converted", index)
        frozen_original_tests = frozen_verifiers / f"{index:02d}-{instance_id}" / "original_tests"
        frozen_functional_tests = frozen_verifiers / f"{index:02d}-{instance_id}" / "functional_tests"
        shutil.copytree(original / "tests", frozen_original_tests)
        shutil.copytree(final / "tests", frozen_functional_tests)
        image_identity = local_image_identity(original_image)
        evidence = accepted_evidence(attempt_root)
        required_statuses = {
            "review/final_audit.json": "PASS",
            "intermediate/validation/acceptance.json": "accepted",
            "intermediate/packaging/package_report.json": "packaged",
        }
        for evidence_path, expected_status in required_statuses.items():
            actual_status = (evidence.get(evidence_path) or {}).get("status")
            if actual_status != expected_status:
                raise ValueError(f"{instance_id}: {evidence_path} status {actual_status!r}, expected {expected_status!r}")
        manifest_rows.append({
            "instance_id": instance_id,
            "attempt": attempt,
            "index": index,
            "original_root": str(original),
            "final_root": str(final),
            "attempt_root": str(attempt_root),
            "original_task_hash": sha256_tree(original),
            "original_instruction_sha256": sha256_file(original / "instruction.md"),
            "final_instruction_sha256": sha256_file(final / "instruction.md"),
            "original_tests_sha256": sha256_tree(original / "tests"),
            "final_tests_sha256": sha256_tree(final / "tests"),
            "original_task_config_sha256": sha256_file(original / "task.toml"),
            "final_task_config_sha256": sha256_file(final / "task.toml"),
            "instruction_text_equal": original_instruction == final_instruction,
            "instruction_change_class": classify_instruction_change(original_instruction, final_instruction),
            "verifiers": {"original_tests": str(frozen_original_tests),
                          "functional_tests": str(frozen_functional_tests)},
            "original_image": original_image,
            **image_identity,
            "final_image": final_image,
            "network": {
                "agent_original": original_config.get("agent", {}).get("network_mode"),
                "agent_final": final_config.get("agent", {}).get("network_mode"),
                "verifier_original": original_config.get("verifier", {}).get("network_mode"),
                "verifier_final": final_config.get("verifier", {}).get("network_mode"),
            },
            "acceptance_evidence": evidence,
            "variants": {"original": str(original_variant), "converted": str(converted_variant)},
            "variant_task_config_sha256": {
                "original": sha256_file(original_variant / "task.toml"),
                "converted": sha256_file(converted_variant / "task.toml"),
            },
        })

    load_dotenv(PROJECT_ROOT / ".env", override=True)
    backend = os.getenv("DEFAULT_BACKEND", "openai_compatible")
    model = os.getenv("SOLVER_MODEL") or os.getenv("DEFAULT_MODEL")
    base_url = os.getenv("DEFAULT_BASE_URL", "").strip()
    if backend != "openai_compatible" or not model or not base_url:
        raise ValueError(".env must define DEFAULT_BACKEND=openai_compatible, DEFAULT_MODEL, and DEFAULT_BASE_URL")
    api_host = urlsplit(base_url).hostname
    if not api_host:
        raise ValueError("DEFAULT_BASE_URL must contain a host")
    if not os.getenv("DEFAULT_API_KEY"):
        raise ValueError(".env DEFAULT_API_KEY is empty")

    manifest = {
        "schema_version": 1,
        "experiment_id": output.name,
        "created_at": utc_now(),
        "cohort_source": str(COHORT_FILE),
        "cohort_source_sha256": sha256_file(COHORT_FILE),
        "cohort_size": len(manifest_rows),
        "rollouts_per_condition": rollouts,
        "concurrency": concurrency,
        "agent": {"name": AGENT_NAME, "version": AGENT_VERSION, "model": model,
                  "model_provider": "openai-compatible", "base_url_host": api_host,
                  "base_url_scheme": urlsplit(base_url).scheme,
                  "base_url_port": urlsplit(base_url).port,
                  "base_url_path": urlsplit(base_url).path,
                  "credential_env": "OPENAI_API_KEY", "seed_policy": "not set",
                  "model_service_version": "not advertised by endpoint at run start",
                  "backend": backend},
        "harbor": {"expected_version": "0.22.0", "binary": str(harbor_bin),
                   "source_commit": subprocess.check_output(
                       ["git", "-C", str(PROJECT_ROOT / "upstream" / "harbor"), "rev-parse", "HEAD"],
                       text=True).strip()},
        "official_task_source": {
            "path": str(PROJECT_ROOT / "upstream" / "SWE-bench_Pro-os"),
            "commit": subprocess.check_output(
                ["git", "-C", str(PROJECT_ROOT / "upstream" / "SWE-bench_Pro-os"), "rev-parse", "HEAD"],
                text=True).strip(),
        },
        "instruction_change_audit": {
            "deletion_only_task_indices": [r["index"] for r in manifest_rows
                                           if r["instruction_change_class"] == "deletion_only"],
            "deletion_plus_behavior_clarification_task_indices": [
                r["index"] for r in manifest_rows
                if r["instruction_change_class"] == "deletion_plus_behavior_clarification"
            ],
            "additional_or_modified_task_indices": [r["index"] for r in manifest_rows
                                                    if r["instruction_change_class"] == "additional_or_modified_behavior"],
        },
        "agent_dependency_constraint": {"path": str(constraint_file),
                                        "sha256": sha256_file(constraint_file),
                                        "litellm_version": LITELLM_VERSION},
        "patch_capture": "temporary tests/test.sh wrapper saves git diff before the original verifier runs",
        "qualified_tasks": manifest_rows,
        "preflight_notices": notices,
        "status": "prepared",
    }
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "manifest.json", manifest)
    (output / "README.txt").write_text(
        "Stage 3 experiment snapshot. Original task inputs remain untouched.\n"
        f"Cohort: {len(manifest_rows)} tasks; rollouts/condition: {rollouts}; concurrency: {concurrency}.\n"
        "Credentials are loaded at run time from project .env and are not copied here.\n",
        encoding="utf-8",
    )
    return manifest


def load_credentials() -> tuple[dict[str, str], dict[str, str]]:
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    key = os.getenv("DEFAULT_API_KEY", "")
    base_url = os.getenv("DEFAULT_BASE_URL", "").strip()
    model = os.getenv("SOLVER_MODEL") or os.getenv("DEFAULT_MODEL", "")
    if not (key and base_url and model):
        raise ValueError("DeepSeek credentials must be configured in project .env")
    provider_model = model if "/" in model else f"openai/{model}"
    env = os.environ.copy()
    env.update({
        "OPENAI_API_KEY": key,
        "OPENAI_BASE_URL": base_url,
        "OPENAI_API_BASE": base_url,
    })
    # Harbor resolves MSWEA_API_KEY before the provider key; for an
    # openai/ model, prefer OPENAI_API_KEY so LiteLLM receives it unchanged.
    env.pop("MSWEA_API_KEY", None)
    config = {"model": model, "provider_model": provider_model, "base_url": base_url,
              "api_host": urlsplit(base_url).hostname or ""}
    return env, config


def jobs_from_manifest(manifest: dict[str, Any], output: Path) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for task in manifest["qualified_tasks"]:
        for cohort in ("original", "converted"):
            for rollout in range(1, int(manifest["rollouts_per_condition"]) + 1):
                task_dir = Path(task["variants"][cohort])
                job_id = f"{task['index']:02d}-{cohort}-r{rollout:03d}"
                jobs.append({
                    "job_id": job_id, "instance_id": task["instance_id"],
                    "attempt": task["attempt"], "cohort": cohort, "rollout": rollout,
                    "task_dir": task_dir, "verifiers": task["verifiers"],
                    "image_name": task["original_image"], "frozen_image_id": task["image_id"],
                    "job_name": f"{manifest['experiment_id']}-{job_id}",
                    "job_dir": output / "harbor_jobs" / job_id,
                    "artifact_dir": output / "instances" / task["instance_id"] / cohort / f"rollout_{rollout:03d}",
                })
    return jobs


def validate_frozen_materials(manifest: dict[str, Any]) -> None:
    for task in manifest["qualified_tasks"]:
        instance_id = task["instance_id"]
        for cohort, expected in (("original", task["original_instruction_sha256"]),
                                 ("converted", task["final_instruction_sha256"])):
            task_dir = Path(task["variants"][cohort])
            if sha256_file(task_dir / "instruction.md") != expected:
                raise ValueError(f"{instance_id}: frozen {cohort} instruction changed")
            frozen_config = task.get("variant_task_config_sha256", {}).get(cohort)
            if frozen_config and sha256_file(task_dir / "task.toml") != frozen_config:
                raise ValueError(f"{instance_id}: frozen {cohort} task config changed")
        for kind, expected in (("original_tests", task["original_tests_sha256"]),
                               ("functional_tests", task["final_tests_sha256"])):
            if sha256_tree(Path(task["verifiers"][kind])) != expected:
                raise ValueError(f"{instance_id}: frozen {kind} changed")
        if local_image_identity(task["original_image"])["image_id"] != task["image_id"]:
            raise ValueError(f"{instance_id}: local Docker image changed")


def run_one_harbor(job: dict[str, Any], output: Path, harbor_bin: Path,
                   concurrency: int, model_cfg: dict[str, str], env: dict[str, str]) -> dict[str, Any]:
    status_path = job["artifact_dir"] / "solver_status.json"
    prior = read_json(status_path) or {}
    patch = job["artifact_dir"] / "candidate.patch"
    if prior.get("status") == "complete" and patch.is_file():
        return {**prior, "resumed": True}
    execution_attempt = int(prior.get("execution_attempt", 0)) + 1
    job_dir = output / "harbor_jobs" / job["job_id"] / f"attempt_{execution_attempt:02d}"
    job_dir.mkdir(parents=True, exist_ok=True)
    job["job_dir"] = job_dir
    command = [
        str(harbor_bin), "run", "-p", str(job["task_dir"]), "-e", "docker",
        "--agent", AGENT_NAME, "--model", model_cfg["provider_model"],
        "--n-concurrent", "1", "--n-attempts", "1", "--max-retries", "0",
        "--job-name", job["job_name"], "--jobs-dir", str(job_dir), "--quiet",
        "--agent-kwarg", f"version={AGENT_VERSION}",
        "--agent-kwarg", "max_tokens=6144",
        "--agent-setup-timeout-multiplier", "2",
        "--allow-agent-host", model_cfg["api_host"],
        "--mounts", json.dumps([{"type": "bind", "source": str(output / "runtime" / "constraints.txt"),
                                 "target": CONSTRAINT_CONTAINER, "read_only": True}]),
    ]
    stdout_path = job["artifact_dir"] / "harbor.stdout.log"
    stderr_path = job["artifact_dir"] / "harbor.stderr.log"
    job["artifact_dir"].mkdir(parents=True, exist_ok=True)
    write_json(job["artifact_dir"] / "command.json", {"command": command, "concurrency_group_limit": concurrency})
    started = utc_now()
    with stdout_path.open("w", encoding="utf-8") as out_stream, stderr_path.open("w", encoding="utf-8") as err_stream:
        process = subprocess.run(command, cwd=PROJECT_ROOT, env=env, stdout=out_stream,
                                 stderr=err_stream, check=False)
    metadata_path = next(job_dir.rglob("stage3_metadata.json"), None)
    patch_source = metadata_path.with_name("candidate.patch") if metadata_path else None
    patch_dest = job["artifact_dir"] / "candidate.patch"
    metadata = read_json(metadata_path) if metadata_path else None
    patch_captured = bool(patch_source and patch_source.is_file() and metadata and
                          metadata.get("instance_id") == job["instance_id"] and metadata.get("cohort") == job["cohort"])
    if patch_captured:
        shutil.copy2(patch_source, patch_dest)
    status = "complete" if patch_captured else "incomplete"
    result = {
        "status": status, "execution_attempt": execution_attempt,
        "returncode": process.returncode, "patch_captured": patch_captured,
        "patch_nonempty": bool(patch_captured and patch_dest.stat().st_size),
        "instance_id": job["instance_id"], "attempt": job["attempt"], "cohort": job["cohort"],
        "rollout": job["rollout"], "job_name": job["job_name"], "job_dir": str(job_dir),
        "trial_dir": str(metadata_path.parent.parent) if metadata_path else None,
        "started_at": started, "finished_at": utc_now(),
        "stdout": str(stdout_path), "stderr": str(stderr_path),
    }
    write_json(status_path, result)
    return result


def run_benchmark(output: Path, harbor_bin: Path, concurrency: int) -> dict[str, Any]:
    manifest_path = output / "manifest.json"
    manifest = read_json(manifest_path)
    if not manifest:
        raise FileNotFoundError(f"missing prepared manifest: {manifest_path}")
    if int(manifest["cohort_size"]) != 20:
        raise ValueError("refusing to run: manifest cohort must contain all 20 qualified tasks")
    validate_frozen_materials(manifest)
    if concurrency != int(manifest["concurrency"]):
        raise ValueError(f"concurrency {concurrency} differs from frozen manifest {manifest['concurrency']}")
    if not harbor_bin.is_file():
        raise FileNotFoundError(f"Harbor CLI not installed: {harbor_bin}")
    env, model_cfg = load_credentials()
    version = subprocess.run([str(harbor_bin), "--version"], cwd=PROJECT_ROOT,
                             capture_output=True, text=True, check=False)
    if version.returncode != 0 or "0.22.0" not in version.stdout + version.stderr:
        raise RuntimeError(f"Expected Harbor 0.22.0, got {version.stdout.strip()} {version.stderr.strip()}")
    if model_cfg["model"] != manifest["agent"]["model"] or model_cfg["api_host"] != manifest["agent"]["base_url_host"]:
        raise ValueError(".env model or endpoint changed since manifest preparation")

    jobs = jobs_from_manifest(manifest, output)
    results: list[dict[str, Any]] = []
    completed = 0
    lock = threading.Lock()
    write_json(output / "run_state.json", {"status": "running", "started_at": utc_now(),
                                           "total_jobs": len(jobs), "concurrency": concurrency})
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_jobs = {
            executor.submit(run_one_harbor, job, output, harbor_bin, concurrency, model_cfg, env): job
            for job in jobs
        }
        for future in concurrent.futures.as_completed(future_jobs):
            job = future_jobs[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {"status": "error", "instance_id": job["instance_id"],
                          "cohort": job["cohort"], "rollout": job["rollout"], "error": repr(exc)}
                write_json(job["artifact_dir"] / "solver_status.json", result)
            with lock:
                results.append(result)
                completed += 1
                write_json(output / "run_state.json", {
                    "status": "running", "updated_at": utc_now(), "total_jobs": len(jobs),
                    "completed_jobs": completed, "success_jobs": sum(x.get("status") == "complete" for x in results),
                    "failed_jobs": sum(x.get("status") != "complete" for x in results), "concurrency": concurrency,
                })
                print(f"[{completed}/{len(jobs)}] {job['instance_id']} {job['cohort']}: {result.get('status')}", flush=True)
    success = sum(x.get("status") == "complete" for x in results)
    state = {"status": "solver_complete" if success == len(jobs) else "solver_partial",
             "finished_at": utc_now(), "total_jobs": len(jobs), "success_jobs": success,
             "failed_jobs": len(jobs) - success, "concurrency": concurrency,
             "results": results}
    write_json(output / "run_state.json", state)
    return state


def regrade_one(job: dict[str, Any], output: Path) -> dict[str, Any]:
    from .qa.replay import run as run_verifier
    from .runtime.stage1 import verifier_network_mode

    patch = job["artifact_dir"] / "candidate.patch"
    status_path = job["artifact_dir"] / "regrade.json"
    if status_path.is_file():
        prior = read_json(status_path) or {}
        if prior.get("status") == "complete":
            return {**prior, "resumed": True}
    if not patch.is_file() or patch.stat().st_size == 0:
        result = {"status": "no_patch", "instance_id": job["instance_id"],
                  "cohort": job["cohort"], "rollout": job["rollout"]}
        write_json(status_path, result)
        return result

    task_root = PROJECT_ROOT / "tasks" / job["instance_id"]
    original_tests = Path(job["verifiers"]["original_tests"])
    functional_tests = Path(job["verifiers"]["functional_tests"])
    image_name = job["image_name"]
    if local_image_identity(image_name)["image_id"] != job["frozen_image_id"]:
        raise RuntimeError(f"Docker image changed since manifest preparation: {image_name}")
    network, harbor_mode = verifier_network_mode(task_root)
    replay_root = job["artifact_dir"] / "regrade"
    replay_root.mkdir(parents=True, exist_ok=True)
    old = run_verifier(task_root, patch, original_tests, network,
                       replay_root / "original", image_name, enforce_clean_verifier=False)
    test_patch = original_tests / "test_patch.patch"
    functional = run_verifier(task_root, patch, functional_tests, network,
                              replay_root / "functional", image_name,
                              enforce_clean_verifier=True,
                              stage_original_test_patch=test_patch.is_file(),
                              original_test_patch_path=test_patch if test_patch.is_file() else None,
                              reset_original_test_space=test_patch.is_file())
    old_valid = old.get("patch_applied") and old.get("returncode") not in (None, 91)
    test_patch_required = functional.get("original_test_patch_staged") is True
    new_valid = (functional.get("patch_applied")
                 and (not test_patch_required or functional.get("test_patch_applied"))
                 and functional.get("returncode") not in (None, 91, 92))
    result = {
        "status": "complete" if old_valid and new_valid else "infrastructure_or_patch_error",
        "instance_id": job["instance_id"], "attempt": job["attempt"],
        "cohort": job["cohort"], "rollout": job["rollout"],
        "patch_sha256": sha256_file(patch), "patch_nonempty": True,
        "network": {"docker": network, "harbor_declared": harbor_mode},
        "image": image_name,
        "original": {"valid_verdict": old_valid, "pass": old.get("returncode") == 0,
                     "returncode": old.get("returncode"), "patch_applied": old.get("patch_applied")},
        "functional": {"valid_verdict": new_valid, "pass": functional.get("returncode") == 0,
                        "returncode": functional.get("returncode"), "patch_applied": functional.get("patch_applied"),
                        "test_patch_applied": functional.get("test_patch_applied")},
        "logs": {"original": str(replay_root / "original"), "functional": str(replay_root / "functional")},
        "finished_at": utc_now(),
    }
    write_json(status_path, result)
    return result


def regrade_benchmark(output: Path, concurrency: int) -> dict[str, Any]:
    manifest = read_json(output / "manifest.json")
    if not manifest:
        raise FileNotFoundError("prepared manifest missing")
    validate_frozen_materials(manifest)
    jobs = jobs_from_manifest(manifest, output)
    results: list[dict[str, Any]] = []
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_jobs = {executor.submit(regrade_one, job, output): job for job in jobs}
        for future in concurrent.futures.as_completed(future_jobs):
            job = future_jobs[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {"status": "error", "instance_id": job["instance_id"],
                          "cohort": job["cohort"], "rollout": job["rollout"], "error": repr(exc)}
                write_json(job["artifact_dir"] / "regrade.json", result)
            results.append(result)
            completed += 1
            print(f"[regrade {completed}/{len(jobs)}] {job['instance_id']} {job['cohort']}: {result.get('status')}", flush=True)
    done = sum(x.get("status") == "complete" for x in results)
    state = {"status": "regrade_complete" if done == len(jobs) else "regrade_partial",
             "finished_at": utc_now(), "total_jobs": len(jobs), "complete_jobs": done,
             "other_jobs": len(jobs) - done, "results": results}
    write_json(output / "regrade_state.json", state)
    return state


def aggregate(output: Path) -> dict[str, Any]:
    from .stage3_analysis import aggregate as build_aggregate
    return build_aggregate(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "regrade", "aggregate", "all"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--harbor", type=Path, default=DEFAULT_HARBOR)
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY)
    parser.add_argument("--rollouts", type=int, default=ROLLOUTS_PER_CONDITION)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    harbor = args.harbor.resolve()
    try:
        if args.command == "prepare":
            result = prepare(output, harbor, args.concurrency, args.rollouts)
        elif args.command == "run":
            result = run_benchmark(output, harbor, args.concurrency)
        elif args.command == "regrade":
            result = regrade_benchmark(output, args.concurrency)
        elif args.command == "aggregate":
            result = aggregate(output)
        else:
            if not (output / "manifest.json").is_file():
                prepare(output, harbor, args.concurrency, args.rollouts)
            solver = run_benchmark(output, harbor, args.concurrency)
            replay = regrade_benchmark(output, args.concurrency) if solver["success_jobs"] else None
            result = aggregate(output) if replay else {"solver": solver, "regrade": None}
        print(json.dumps({k: v for k, v in result.items() if k != "tasks"}, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"stage3 error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
