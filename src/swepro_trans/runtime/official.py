#!/usr/bin/env python3
"""Run the official Harbor v0.22 oracle action when its CLI is installed.

This wrapper never silently falls back to the local Docker preflight. Harbor
requires Python >=3.12 and is intentionally kept as a pinned checkout under
``upstream/harbor``.
"""
from __future__ import annotations
import argparse, shutil, subprocess, sys
from pathlib import Path

from ..paths import PROJECT_ROOT as ROOT
HARBOR=ROOT/'upstream/harbor'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--instance-id', required=True)
    ap.add_argument('--tasks-root', type=Path, default=ROOT/'tasks')
    ap.add_argument('--job-name', default='swepro-v2-oracle')
    args=ap.parse_args()
    harbor=shutil.which('harbor')
    if harbor is None:
        raise SystemExit('official Harbor CLI is not installed; use Python >=3.12 and install upstream/harbor v0.22.0, then rerun this command')
    cmd=[harbor,'run','-p',str(args.tasks_root),'-i',args.instance_id,'-e','docker','-n','1','-a','oracle','--job-name',args.job_name]
    print('Executing official Harbor:', ' '.join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT).returncode

if __name__=='__main__': raise SystemExit(main())
