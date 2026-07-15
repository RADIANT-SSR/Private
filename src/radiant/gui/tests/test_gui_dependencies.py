"""Dependency-hygiene guard for the GUI package (GUI plan Phase 9, CU-134).

The 2D ``QPainter`` schematic viewer (ADR-0007) replaced the PyVista/VTK 3D viewer, and
the ``pyvista`` / ``pyvistaqt`` pins were dropped from the ``gui`` extra. This test guards
that no module anywhere under ``radiant.gui`` imports pyvista / pyvistaqt / vtk, so the
extra never silently regrows the heavy native dependency (a mechanical grep across the
whole package, broadening the viewer-only ``test_no_pyvista_import_in_viewer``).
"""

from __future__ import annotations

import re
from pathlib import Path

# A top-level ``import pyvista`` / ``from pyvistaqt import ...`` / ``import vtk`` line.
_PV_RE = re.compile(r"^\s*(?:from|import)\s+(pyvista|pyvistaqt|vtk)\b", re.MULTILINE)


def test_no_pyvista_import_in_gui() -> None:
    """No file under ``radiant.gui`` imports pyvista / pyvistaqt / vtk (CU-134)."""
    gui_root = Path(__file__).resolve().parents[1]
    offenders: dict[str, list[str]] = {}
    for path in gui_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        hits = _PV_RE.findall(path.read_text(encoding="utf-8"))
        if hits:
            offenders[str(path)] = hits
    assert not offenders, f"pyvista/pyvistaqt/vtk imports remain under radiant.gui: {offenders}"
