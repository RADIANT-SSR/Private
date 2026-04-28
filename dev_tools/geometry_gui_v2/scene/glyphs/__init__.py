"""Schematic glyph primitives — observer (satellite), sun, background marker.

Per Rule 19 / C5: one file per glyph. Phase 1 ships fixed-world-size
meshes for shape identification; Phase 3 moves them to screen-space
sizing per ``style.SAT_GLYPH_SIZE`` / ``SUN_DISC_SIZE``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dev_tools.geometry_gui_v2.app.state import SceneState

if TYPE_CHECKING:
    import pyvista as pv


def add_to_plotter(plotter: "pv.Plotter", state: SceneState) -> None:
    from dev_tools.geometry_gui_v2.scene.glyphs import background, observer, sun

    observer.add_to_plotter(plotter, state)
    sun.add_to_plotter(plotter, state)
    background.add_to_plotter(plotter, state)
