"""Boresight vector — target → observer along the look direction.

Phase 1: straight tube from the target origin out to the observer glyph
position (``SCENE_OBSERVER_DISTANCE_M`` along ``observer_direction_scene``).
Phase 3 swaps the tube for ``vector_with_arrow`` and adds the not-to-scale
break-mark.

Round-3 S4 (break-mark visibility): the line now starts at the target
centroid (``target_centroid_scene``) instead of the world origin.
Pre-S4 the line started at ``(0, 0, 0)`` so its midpoint — and the
break-mark anchored there — sat at z≈3 m regardless of target altitude.
With the schematic altitude lift, the lifted target rose to z≈4–5 m at
600+ km altitude, leaving the break-mark below the target and outside
the visible portion of the line. Anchoring the start at the target
centroid keeps the break-mark on the visible portion at every altitude
(plan §6 step 4).
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from radiant.gui.viewer.scene import style
from radiant.gui.viewer.scene._directions import observer_direction_scene
from radiant.gui.viewer.scene._display_distance import schematic_display_distance_m
from radiant.gui.viewer.scene._layout import SCENE_OBSERVER_DISTANCE_M
from radiant.gui.viewer.scene.target._pose import target_centroid_scene
from radiant.gui.viewer.scene.vectors._tube import add_vector_with_arrow
from radiant.gui.viewer.viewer_state import ViewerState as SceneState


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    direction = observer_direction_scene(state)
    start = np.array(target_centroid_scene(state), dtype=np.float64)
    # S5: end-point follows the satellite glyph, which is now anchored
    # at ``target + display * direction`` and grows with altitude. The
    # break-mark midpoint sits at the visible-line midpoint between the
    # lifted target and the (also-lifted) satellite glyph.
    distance = schematic_display_distance_m(state, SCENE_OBSERVER_DISTANCE_M)
    end = start + direction * distance
    # Round-2 R5: re-enable the not-to-scale break-mark. The diet had
    # dropped it, but the round-1 first-cut readout-panel-only treatment
    # left users with no in-canvas indicator that the schematic 6 m
    # observer distance is standing in for ~600 km of physical altitude.
    # The zigzag is now drawn through a real gap in the shaft (see
    # _tube.py with_break_mark branch) so the symbol reads as a kink
    # rather than as noise overlaid on a line.
    add_vector_with_arrow(
        plotter,
        start,
        end,
        color=style.SATELLITE_FAMILY,
        name="vec_boresight",
        with_break_mark=True,
    )
