#!/usr/bin/env python3
"""Run local Base/Gold preflight as selected images become available."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
from pathlib import Path

from prepare_swebench_pro_v2 import image_name, run_docker_preflight, write_json

ROOT = Path(__file__).resolve().parents[1]


def ready(image: str) -> bool:
    return subprocess.run(["docker", "image", "inspect", image],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30).returncode == 0


def preflight(instance_id: str, image: str, repeat: bool) -> dict:
    root = ROOT / "data/stage1" / instance_id
    report_path = root / "preflight/report.json"
    report = json.loads(report_path.read_text())
    old = report.get("preflight", {})
    if not repeat and old.get("status") == "pass":
        return {"instance_id": instance_id, "status": "pass", "reused": True}
    original = ROOT / "tasks" / instance_id / "original"
    result = run_docker_preflight(root, image, original_root=original, evidence_root=root)
    report["preflight"] = result
    write_json(report_path, report)
    provenance_path = root / "source/provenance.json"
    if provenance_path.exists():
        provenance = json.loads(provenance_path.read_text())
        inspect = subprocess.run(["docker", "image", "inspect", image, "--format", "{{json .RepoDigests}}"],
                                 capture_output=True, text=True, timeout=30)
        provenance["image"] = {"image": image, "status": "present",
                               "repo_digests": json.loads(inspect.stdout) if inspect.returncode == 0 else []}
        write_json(provenance_path, provenance)
    return {"instance_id": instance_id, "status": result["status"],
            "base_returncode": result.get("runs", {}).get("base", {}).get("returncode"),
            "gold_returncode": result.get("runs", {}).get("gold", {}).get("returncode"),
            "classification": result.get("classification")}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ids-file", type=Path, default=ROOT / "task_list/selected_100.txt")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--repeat", action="store_true")
    args = p.parse_args()
    ids = [s.strip() for s in args.ids_file.read_text().splitlines() if s.strip()]
    rows = {row["instance_id"]: row for row in json.loads((ROOT / "data/dataset_rows.json").read_text())["rows"]}
    pending = set(ids)
    running = {}
    results = {}
    summary_path = ROOT / "data/stage1/preflight_100_summary.json"
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        while pending or running:
            for instance_id in ids:
                if instance_id not in pending or len(running) >= args.workers:
                    continue
                image = rows[instance_id]["docker_image"]
                if (ROOT / "tasks" / instance_id / "original").is_dir() and ready(image):
                    future = pool.submit(preflight, instance_id, image, args.repeat)
                    running[future] = instance_id
                    pending.remove(instance_id)
            if running:
                done, _ = wait(running, timeout=10, return_when=FIRST_COMPLETED)
                for future in done:
                    instance_id = running.pop(future)
                    try:
                        result = future.result()
                    except Exception as exc:
                        result = {"instance_id": instance_id, "status": "error", "error": repr(exc)}
                    results[instance_id] = result
                    print(f"{len(results)}/{len(ids)} {result['status']} {instance_id}", flush=True)
                    write_json(summary_path, {
                        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                        "count": len(ids), "completed_count": len(results),
                        "results": [results[i] for i in ids if i in results],
                    })
            else:
                time.sleep(10)
    return 0 if all(x["status"] == "pass" for x in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
