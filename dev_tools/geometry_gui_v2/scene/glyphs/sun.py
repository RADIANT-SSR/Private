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
    # Phase-7 diet: solid sphere glyph, no rays. The 8-ray sunburst was
    # adding 8 actors of visual noise around the orange disc; the
    # reference design uses a single filled circle and lets context
    # (color, position) sell "sun." Sphere is camera-orientation-free
    # so the glyph reads as a disc from every angle without the
    # disc-normal hack the previous version needed.
    direction = sun_direction_scene(state)
    pos = direction * SCENE_SUN_DISTANCE_M
    sphere = pv.Sphere(
        center=tuple(pos),
        radius=_DISC_OUTER_RADIUS_M,
        theta_resolution=24,
        phi_resolution=24,
    )
    plotter.add_mesh(sphere, color=style.SOLAR_FAMILY, name="glyph_sun")
