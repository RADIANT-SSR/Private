"""Make ``dev_tools.geometry_gui_v2.*`` importable when pytest runs from the repo root.

Mirrors the v1 conftest pattern. ``dev_tools/`` is intentionally outside the
``src/`` layout used by ``radiant`` and has no install hook of its own;
adding the repo root to ``sys.path`` here keeps the dev tool self-contained
without touching the top-level ``pyproject.toml`` or the src tree.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
