"""Make `dev_tools.geometry_gui.*` importable when pytest runs from the repo root.

The project layout uses src-layout for `radiant` (configured via setuptools), but
`dev_tools/` is intentionally outside that package and has no install hook. Adding
the repo root to sys.path here keeps the dev tool self-contained without touching
pyproject.toml or the src tree.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
