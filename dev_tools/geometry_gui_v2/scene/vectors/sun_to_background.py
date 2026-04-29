"""Sun → background vector ``s_B`` — sun illuminating the background marker.

Phase 1: tube from the sun glyph position to the background marker
position. Same SOLAR_FAMILY color as the primary sun ray, dashed-companion
weight (Phase 3 wires the dashed style; Phase 1 uses the same tube).
"""

from __future__ import annotations

import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene._directions import (
    background_direction_scene,
    sun_direction_scene,
)
from dev_tools.geometry_gui_v2.scene._layout import (
    SCENE_BACKGROUND_DISTANCE_M,
    SCENE_SUN_DISTANCE_M,
)
from dev_tools.geometry_gui_v2.scene.vectors._tube import add_vector_with_arrow


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    # Phase-7 diet: the s_B ray only renders when there is a background.
    if state.background_kind == "none":
        return
    sun_pos = sun_direction_scene(state) * SCENE_SUN_DISTANCE_M
    bg_pos = background_direction_scene(state) * SCENE_BACKGROUND_DISTANCE_M
    add_vector_with_arrow(
        plotter,
        sun_pos,
        bg_pos,
        color=style.SOLAR_FAMILY,
        name="vec_sun_to_background",
    )
