"""Sun glyph — disc body + 8 rays at 45° increments.

Phase 3 (PLAN_v2.md §11 step 5): a small ``pv.Disc`` for the body plus
8 short tube rays at 45° around the disc, all in ``SOLAR_FAMILY``. The
disc faces the target (its normal points along ``-sun_direction_scene``,
i.e. the disc face is what you would see from the target).

Screen-space sizing (PLAN_v2.md §11 step 3) deferred to Phase 5; the
glyph has a fixed world-space radius for static-golden determinism.
"""

from __future__ import annotations

import math

import numpy as np
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene._directions import sun_direction_scene
from dev_tools.geometry_gui_v2.scene._layout import SCENE_SUN_DISTANCE_M

_DISC_INNER_RADIUS_M = 0.0
_DISC_OUTER_RADIUS_M = 0.40
_RAY_INNER_M = 0.50
_RAY_OUTER_M = 0.85
_RAY_TUBE_RADIUS_M = 0.025
_NUM_RAYS = 8


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    direction = sun_direction_scene(state)
    pos = direction * SCENE_SUN_DISTANCE_M

    # Disc faces the target (normal = -sun_direction).
    disc_normal = -direction
    disc = pv.Disc(
        center=tuple(pos),
        inner=_DISC_INNER_RADIUS_M,
        outer=_DISC_OUTER_RADIUS_M,
        normal=tuple(disc_normal),
        r_res=1,
        c_res=32,
    )
    plotter.add_mesh(disc, color=style.SOLAR_FAMILY, name="glyph_sun")

    # Two unit vectors spanning the disc plane (perpendicular to direction).
    up = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(direction, up)) > 0.95:
        up = np.array([1.0, 0.0, 0.0])
    e1 = np.cross(direction, up)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(direction, e1)
    e2 /= np.linalg.norm(e2)

    for k in range(_NUM_RAYS):
        phi = 2.0 * math.pi * k / _NUM_RAYS
        radial = math.cos(phi) * e1 + math.sin(phi) * e2
        start = pos + radial * _RAY_INNER_M
        end = pos + radial * _RAY_OUTER_M
        line = pv.Line(pointa=tuple(start), pointb=tuple(end))
        tube = line.tube(radius=_RAY_TUBE_RADIUS_M)
        plotter.add_mesh(tube, color=style.SOLAR_FAMILY, name=f"glyph_sun_ray_{k}")
