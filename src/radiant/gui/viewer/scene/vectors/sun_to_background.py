"""Sun → background vector ``s_B`` — sun illuminating the background marker.

Phase 1: tube from the sun glyph position to the background marker
position. Same SOLAR_FAMILY color as the primary sun ray, dashed-companion
weight (Phase 3 wires the dashed style; Phase 1 uses the same tube).

Round-3 S5: sun and background glyphs are now anchored at
``target_centroid + display * direction`` (see
``scene/_display_distance.py``); this line follows the same anchoring
so it always connects the two glyphs cleanly at every altitude.
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from radiant.gui.viewer.scene import style
from radiant.gui.viewer.scene._directions import (
    background_direction_scene,
    sun_direction_scene,
)
from radiant.gui.viewer.scene._display_distance import schematic_display_distance_m
from radiant.gui.viewer.scene._layout import (
    SCENE_BACKGROUND_DISTANCE_M,
    SCENE_SUN_DISTANCE_M,
)
from radiant.gui.viewer.scene.target._pose import target_centroid_scene
from radiant.gui.viewer.scene.vectors._tube import add_vector_with_arrow
from radiant.gui.viewer.viewer_state import ViewerState as SceneState


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    # Phase-7 diet: the s_B ray only renders when there is a background.
    if state.background_kind == "none":
        return
    target_pos = np.array(target_centroid_scene(state), dtype=np.float64)
    sun_pos = target_pos + sun_direction_scene(state) * schematic_display_distance_m(
        state, SCENE_SUN_DISTANCE_M
    )
    bg_pos = target_pos + background_direction_scene(state) * schematic_display_distance_m(
        state, SCENE_BACKGROUND_DISTANCE_M
    )
    add_vector_with_arrow(
        plotter,
        sun_pos,
        bg_pos,
        color=style.SOLAR_FAMILY,
        name="vec_sun_to_background",
    )
