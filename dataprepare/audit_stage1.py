#!/usr/bin/env python3
"""Audit all selected Stage 1 originals, image digests, and local oracle verdicts."""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from prepare_swebench_pro_v2 import structural_check, write_json

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_LANGUAGES = {"python": 40, "go": 36, "js": 22, "ts": 2}
EXPECTED_HARD = {"python": 2, "go": 2, "js": 2, "ts": 0}
UPSTREAM_COMMIT = "66f92766bba642462d4bbe5479e83f91f9211862"


def row_hash(row: dict) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def audit_one(instance_id: str, row: dict) -> dict:
    reasons = []
    original = ROOT / "tasks" / instance_id / "original"
    if original.is_dir():
        structural = structural_check(original)
        if structural["status"] != "pass":
            reasons.append("original_structure")
    else:
        structural = None
        reasons.append("original_missing")
    provenance_path = ROOT / "data/stage1" / instance_id / "source/provenance.json"
    if not provenance_path.is_file():
        provenance_path = ROOT / "runs" / instance_id / "source/provenance.json"
    if provenance_path.is_file():
        provenance = json.loads(provenance_path.read_text())
        if provenance.get("source", {}).get("commit") != UPSTREAM_COMMIT:
            reasons.append("upstream_commit")
        if provenance.get("dataset", {}).get("row_sha256") != row_hash(row):
            reasons.append("dataset_row_hash")
        if structural and provenance.get("original", {}).get("tree_sha256") != structural["tree_sha256"]:
            reasons.append("original_tree_hash")
    else:
        provenance = None
        reasons.append("provenance_missing")
    image = row["docker_image"]
    proc = subprocess.run(["docker", "image", "inspect", image, "--format", "{{json .RepoDigests}}"],
                          capture_output=True, text=True, timeout=30)
    digests = json.loads(proc.stdout) if proc.returncode == 0 else []
    if not digests:
        reasons.append("image_digest_missing")
    report_path = ROOT / "data/stage1" / instance_id / "preflight/report.json"
    preflight = json.loads(report_path.read_text()).get("preflight", {}) if report_path.is_file() else {}
    base_rc = preflight.get("runs", {}).get("base", {}).get("returncode")
    gold_rc = preflight.get("runs", {}).get("gold", {}).get("returncode")
    if preflight.get("status") != "pass" or base_rc is None or base_rc == 0 or gold_rc != 0:
        reasons.append("oracle_not_passed")
    return {
        "instance_id": instance_id, "language": row["repo_language"], "hard": row["hard"],
        "status": "READY" if not reasons else "NOT_READY", "reasons": reasons,
        "base_returncode": base_rc, "gold_returncode": gold_rc,
        "image": image, "image_digests": digests,
        "provenance_path": str(provenance_path.relative_to(ROOT)) if provenance else None,
        "preflight_path": str(report_path.relative_to(ROOT)),
    }


def main() -> int:
    ids = [s for s in (ROOT / "task_list/selected_100.txt").read_text().splitlines() if s]
    rows = {r["instance_id"]: r for r in json.loads((ROOT / "data/dataset_rows.json").read_text())["rows"]}
    results = [audit_one(i, rows[i]) for i in ids]
    actual_tasks = {p.name for p in (ROOT / "tasks").iterdir() if p.is_dir()}
    languages = Counter(rows[i]["repo_language"] for i in ids)
    hard = Counter(rows[i]["repo_language"] for i in ids if rows[i]["hard"])
    counts_ok = len(ids) == len(set(ids)) == 100 and dict(languages) == EXPECTED_LANGUAGES and all(
        hard[lang] == n for lang, n in EXPECTED_HARD.items()
    )
    all_ready = counts_ok and actual_tasks == set(ids) and all(r["status"] == "READY" for r in results)
    report = {
        "status": "READY" if all_ready else "NOT_READY",
        "selected_count": len(ids), "ready_count": sum(r["status"] == "READY" for r in results),
        "language_counts": dict(languages), "hard_counts": dict(hard),
        "counts_ok": counts_ok, "tasks_directory_exact": actual_tasks == set(ids),
        "extra_task_directories": sorted(actual_tasks - set(ids)),
        "missing_task_directories": sorted(set(ids) - actual_tasks),
        "upstream_commit": UPSTREAM_COMMIT, "docker_root": "/data/docker",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "tasks": results,
    }
    write_json(ROOT / "data/stage1/final_100_report.json", report)
    print(json.dumps({k: report[k] for k in ("status", "selected_count", "ready_count",
                                          "language_counts", "hard_counts", "counts_ok",
                                          "tasks_directory_exact")}, indent=2))
    return 0 if all_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
