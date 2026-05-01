"""Round-3 S5 regression — satellite glyph stays above the target on screen.

Round-3 §0 defect 5: at high target altitude (the round-three reel's
600 km frame) the satellite glyph appeared *below* the target on screen
even though the look angle should have placed it clearly above. Pre-S5
the satellite glyph was anchored at ``observer_direction * 6 m`` from
the world origin while the target rose to z ≈ 4–5 m via the schematic
altitude lift. The lifted target visually intruded on (and at slant=0,
overlapped) the fixed-position satellite glyph.

The S5 fix anchors the satellite glyph at ``target_centroid +
display_distance * direction`` and grows ``display_distance`` with
altitude (see ``scene/_display_distance.py``). This test verifies the
fix holds across the full altitude sweep: the satellite's display y
coordinate must be greater than the target's (VTK display coords place
the origin at the lower-left, so larger y = higher on screen).
"""

from __future__ import annotations

import dataclasses
from typing import Final

import numpy as np
import pytest
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene.builder import build_scene
from dev_tools.geometry_gui_v2.scene.labels.leader_label import project_world_to_display
from dev_tools.geometry_gui_v2.scene.target._pose import target_centroid_scene


_WINDOW_SIZE: Final[tuple[int, int]] = (1920, 1080)


def _bounds_center(actor: pv.Actor) -> np.ndarray:
    bx = actor.GetBounds()  # (xmin, xmax, ymin, ymax, zmin, zmax)
    return np.array(
        [(bx[0] + bx[1]) * 0.5, (bx[2] + bx[3]) * 0.5, (bx[4] + bx[5]) * 0.5],
        dtype=np.float64,
    )


@pytest.mark.parametrize("alt_km", [0, 1, 10, 100, 600, 2000])
def test_satellite_above_target_at_all_target_altitudes(alt_km: int) -> None:
    """Satellite glyph projects above the target centroid in screen y at
    every altitude in the round-three sweep."""
    state = dataclasses.replace(
        SceneState.default(), target_altitude_m=float(alt_km) * 1_000.0
    )
    p = pv.Plotter(off_screen=True, window_size=_WINDOW_SIZE)
    try:
        build_scene(state, plotter=p)
        p.show(auto_close=False)

        sat_world = _bounds_center(p.actors["glyph_observer"])
        target_world = np.array(target_centroid_scene(state), dtype=np.float64)

        sat_xy = project_world_to_display(p, sat_world)
        target_xy = project_world_to_display(p, target_world)
    finally:
        p.close()

    # VTK display coords: y = 0 is the bottom of the viewport; larger y
    # is higher on screen. The satellite must be above the target.
    assert sat_xy[1] > target_xy[1], (
        f"alt={alt_km} km: satellite y={sat_xy[1]:.1f} px is not above "
        f"target y={target_xy[1]:.1f} px (VTK display coords, larger=up)"
    )
