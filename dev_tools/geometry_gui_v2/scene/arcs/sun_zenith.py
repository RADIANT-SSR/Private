"""Sun-zenith arc — angle between local zenith (+Z) and the sun direction.

Phase 1: great-arc tube from +Z to the sun-direction unit vector at
``ARC_RADIUS_M``. Drawn in ``SOLAR_FAMILY``.
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene._directions import sun_direction_scene
from dev_tools.geometry_gui_v2.scene._layout import ARC_RADIUS_M
from dev_tools.geometry_gui_v2.scene.arcs._arc import add_great_arc


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    zenith = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    add_great_arc(
        plotter,
        zenith,
        sun_direction_scene(state),
        radius=ARC_RADIUS_M,
        color=style.SOLAR_FAMILY,
        name="arc_sun_zenith",
    )
