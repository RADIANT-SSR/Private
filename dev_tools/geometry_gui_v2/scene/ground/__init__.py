"""Ground primitives — flat cap and contact-shadow disc.

Per Rule 19 / C5: one file per ground primitive. Phase 1 ships flat
placeholders; Phase 2 wires the procedural grid texture and the soft
shadow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dev_tools.geometry_gui_v2.app.state import SceneState

if TYPE_CHECKING:
    import pyvista as pv


def add_to_plotter(plotter: "pv.Plotter", state: SceneState) -> None:
    from dev_tools.geometry_gui_v2.scene.ground import cap, contact_shadow

    cap.add_to_plotter(plotter, state)
    contact_shadow.add_to_plotter(plotter, state)
