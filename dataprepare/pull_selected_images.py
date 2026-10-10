#!/usr/bin/env python3
"""Pull missing official V2 images for a selected task list into local Docker."""
from __future__ import annotations

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_image(instance_id: str, image: str, log_dir: Path) -> dict:
    inspect = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{json .RepoDigests}}"],
        capture_output=True, text=True, timeout=30,
    )
    if inspect.returncode == 0:
        return {"instance_id": instance_id, "image": image, "status": "present", "repo_digests": json.loads(inspect.stdout)}
    output = ""
    for attempt in range(1, 4):
        try:
            proc = subprocess.run(["docker", "pull", image], capture_output=True, text=True, timeout=1800)
            output += f"ATTEMPT {attempt}, rc={proc.returncode}\n{proc.stdout}\n{proc.stderr}\n"
            if proc.returncode == 0:
                break
        except subprocess.TimeoutExpired as exc:
            output += f"ATTEMPT {attempt}, timeout: {exc}\n"
    (log_dir / f"{instance_id}.log").write_text(output)
    inspect = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{json .RepoDigests}}"],
        capture_output=True, text=True, timeout=30,
    )
    if inspect.returncode:
        return {"instance_id": instance_id, "image": image, "status": "failed", "error": output[-2000:]}
    return {"instance_id": instance_id, "image": image, "status": "pulled", "repo_digests": json.loads(inspect.stdout)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids-file", type=Path, default=ROOT / "task_list/selected_100.txt")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    ids = [s.strip() for s in args.ids_file.read_text().splitlines() if s.strip()]
    rows = {row["instance_id"]: row for row in json.loads((ROOT / "data/dataset_rows.json").read_text())["rows"]}
    log_dir = ROOT / "data/stage1/image_pull_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_image, i, rows[i]["docker_image"], log_dir): i for i in ids}
        for future in as_completed(futures):
            try:
                item = future.result()
            except Exception as exc:
                item = {"instance_id": futures[future], "status": "failed", "error": repr(exc)}
            results.append(item)
            print(f"{len(results)}/{len(ids)} {item['status']} {item['instance_id']}", flush=True)
            summary_path = ROOT / "data/stage1/image_pull_summary.json"
            temporary = summary_path.with_name(summary_path.name + ".tmp")
            temporary.write_text(json.dumps({
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                "count": len(ids), "completed_count": len(results),
                "results": sorted(results, key=lambda x: ids.index(x["instance_id"])),
            }, indent=2) + "\n")
            temporary.replace(summary_path)
    return 0 if all(x["status"] in {"present", "pulled"} for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
