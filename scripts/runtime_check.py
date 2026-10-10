#!/usr/bin/env python3
"""Check Python, credentials, Docker, and mini-SWE-agent availability."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from swepro_trans.agents.runtime_check import main
raise SystemExit(main())
