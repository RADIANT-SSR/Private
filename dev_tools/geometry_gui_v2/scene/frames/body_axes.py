"""Target body-frame axes triad.

Phase 1: three short tubes at the target origin along ±X / ±Y / ±Z, in
``BODY_AXES_COLOR``. Length = ``BODY_AXES_LENGTH_FRACTION × max(target
characteristic length)``. Phase 5's frame switcher animates these tubes
in/out when the user toggles between body / world / sensor frames.
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene.vectors._tube import add_tube


def _characteristic_length(state: SceneState) -> float:
    return max(
        state.target_radius_m,
        state.target_length_m,
        state.target_width_m,
        state.target_height_m,
        state.target_base_radius_m,
        1.0,
    )


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    L = _characteristic_length(state) * style.BODY_AXES_LENGTH_FRACTION
    origin = np.zeros(3, dtype=np.float64)
    for axis_idx, name in ((0, "body_axis_x"), (1, "body_axis_y"), (2, "body_axis_z")):
        end = np.zeros(3, dtype=np.float64)
        end[axis_idx] = L
        add_tube(plotter, origin, end, color=style.BODY_AXES_COLOR, name=name)
