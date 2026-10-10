"""Small adapter around the Stage 1 preparation helpers.

Stage 2 reuses the official Stage 1 Docker/image policy, but keeps that
compatibility boundary in one module instead of importing a script from every
command.
"""
from __future__ import annotations

import sys
from pathlib import Path

from ..paths import PROJECT_ROOT
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dataprepare.prepare_swebench_pro_v2 import (  # noqa: E402
    image_name,
    run_docker_preflight,
    verifier_network_mode,
    write_json,
)

__all__ = ["image_name", "run_docker_preflight", "verifier_network_mode", "write_json"]
