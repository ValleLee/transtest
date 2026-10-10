#!/usr/bin/env python3
"""Create the project-local Python 3.12 environment and credential template."""
from __future__ import annotations
import argparse, os, shutil, subprocess, sys
from pathlib import Path

from ..paths import PROJECT_ROOT as ROOT
PYTHON_CANDIDATES=(
    os.environ.get("SWEPRO_PYTHON", ""),
    shutil.which("python3.12") or "",
    sys.executable,
)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--skip-install',action='store_true'); a=p.parse_args(argv)
    venv=ROOT/'.venv'; env=ROOT/'.env'; template=ROOT/'.env.example'
    if not venv.exists():
        interpreter=next((Path(x) for x in PYTHON_CANDIDATES if x and Path(x).is_file()),None)
        if interpreter is None: raise SystemExit('Python 3.12 is required; set SWEPRO_PYTHON to its executable')
        subprocess.run([str(interpreter),'-m','venv',str(venv)],check=True)
    if not env.exists():
        shutil.copy2(template,env); env.chmod(0o600)
        print(f'created {env}; fill its endpoint credentials before running a model role')
    if not a.skip_install:
        pip=venv/'bin'/'pip'
        if not pip.exists():
            subprocess.run([str(venv/'bin'/'python'), '-m', 'ensurepip', '--default-pip'], check=True)
        subprocess.run([str(pip),'install','-e',str(ROOT)],check=True)
    print(f'virtualenv: {venv}')
    print(f'python: {venv / "bin" / "python"}')
    print(f'mini-swe-agent check: {venv / "bin" / "python"} -c "import minisweagent"')
    return 0
if __name__=='__main__': raise SystemExit(main())
