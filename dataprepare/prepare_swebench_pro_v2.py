#!/usr/bin/env python3
"""Prepare and validate selected SWE-bench Pro V2 Harbor tasks.

This script deliberately keeps ``tasks/<id>/original`` immutable after copying the
upstream task.  It writes Stage 1 provenance and preflight evidence under ``data/stage1/<id>``;
Stage 2 conversion runs are created separately under ``runs/<id>``.
The default run is deterministic and does not pull 20 multi-GB images; use
``--pull-images`` and ``--preflight`` when Docker/Harbor are available.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

UPSTREAM_URL = "https://github.com/scaleapi/SWE-bench_Pro-os.git"
UPSTREAM_COMMIT = "66f92766bba642462d4bbe5479e83f91f9211862"
DATASET_URL = "https://datasets-server.huggingface.co/rows?dataset=ScaleAI%2FSWE-bench_Pro&config=default&split=test&offset={offset}&length={length}"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC = PROJECT_ROOT / "docs" / "20pilotdata.md"
DEFAULT_UPSTREAM = PROJECT_ROOT / "upstream" / "SWE-bench_Pro-os"
DEFAULT_OUTPUT = PROJECT_ROOT
DOCKER_READY: bool | None = None
REQUIRED_FILES = (
    "task.toml", "instruction.md", "environment/Dockerfile",
    "solution/gold_patch.diff", "solution/solve.sh",
    "tests/config.json", "tests/parser.py", "tests/run_script.sh",
    "tests/test.sh", "tests/test_patch.patch",
)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run(cmd: list[str], cwd: Path | None = None, *, check: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=check, timeout=timeout)


def instance_ids(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    ids = re.findall(r"`(instance_[^`]+)`", text)
    # The document contains exactly the pilot table; reject accidental duplicates.
    out = list(dict.fromkeys(ids))
    if len(out) != 20:
        raise ValueError(f"expected 20 instance IDs in {path}, found {len(out)}")
    return out


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_hash(root: Path) -> tuple[str, dict[str, str]]:
    files: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        files[path.relative_to(root).as_posix()] = sha256_file(path)
    digest = hashlib.sha256()
    for name, value in files.items():
        digest.update(f"{value}  {name}\n".encode())
    return digest.hexdigest(), files


def ensure_upstream(upstream: Path, ids: list[str]) -> str:
    if not (upstream / ".git").exists():
        upstream.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--filter=blob:none", "--no-checkout", UPSTREAM_URL, str(upstream)])
    else:
        current = run(["git", "rev-parse", "HEAD"], cwd=upstream, check=False).stdout.strip()
        if current != UPSTREAM_COMMIT:
            run(["git", "fetch", "--depth=1", "origin", UPSTREAM_COMMIT], cwd=upstream)
    paths = ["v2/README.md", "v2/SHA256SUMS", "v2/GATE.md"]
    paths.extend(f"v2/tasks/{instance_id}" for instance_id in ids)
    # Configure the sparse index before checkout; otherwise Git materializes all 642 tasks.
    run(["git", "sparse-checkout", "init", "--no-cone"], cwd=upstream)
    run(["git", "sparse-checkout", "set", "--no-cone", *paths], cwd=upstream)
    current = run(["git", "rev-parse", "HEAD"], cwd=upstream, check=False).stdout.strip()
    if current != UPSTREAM_COMMIT:
        run(["git", "checkout", "--detach", UPSTREAM_COMMIT], cwd=upstream)
    actual = run(["git", "rev-parse", "HEAD"], cwd=upstream).stdout.strip()
    if actual != UPSTREAM_COMMIT:
        raise RuntimeError(f"upstream commit mismatch: {actual} != {UPSTREAM_COMMIT}")
    return actual


def http_json(url: str, attempts: int = 3) -> Any:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            req = Request(url, headers={"User-Agent": "Swepro-test-trans/Stage1"})
            with urlopen(req, timeout=90) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"could not fetch {url}: {last}")


def fetch_rows(cache: Path, wanted: set[str], *, refresh: bool = False) -> dict[str, dict[str, Any]]:
    if cache.exists() and not refresh:
        payload = json.loads(cache.read_text(encoding="utf-8"))
        rows = {row["instance_id"]: row for row in payload.get("rows", [])}
    else:
        rows_list: list[dict[str, Any]] = []
        # The endpoint caps responses; 100 keeps each request manageable.
        for offset in range(0, 1000, 100):
            payload = http_json(DATASET_URL.format(offset=offset, length=100))
            batch = [entry["row"] for entry in payload.get("rows", [])]
            rows_list.extend(batch)
            if len(batch) < 100:
                break
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"source": DATASET_URL, "rows": rows_list}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        rows = {row["instance_id"]: row for row in rows_list}
    # Keep missing IDs in the report. A few historical recommendations can refer
    # to V1-only instances; silently substituting a different V2 task would break
    # provenance and make the pilot set irreproducible.
    return {key: rows[key] for key in wanted if key in rows}


def image_name(task: Path, row: dict[str, Any]) -> str | None:
    try:
        import tomllib
        config = tomllib.loads((task / "task.toml").read_text(encoding="utf-8"))
        value = config.get("environment", {}).get("docker_image")
        if value:
            return str(value)
    except Exception:
        pass
    value = row.get("docker_image")
    return str(value) if value else None


def image_evidence(image: str | None, *, pull: bool) -> dict[str, Any]:
    evidence: dict[str, Any] = {"image": image, "requested_pull": pull, "status": "not_requested"}
    if not image:
        evidence.update(status="missing_metadata", error="docker image not found in task.toml or dataset row")
        return evidence
    docker = shutil.which("docker")
    if not docker:
        evidence.update(status="unavailable", error="docker executable not found")
        return evidence
    global DOCKER_READY
    if not pull and DOCKER_READY is None:
        try:
            probe = run([docker, "info", "--format", "{{.ServerVersion}}"], check=False, timeout=3)
            DOCKER_READY = probe.returncode == 0
        except subprocess.TimeoutExpired:
            DOCKER_READY = False
    if not pull and DOCKER_READY is False:
        evidence.update(status="unavailable", error="Docker daemon unavailable; image digest not inspected")
        return evidence
    if pull:
        # Reuse an already-present image; GHCR may serialize or stall a redundant pull.
        try:
            existing = run([docker, "image", "inspect", image, "--format", "{{json .RepoDigests}}"], check=False, timeout=10)
        except subprocess.TimeoutExpired:
            existing = None
        if existing is not None and existing.returncode == 0:
            try:
                digests = json.loads(existing.stdout.strip() or "[]")
            except json.JSONDecodeError:
                digests = []
            evidence.update(status="present", repo_digests=digests, reused=True)
            return evidence
        try:
            proc = run([docker, "pull", image], check=False, timeout=1800)
        except subprocess.TimeoutExpired as exc:
            evidence.update(status="pull_timeout", error=str(exc))
            return evidence
        evidence["pull_output"] = proc.stdout[-4000:]
        if proc.returncode:
            evidence.update(status="pull_failed", returncode=proc.returncode)
            return evidence
    try:
        proc = run([docker, "image", "inspect", image, "--format", "{{json .RepoDigests}}"], check=False, timeout=10)
    except subprocess.TimeoutExpired as exc:
        evidence.update(status="docker_timeout", error=str(exc))
        return evidence
    if proc.returncode == 0:
        try:
            digests = json.loads(proc.stdout.strip() or "[]")
        except json.JSONDecodeError:
            digests = []
        evidence.update(status="present", repo_digests=digests)
    else:
        evidence.update(status="absent", inspect_output=proc.stdout[-2000:])
    return evidence


def strip_instruction_sections(instruction: str) -> str:
    """Remove only the two construction-only Markdown sections.

    Harbor's instruction contains useful task framing around the PR
    description. Preserve that framing, the ``<pr_description>`` wrapper, and
    constraints; remove only the Requirements and New Interfaces sections.
    """
    lines = instruction.splitlines(keepends=True)
    output: list[str] = []
    skipping = False
    for line in lines:
        heading = re.match(r"^(##)\s+(Requirements|New Interfaces)\s*$", line.rstrip("\r\n"))
        any_h2 = re.match(r"^##\s+", line)
        if heading:
            skipping = True
            continue
        if skipping and (any_h2 or line.startswith("</pr_description>")):
            skipping = False
        if not skipping:
            output.append(line)
    return "".join(output).strip() + "\n"


def write_source_contract(evidence_root: Path, row: dict[str, Any], original_instruction: Path | None = None) -> None:
    """Persist the P-only solver instruction and construction evidence separately."""
    source = evidence_root / "source"
    source.mkdir(parents=True, exist_ok=True)
    if original_instruction and original_instruction.is_file():
        instruction = strip_instruction_sections(original_instruction.read_text(encoding="utf-8"))
        source_field = "original/instruction.md"
    else:
        instruction = str(row.get("problem_statement") or "").strip() + "\n"
        source_field = "problem_statement"
    (source / "problem_statement.md").write_text(instruction, encoding="utf-8")
    (source / "requirements.md").write_text(str(row.get("requirements") or ""), encoding="utf-8")
    (source / "interface.md").write_text(str(row.get("interface") or ""), encoding="utf-8")
    write_json(source / "instruction_policy.json", {
        "solver_instruction": "problem_statement_only_with_audited_addendum",
        "source_field": source_field,
        "removed_sections": ["Requirements", "New Interfaces"],
        "construction_evidence": ["requirements", "interface"],
    })


def verifier_network_mode(task_root: Path, original_root: Path | None = None) -> tuple[str, str]:
    """Map Harbor's verifier network policy to a local Docker network.

    Harbor's ``public`` policy permits the verifier to reach the network; Docker
    bridge is the closest local equivalent. ``none`` remains isolated.
    """
    if original_root is not None:
        config = original_root / "task.toml"
    elif (task_root / "original").is_dir():
        config = task_root / "original" / "task.toml"
    elif task_root.parent.name == "runs":
        config = task_root.parent.parent / "tasks" / task_root.name / "original" / "task.toml"
    else:
        config = task_root / "task.toml"
    raw = "none"
    if config.exists():
        text = config.read_text(encoding="utf-8")
        section_match = re.search(r"(?ms)^\[verifier\]\s*(.*?)(?=^\[|\Z)", text)
        section = section_match.group(1) if section_match else ""
        mode_match = re.search(r"(?m)^\s*network_mode\s*=\s*[\"']([^\"']+)[\"']", section)
        if mode_match:
            raw = mode_match.group(1).strip().lower()
    if raw in {"public", "bridge"}:
        return "bridge", raw
    if raw in {"host"}:
        return "host", raw
    return "none", raw




def _test_execution_diagnosis(result: dict[str, Any]) -> dict[str, Any]:
    """Summarize whether parsed runner output reached leaf tests.

    A Docker command can return the same non-zero status for a product
    assertion and for a suite setup hook that prevented every leaf test from
    running. Keep replay acceptance unchanged, but make this distinction
    explicit in repair evidence.
    """
    artifacts = result.get("diagnostic_artifacts", {})
    payload = None
    source = None
    if isinstance(artifacts, dict):
        for name in ("output.json", "parsed_results.json", "results.json"):
            raw = artifacts.get(name)
            if not isinstance(raw, str):
                continue
            try:
                candidate = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and isinstance(candidate.get("tests"), list):
                payload, source = candidate, name
                break

    if payload is None:
        return {"classification": "unavailable", "reason": "no parsed test result artifact"}

    rows = [row for row in payload["tests"] if isinstance(row, dict)]
    hook_rows = []
    leaf_rows = []
    for row in rows:
        name = str(row.get("fullTitle") or row.get("name") or row.get("title") or "")
        is_hook = bool(re.search(r"\b(?:before|after)\s+(?:all|each)\b|\bhook\b", name, re.IGNORECASE))
        (hook_rows if is_hook else leaf_rows).append(row)

    failed_hooks = [
        str(row.get("fullTitle") or row.get("name") or row.get("title") or "<unnamed hook>")
        for row in hook_rows
        if str(row.get("status", "")).upper() in {"FAILED", "ERROR"}
    ]
    if not leaf_rows and failed_hooks:
        classification = "setup_failure_before_leaf_tests"
    elif leaf_rows:
        classification = "leaf_test_results_reported"
    else:
        classification = "no_leaf_test_results_reported"
    stats = payload.get("stats")
    return {
        "classification": classification,
        "source": source,
        "reported_rows": len(rows),
        "leaf_test_rows": len(leaf_rows),
        "setup_hook_rows": len(hook_rows),
        "failed_setup_hooks": failed_hooks[:10],
        "stats_tests": stats.get("tests") if isinstance(stats, dict) else None,
    }

def run_docker_preflight(task_root: Path, image: str | None, *, tests_dir: Path | None = None, log_root: Path | None = None, original_root: Path | None = None, evidence_root: Path | None = None, write_compat_results: bool = True, expectation: str = "base_fail_gold_pass", stage_original_test_patch: bool = False) -> dict[str, Any]:
    """Run the official Harbor tests/test.sh with Base and Gold states."""
    if not image:
        return {"status": "unavailable", "reason": "no docker_image metadata"}
    docker = shutil.which("docker")
    if not docker:
        return {"status": "unavailable", "reason": "docker executable not found"}
    original = original_root or (task_root / "original")
    tests = tests_dir or (original / "tests")
    gold = original / "solution" / "gold_patch.diff"
    original_test_patch = original / "tests" / "test_patch.patch"
    if stage_original_test_patch and not original_test_patch.is_file():
        raise FileNotFoundError(
            f"cannot stage original P2P test source; missing {original_test_patch}"
        )
    evidence_root = evidence_root or (task_root / "intermediate")
    log_root = log_root or (evidence_root / "preflight" / "docker")
    log_root.mkdir(parents=True, exist_ok=True)
    runs: dict[str, Any] = {}
    docker_network, harbor_network = verifier_network_mode(task_root, original_root)
    for label in ("base", "gold"):
        # Give Base and Gold separate writable diagnostic directories. Sharing
        # one mount lets the second run overwrite the first run's logs and
        # makes an automatic repair agent guess which repository state failed.
        label_log = log_root / label
        # Per-selector role audits must never read output.json left by an older
        # revision or replay. Each Base/Gold execution owns a fresh log mount.
        if label_log.exists():
            shutil.rmtree(label_log)
        label_log.mkdir(parents=True, exist_ok=True)
        container_name = f"swepro-preflight-{label}-{uuid.uuid4().hex[:12]}"
        command = [docker, "run", "--rm", "--name", container_name,
                   "--network", docker_network,
                   "-v", f"{tests.resolve()}:/tests:ro",
                   "-v", f"{label_log.resolve()}:/logs/verifier"]
        script = "cd /app 2>/dev/null || cd /testbed 2>/dev/null || exit 91; "
        if label == "gold":
            command += ["-v", f"{gold.resolve()}:/solution/gold_patch.diff:ro"]
            script += "git apply /solution/gold_patch.diff && "
        if stage_original_test_patch:
            # Stage 2 keeps original P2P selectors and source intact while
            # applying the official test-only patch in the disposable checkout.
            # It is mounted outside /tests so the emitted verifier cannot copy,
            # edit, or depend on the historical patch.
            command += ["-v", f"{original_test_patch.resolve()}:/original_test_patch.patch:ro"]
            script += "git apply /original_test_patch.patch && "
        command += [image, "bash", "-c", script + "bash /tests/test.sh"]
        try:
            # Stage 2 additionally replays the immutable original P2P tests.
            # Some official benchmark selectors process large checked-in
            # datasets and legitimately take longer than the Stage 1 smoke
            # test budget. Keep the Stage 1 default bounded at one hour while
            # allowing these unchanged Stage 2 suites up to two hours per
            # Base/Gold state.
            timeout_seconds = 7200 if stage_original_test_patch else 3600
            proc = run(command, check=False, timeout=timeout_seconds)
            result = {"returncode": proc.returncode, "output": proc.stdout[-30000:], "command": command}
        except subprocess.TimeoutExpired as exc:
            # Killing the Docker CLI does not reliably stop the container it
            # launched. Remove the named container explicitly so a timed-out
            # benchmark cannot keep consuming resources in the background.
            cleanup_command = [docker, "rm", "--force", container_name]
            try:
                cleanup_proc = run(cleanup_command, check=False, timeout=30)
                cleanup = {
                    "returncode": cleanup_proc.returncode,
                    "output": cleanup_proc.stdout[-2000:],
                }
            except Exception as cleanup_exc:  # preserve timeout evidence even if cleanup fails
                cleanup = {"error": repr(cleanup_exc), "command": cleanup_command}
            result = {
                "returncode": None, "output": str(exc), "command": command,
                "timeout": True, "container_cleanup": cleanup,
            }
        # Verifiers are required to retain runner diagnostics in /logs/verifier.
        # Fold bounded textual artifacts into the replay result so structured
        # repair feedback remains useful after the disposable container exits.
        diagnostics: dict[str, str] = {}
        for artifact in sorted(label_log.rglob("*")):
            if not artifact.is_file() or artifact.name == "reward.txt":
                continue
            try:
                if artifact.stat().st_size > 2_000_000:
                    continue
                diagnostics[str(artifact.relative_to(label_log))] = artifact.read_text(
                    encoding="utf-8", errors="replace"
                )[-30000:]
            except OSError:
                continue
        if diagnostics:
            result["diagnostic_artifacts"] = diagnostics
        result["execution_diagnosis"] = _test_execution_diagnosis(result)
        write_json(log_root / f"{label}_result.json", result)
        runs[label] = result
    base_rc = runs["base"]["returncode"]
    gold_rc = runs["gold"]["returncode"]
    if expectation == "base_pass_gold_pass":
        passed = base_rc == 0 and gold_rc == 0
        expected = "Base PASS and Gold PASS"
    elif expectation == "base_fail_gold_pass":
        passed = base_rc is not None and base_rc != 0 and gold_rc == 0
        expected = "Base FAIL and Gold PASS"
    else:
        raise ValueError(f"unknown Docker preflight expectation: {expectation}")
    result = {"status": "pass" if passed else "fail",
              "engine": "docker-official-tests", "network": {"harbor": harbor_network, "docker": docker_network},
              "expected": expected, "expectation": expectation,
              "original_test_patch_staged": stage_original_test_patch, "runs": runs}
    combined_output = "\n".join(str(item.get("output", "")) for item in runs.values())
    if result["status"] != "pass" and "go: command not found" in combined_output:
        result["classification"] = "published_image_missing_go_runtime"
        result["note"] = "Official run_script.sh could not find go inside the published image; Base and Gold failed before executing the selected Go test."
    if write_compat_results:
        write_json(evidence_root / "preflight" / "base_result.json", runs["base"])
        write_json(evidence_root / "preflight" / "gold_result.json", runs["gold"])
    return result


def structural_check(original: Path) -> dict[str, Any]:
    missing = [name for name in REQUIRED_FILES if not (original / name).is_file()]
    empty = [name for name in REQUIRED_FILES if (original / name).is_file() and (original / name).stat().st_size == 0]
    tree, files = tree_hash(original)
    return {"status": "pass" if not missing and not empty else "fail", "missing": missing, "empty": empty, "file_count": len(files), "tree_sha256": tree, "files": files}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids-file", type=Path, default=None, help="newline-separated instance IDs; defaults to 20pilotdata.md")
    parser.add_argument("--upstream-dir", type=Path, default=DEFAULT_UPSTREAM)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--refresh-dataset", action="store_true")
    parser.add_argument("--pull-images", action="store_true", help="pull missing GHCR images (large downloads)")
    parser.add_argument("--pull-images-file", type=Path, help="only pull images for IDs listed in this file")
    parser.add_argument("--preflight", action="store_true", help="run Base/Gold checks for selected IDs")
    parser.add_argument("--preflight-ids-file", type=Path, help="only preflight IDs listed in this file")
    parser.add_argument("--preflight-engine", choices=("auto", "harbor", "docker"), default="auto")
    args = parser.parse_args()
    ids_path = args.ids_file or DEFAULT_DOC
    ids = [line.strip() for line in ids_path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")] if args.ids_file else instance_ids(ids_path)
    if not ids or len(set(ids)) != len(ids):
        raise SystemExit(f"expected a non-empty list of unique IDs, found {len(ids)} entries and {len(set(ids))} unique IDs")
    commit = ensure_upstream(args.upstream_dir, ids)
    dataset_cache = args.output_dir / "data" / "dataset_rows.json"
    rows = fetch_rows(dataset_cache, set(ids), refresh=args.refresh_dataset)
    dataset_cache_sha256 = sha256_file(dataset_cache)
    pull_ids = set(ids)
    if args.pull_images_file:
        pull_ids = {line.strip() for line in args.pull_images_file.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}
    preflight_ids = set(ids)
    if args.preflight_ids_file:
        preflight_ids = {line.strip() for line in args.preflight_ids_file.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}
    summary: list[dict[str, Any]] = []
    for instance_id in ids:
        source = args.upstream_dir / "v2" / "tasks" / instance_id
        task_root = args.output_dir / "tasks" / instance_id
        stage1_root = args.output_dir / "data" / "stage1" / instance_id
        if not source.is_dir() or instance_id not in rows:
            reason = []
            if not source.is_dir():
                reason.append("not present in pinned v2/tasks tree")
            if instance_id not in rows:
                reason.append("not present in ScaleAI/SWE-bench_Pro default/test metadata")
            missing_report = {
                "instance_id": instance_id,
                "status": "unavailable",
                "reasons": reason,
                "source": {"repository": UPSTREAM_URL, "commit": commit, "expected_path": f"v2/tasks/{instance_id}"},
                "dataset": {"name": "ScaleAI/SWE-bench_Pro", "config": "default", "split": "test", "row_present": False},
                "note": "No replacement was selected automatically; this preserves the requested ID and provenance.",
                "generated_at_utc": now(),
            }
            write_json(stage1_root / "provenance.json", missing_report)
            summary.append({"instance_id": instance_id, "status": "unavailable", "reasons": reason})
            continue
        original = task_root / "original"
        if original.exists():
            old_hash, _ = tree_hash(original)
            # Never mutate an existing original; replace only if it exactly matches source.
            source_hash, _ = tree_hash(source)
            if old_hash != source_hash:
                raise RuntimeError(f"immutable original differs for {instance_id}; remove it explicitly to re-materialize")
        else:
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, original)
        check = structural_check(original)
        row = rows[instance_id]
        image = image_name(original, row)
        image_info = image_evidence(image, pull=args.pull_images and instance_id in pull_ids)
        provenance = {
            "instance_id": instance_id,
            "source": {"repository": UPSTREAM_URL, "commit": commit, "path": f"v2/tasks/{instance_id}"},
            "dataset": {"name": "ScaleAI/SWE-bench_Pro", "config": "default", "split": "test", "version": row.get("version"), "cache_sha256": dataset_cache_sha256, "row_sha256": hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()},
            "original": {"tree_sha256": check["tree_sha256"], "file_count": check["file_count"]},
            "image": image_info,
            "generated_at_utc": now(),
        }
        run_source = args.output_dir / "runs" / instance_id / "source"
        if run_source.is_dir():
            # Stage 2 already owns this source. Do not recreate a duplicate
            # Stage 1 copy or rewrite evidence used by an active conversion.
            if not (run_source / "problem_statement.md").is_file():
                raise RuntimeError(f"incomplete promoted source: {run_source}")
        else:
            write_json(stage1_root / "source" / "provenance.json", provenance)
            write_json(stage1_root / "source" / "dataset_row.json", row)
            write_source_contract(stage1_root, row, original / "instruction.md")
        existing_preflight_report = stage1_root / "preflight" / "report.json"
        if existing_preflight_report.is_file():
            preflight = json.loads(existing_preflight_report.read_text(encoding="utf-8")).get("preflight", {"status": "not_run"})
        else:
            preflight = {"status": "not_run", "reason": "ID not selected for preflight"}
        if args.preflight and instance_id in preflight_ids:
            preflight = run_harbor_preflight(args.upstream_dir, instance_id, task_root=stage1_root, original_root=original, image=image, engine=args.preflight_engine, evidence_root=stage1_root)
        write_json(stage1_root / "preflight" / "report.json", {"structural": check, "preflight": preflight})
        summary.append({"instance_id": instance_id, "structural": check["status"], "image": image_info["status"], "preflight": preflight["status"], "tree_sha256": check["tree_sha256"]})
    structural_ok = all(x.get("structural") == "pass" for x in summary)
    images_ok = structural_ok and all(x.get("image") == "present" for x in summary)
    preflight_ok = images_ok and all(x.get("preflight") == "pass" for x in summary)
    status = "READY" if preflight_ok else ("STRUCTURAL_READY" if structural_ok else "NOT_READY")
    report = {"status": status, "instance_count": len(summary), "available_count": sum(x.get("status") != "unavailable" for x in summary), "unavailable_count": sum(x.get("status") == "unavailable" for x in summary), "image_present_count": sum(x.get("image") == "present" for x in summary), "preflight_pass_count": sum(x.get("preflight") == "pass" for x in summary), "upstream_commit": commit, "dataset_version": "2.0.0", "dataset_cache_sha256": dataset_cache_sha256, "summary": summary, "generated_at_utc": now()}
    write_json(args.output_dir / "preparation_report.json", report)
    write_json(args.output_dir / "data" / "preparation_report.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] in {"READY", "STRUCTURAL_READY"} else 2


def run_harbor_preflight(upstream: Path, instance_id: str, *, task_root: Path | None = None, original_root: Path | None = None, image: str | None = None, engine: str = "auto", evidence_root: Path | None = None) -> dict[str, Any]:
    harbor = shutil.which("harbor")
    if engine == "docker" or (engine == "auto" and not harbor):
        if task_root is None:
            return {"status": "unavailable", "reason": "task_root required for Docker preflight"}
        return run_docker_preflight(task_root, image, original_root=original_root, evidence_root=evidence_root)
    if not harbor:
        return {"status": "unavailable", "reason": "harbor executable not found; Base/Gold not executed"}
    results: dict[str, Any] = {"status": "not_run", "runs": {}}
    for label, agent in (("base", "nop"), ("gold", "oracle")):
        command = [harbor, "run", "-p", str(upstream / "v2" / "tasks"), "-i", instance_id, "-e", "local", "-n", "1", "-a", agent]
        proc = run(command, check=False)
        results["runs"][label] = {"command": command, "returncode": proc.returncode, "output": proc.stdout[-12000:]}
    base = results["runs"]["base"]["returncode"]
    gold = results["runs"]["gold"]["returncode"]
    results["status"] = "pass" if base != 0 and gold == 0 else "fail"
    results["expected"] = "Base FAIL and Gold PASS"
    return results


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"prepare_swebench_pro_v2: error: {exc}", file=sys.stderr)
        raise SystemExit(1)
