"""Sun-direction vector ``s_t`` — target → sun.

Phase 1: tube from the target origin to the sun glyph position. Phase 2
adds the directional light wired to the same direction so the lit
hemisphere on the target body matches this vector visually.

Round-3 S4 (break-mark visibility): the line now starts at the target
centroid (``target_centroid_scene``) instead of the world origin so
the break-mark anchors on the visible portion of the line at every
target altitude. See ``boresight.py`` for the full root-cause analysis.
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from radiant.gui.viewer.scene import style
from radiant.gui.viewer.scene._directions import sun_direction_scene
from radiant.gui.viewer.scene._display_distance import schematic_display_distance_m
from radiant.gui.viewer.scene._layout import SCENE_SUN_DISTANCE_M
from radiant.gui.viewer.scene.target._pose import target_centroid_scene
from radiant.gui.viewer.scene.vectors._tube import add_vector_with_arrow
from radiant.gui.viewer.viewer_state import ViewerState as SceneState


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    direction = sun_direction_scene(state)
    start = np.array(target_centroid_scene(state), dtype=np.float64)
    # S5: end follows the sun glyph, anchored at ``target + display *
    # direction`` and growing with altitude. See boresight.py.
    distance = schematic_display_distance_m(state, SCENE_SUN_DISTANCE_M)
    end = start + direction * distance
    # Round-2 R5: re-enable the not-to-scale break-mark. The schematic
    # 9 m sun distance is standing in for 1 AU; the break-mark conveys
    # that in-canvas. See boresight.py for the full rationale.
    add_vector_with_arrow(
        plotter,
        start,
        end,
        color=style.SOLAR_FAMILY,
        name="vec_sun_ray",
        with_break_mark=True,
    )
