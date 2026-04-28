"""Boresight vector — target → observer along the look direction.

Phase 1: straight tube from the target origin out to the observer glyph
position (``SCENE_OBSERVER_DISTANCE_M`` along ``observer_direction_scene``).
Phase 3 swaps the tube for ``vector_with_arrow`` and adds the not-to-scale
break-mark.
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene._directions import observer_direction_scene
from dev_tools.geometry_gui_v2.scene._layout import SCENE_OBSERVER_DISTANCE_M
from dev_tools.geometry_gui_v2.scene.vectors._tube import add_vector_with_arrow


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    direction = observer_direction_scene(state)
    end = direction * SCENE_OBSERVER_DISTANCE_M
    # Break-mark: schematic 6 m vs physical ~600 km satellite distance.
    add_vector_with_arrow(
        plotter,
        np.zeros(3, dtype=np.float64),
        end,
        color=style.SATELLITE_FAMILY,
        name="vec_boresight",
        with_break_mark=True,
    )
