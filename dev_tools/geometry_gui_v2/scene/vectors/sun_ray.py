"""Sun-direction vector ``s_t`` — target → sun.

Phase 1: tube from the target origin to the sun glyph position. Phase 2
adds the directional light wired to the same direction so the lit
hemisphere on the target body matches this vector visually.
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene._directions import sun_direction_scene
from dev_tools.geometry_gui_v2.scene._layout import SCENE_SUN_DISTANCE_M
from dev_tools.geometry_gui_v2.scene.vectors._tube import add_vector_with_arrow


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    direction = sun_direction_scene(state)
    end = direction * SCENE_SUN_DISTANCE_M
    # Round-2 R5: re-enable the not-to-scale break-mark. The schematic
    # 9 m sun distance is standing in for 1 AU; the break-mark conveys
    # that in-canvas. See boresight.py for the full rationale.
    add_vector_with_arrow(
        plotter,
        np.zeros(3, dtype=np.float64),
        end,
        color=style.SOLAR_FAMILY,
        name="vec_sun_ray",
        with_break_mark=True,
    )
