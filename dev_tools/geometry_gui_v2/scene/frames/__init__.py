"""Reference-frame triads — body axes (target body) and world axes.

Per Rule 19 / C5: one file per frame triad.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dev_tools.geometry_gui_v2.app.state import SceneState

if TYPE_CHECKING:
    import pyvista as pv


def add_to_plotter(plotter: "pv.Plotter", state: SceneState) -> None:
    from dev_tools.geometry_gui_v2.scene.frames import body_axes, world_axes

    body_axes.add_to_plotter(plotter, state)
    world_axes.add_to_plotter(plotter, state)
