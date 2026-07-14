"""Observer (satellite) glyph — diamond facing the boresight.

Phase 3 (PLAN_v2.md §11 step 6): a 4-sided ``vtk.vtkRegularPolygonSource``
diamond with white fill and ``SATELLITE_FAMILY`` outline. The diamond is
oriented so its normal points along the boresight (target → observer)
unit vector, which matches the user expectation that the satellite icon
"faces the camera looking toward the target".

Round-3 S5 (PLAN_v2_remediation_round3.md §7): the glyph is now anchored
at ``target_centroid + display_distance * direction`` instead of
``direction * SCENE_OBSERVER_DISTANCE_M``. Pre-S5 the lifted target at
high altitude (z ≈ 4–5 m) overlapped the satellite glyph at its fixed
world-space position. ``display_distance`` is sourced from
``scene/_display_distance.py``, which grows the schematic distance with
target altitude so the glyph remains visibly above the target.

Screen-space sizing (PLAN_v2.md §11 step 3) is a Phase 5 interactive
concern; for now the glyph has a fixed world-space radius so the static
goldens are deterministic.
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from radiant.gui.viewer.scene import palette, style
from radiant.gui.viewer.scene._directions import observer_direction_scene
from radiant.gui.viewer.scene._display_distance import schematic_display_distance_m
from radiant.gui.viewer.scene._layout import SCENE_OBSERVER_DISTANCE_M
from radiant.gui.viewer.scene.target._pose import target_centroid_scene
from radiant.gui.viewer.viewer_state import ViewerState as SceneState

_DIAMOND_RADIUS_M = 0.30


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    direction = observer_direction_scene(state)
    distance = schematic_display_distance_m(state, SCENE_OBSERVER_DISTANCE_M)
    target_pos = np.array(target_centroid_scene(state), dtype=np.float64)
    pos = target_pos + direction * distance
    diamond = pv.Polygon(
        center=tuple(pos),
        radius=_DIAMOND_RADIUS_M,
        normal=tuple(direction),
        n_sides=4,
    )
    plotter.add_mesh(
        diamond,
        color=palette.OBSERVER_FILL,
        show_edges=True,
        edge_color=style.SATELLITE_FAMILY,
        line_width=2.0,
        name="glyph_observer",
    )
