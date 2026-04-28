"""Reference-frame triads — body axes only (T4 moved world axes to a gnomon).

Per Rule 19 / C5: one file per frame triad. Phase-1 also shipped a 3D
world-axes triad at the world origin, but because the v2 scene is
target-centric the world origin coincides with the body origin and the
two triads overlapped into a six-tube tangle. T4 of the visual
remediation relocates the world frame to a screen-space gnomon in the
bottom-left of the viewport (see ``scene/widgets/world_axes_gnomon.py``)
and removes the in-scene primitive entirely.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dev_tools.geometry_gui_v2.app.state import SceneState

if TYPE_CHECKING:
    import pyvista as pv


def add_to_plotter(plotter: "pv.Plotter", state: SceneState) -> None:
    from dev_tools.geometry_gui_v2.scene.frames import body_axes

    body_axes.add_to_plotter(plotter, state)
