"""World-frame axes triad — anchored at the world origin.

Phase 1: three slightly longer tubes along ±X / ±Y / ±Z in
``WORLD_AXES_COLOR``. Origin coincides with the target in this scene
(target-centric framing); the world axes therefore share the origin
with the body axes but use a different color and a longer scale to read
as a separate triad.
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene.frames.body_axes import _characteristic_length
from dev_tools.geometry_gui_v2.scene.vectors._tube import add_tube


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    L = _characteristic_length(state) * style.WORLD_AXES_LENGTH_FRACTION
    origin = np.zeros(3, dtype=np.float64)
    for axis_idx, name in ((0, "world_axis_x"), (1, "world_axis_y"), (2, "world_axis_z")):
        end = np.zeros(3, dtype=np.float64)
        end[axis_idx] = L
        add_tube(plotter, origin, end, color=style.WORLD_AXES_COLOR, name=name)
