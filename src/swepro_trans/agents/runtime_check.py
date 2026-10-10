"""Check the local runtime without printing credential values."""
from __future__ import annotations
import argparse, importlib.util, shutil, sys
from pathlib import Path

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('--project-root',type=Path,default=Path('.')); p.add_argument('--env-file',type=Path,default=Path('.env')); a=p.parse_args(argv)
    root=a.project_root.resolve(); checks={
      'python_version': f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}',
      'python_ok': sys.version_info >= (3,12),
      'mini_swe_agent_importable': importlib.util.find_spec('minisweagent') is not None,
      'docker_executable': shutil.which('docker') is not None,
      'credentials_file': a.env_file.resolve().is_file(),
      'credentials_mode_600': False,
    }
    if checks['credentials_file']:
      checks['credentials_mode_600']=(a.env_file.resolve().stat().st_mode & 0o077)==0
    checks['status']='pass' if all(checks[k] for k in ('python_ok','mini_swe_agent_importable','docker_executable','credentials_file','credentials_mode_600')) else 'incomplete'
    print(__import__('json').dumps(checks,indent=2)); return 0 if checks['status']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
