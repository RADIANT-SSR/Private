"""Phase-angle arc ``alpha_t`` — angle between sun and observer at the target.

Phase 1: great-arc tube from the sun direction to the observer direction
at ``ARC_RADIUS_M``. Drawn in ``TARGET_VECTOR_FAMILY`` (desaturated teal),
the v1 convention for the at-target phase angle.
"""

from __future__ import annotations

import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene._directions import (
    observer_direction_scene,
    sun_direction_scene,
)
from dev_tools.geometry_gui_v2.scene._layout import ARC_RADIUS_M
from dev_tools.geometry_gui_v2.scene.arcs._arc import add_great_arc


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    add_great_arc(
        plotter,
        sun_direction_scene(state),
        observer_direction_scene(state),
        radius=ARC_RADIUS_M,
        color=style.TARGET_VECTOR_FAMILY,
        name="arc_phase_angle",
    )
