"""Surface-normal vector ``n_B`` at the target.

Phase 1: short +Z stub from the target origin (the "local up" at the
target's body frame). Phase 2 may rotate this into the per-shape
relevant facet's normal, but for shape-identification purposes a +Z
stub is unambiguous.
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene.vectors._tube import add_vector_with_arrow


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    # Phase-7 diet: ``n_B`` is the *background* surface normal; with no
    # background it has no referent and just clutters the +Z axis next
    # to the body axes. Renders only when the background is on.
    if state.background_kind == "none":
        return
    length = max(1.5 * state.target_radius_m, 1.5)
    end = np.array([0.0, 0.0, length], dtype=np.float64)
    add_vector_with_arrow(
        plotter,
        np.zeros(3, dtype=np.float64),
        end,
        color=style.SURFACE_FAMILY,
        name="vec_surface_normal",
    )
