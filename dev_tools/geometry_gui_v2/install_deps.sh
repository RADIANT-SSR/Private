#!/usr/bin/env bash
# Install RADIANT Geometry GUI v2 dependencies into the active environment.
#
# Run this once before running the v2 test suite or launching the app.
# The harness sandbox blocks pip install during automated runs, so this
# script exists as a manual step the user runs themselves.
#
# Per PLAN_v2.md §8 step 5: pin to versions known to work together.

set -euo pipefail

pip install \
    "pyvista>=0.43" \
    "pyvistaqt>=0.11" \
    "PySide6>=6.7" \
    "numpy>=1.24" \
    "qt-material>=2.14" \
    "pytest>=7" \
    "pytest-qt>=4" \
    pytest-image-diff
# Notes:
#   * PySide6 6.5.x requires Python <3.12; 6.7+ supports 3.12 cleanly. Recommended interpreter is Python 3.12.
#   * pytest-image-diff has no version floor — max published version on PyPI is 0.0.14.

echo
echo "Done. Verify with:"
echo "  python -c 'import pyvista, PySide6, pyvistaqt; print(pyvista.__version__, PySide6.__version__, pyvistaqt.__version__)'"
echo "  pytest dev_tools/geometry_gui_v2/tests/ -v"
echo "  python -m dev_tools.geometry_gui_v2.app.main"
