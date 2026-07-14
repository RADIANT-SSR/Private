"""Background-point glyph.

Phase 1: a small ``pv.Sphere`` at the schematic background-marker position
(currently along the anti-sun ray; see ``scene/_directions.py``). Drawn
in the surface family color to read as "the thing the sun-to-background
ray terminates on".

Round-3 S5: the glyph is anchored at ``target_centroid + display *
direction`` so it stays at a consistent schematic distance from the
lifted target. ``display`` grows with target altitude via
``scene/_display_distance.py``.
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from radiant.gui.viewer.scene import style
from radiant.gui.viewer.scene._directions import background_direction_scene
from radiant.gui.viewer.scene._display_distance import schematic_display_distance_m
from radiant.gui.viewer.scene._layout import SCENE_BACKGROUND_DISTANCE_M
from radiant.gui.viewer.scene.target._pose import target_centroid_scene
from radiant.gui.viewer.viewer_state import ViewerState as SceneState


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    # Phase-7 diet: the background marker is only meaningful when there
    # *is* a background. With ``background_kind="none"`` the glyph and
    # its companion ``vec_sun_to_background`` were drawing along an
    # arbitrary anti-sun direction with no physical referent.
    if state.background_kind == "none":
        return
    direction = background_direction_scene(state)
    distance = schematic_display_distance_m(state, SCENE_BACKGROUND_DISTANCE_M)
    target_pos = np.array(target_centroid_scene(state), dtype=np.float64)
    pos = target_pos + direction * distance
    glyph = pv.Sphere(radius=0.25, center=tuple(pos), theta_resolution=18, phi_resolution=18)
    plotter.add_mesh(glyph, color=style.SURFACE_FAMILY, name="glyph_background")
