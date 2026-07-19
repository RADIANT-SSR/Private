#!/usr/bin/env python
"""Install RADIANT Geometry GUI v2 dependencies into the active environment.

Cross-platform (Rule 30) replacement for the former ``install_deps.sh`` — runs
identically on Windows and macOS/Linux. Run once before the v2 test suite or
launching the app::

    python dev_tools/geometry_gui_v2/install_deps.py

Versions are pinned in the sibling ``requirements.txt`` (PLAN_v2.md §8 step 5).
The harness sandbox blocks ``pip install`` during automated runs, so this is a
manual step the user runs themselves.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REQUIREMENTS = Path(__file__).with_name("requirements.txt")


def main() -> int:
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(_REQUIREMENTS)]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        return result.returncode
    print("\nDone. Verify with:")
    print(
        '  python -c "import pyvista, PySide6, pyvistaqt; '
        'print(pyvista.__version__, PySide6.__version__, pyvistaqt.__version__)"'
    )
    print("  pytest dev_tools/geometry_gui_v2/tests/ -v")
    print("  python -m dev_tools.geometry_gui_v2.app.main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
