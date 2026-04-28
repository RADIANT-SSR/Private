"""Off-nadir arc — angle between the local zenith (+Z) and the boresight.

Phase 1: great-arc tube from +Z to the observer-direction unit vector
at ``ARC_RADIUS_M``. Drawn in ``SATELLITE_FAMILY`` (the off-nadir angle
is part of the satellite-vector family).
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene._directions import observer_direction_scene
from dev_tools.geometry_gui_v2.scene._layout import ARC_RADIUS_M
from dev_tools.geometry_gui_v2.scene.arcs._arc import add_great_arc


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    zenith = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    obs = observer_direction_scene(state)
    add_great_arc(
        plotter,
        zenith,
        obs,
        radius=ARC_RADIUS_M,
        color=style.SATELLITE_FAMILY,
        name="arc_off_nadir",
    )
