"""Sun glyph — disc body + 8 rays at 45° increments.

Round-2 R3 (PLAN_v2_remediation_round2.md §4): a small ``pv.Disc`` for
the body plus 8 short ``pv.Tube`` rays at 45° around the disc, all in
``SOLAR_FAMILY`` amber and rendered with ``lighting=False`` so the
glyph reads as an icon rather than a physical body.

The Phase-7 diet pass had collapsed the glyph to a single shaded
sphere, which on the round-2 first-cut screenshot read as "a second
celestial body" rather than "the sun symbol". The disc + rays
restoration is part of round 2.

Sizing: world-space, scaled so the glyph reads at roughly 24 px /
8 px (disc diameter / ray length) at the round-2 default camera
distance for the default state (~17 m). True screen-space sizing
(via ``vtkActor2D`` or a camera-change callback) is deferred — this
file documents that deferral as CU-056; the user-visible difference
is that zooming in/out scales the glyph with the rest of the scene
rather than nailing it to fixed pixels. The icon nature of the disc
+ rays survives the zoom because the proportions stay correct.

The disc face is oriented toward the target (its normal points along
``-sun_direction_scene``). At the round-2 isometric pose this
approximates camera-facing because the camera looks roughly toward
the target from the iso direction.
"""

from __future__ import annotations

import math

import numpy as np
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene._directions import sun_direction_scene
from dev_tools.geometry_gui_v2.scene._display_distance import schematic_display_distance_m
from dev_tools.geometry_gui_v2.scene._layout import SCENE_SUN_DISTANCE_M
from dev_tools.geometry_gui_v2.scene.target._pose import target_centroid_scene

# World-space sizes — see module docstring for the screen-space rationale.
_DISC_OUTER_RADIUS_M = 0.30
_RAY_INNER_M = 0.40
_RAY_OUTER_M = 0.65
_RAY_TUBE_RADIUS_M = 0.025
_NUM_RAYS = 8

# Disc fill color: a slightly brighter amber than ``SOLAR_FAMILY`` so the
# disc body stands out from the rays in the rendered icon. ``SOLAR_FAMILY``
# is ``#C28A1F``; this lifts the lightness without shifting hue.
_DISC_FILL_COLOR = "#E5A732"


def _orthonormal_basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return two unit vectors that, with ``normal``, span 3D space.

    The disc plane is the span of these two vectors. Picks
    ``world_up = (0, 0, 1)`` as the seed unless ``normal`` is nearly
    parallel to it, in which case ``world_x = (1, 0, 0)`` is used.
    """
    n = normal / np.linalg.norm(normal)
    seed = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(n, seed)) > 0.95:
        seed = np.array([1.0, 0.0, 0.0])
    e1 = seed - np.dot(seed, n) * n
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    return e1, e2


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    """Add the disc + 8 rays to the plotter as the sun glyph.

    Single ``add_mesh`` per actor so the existing
    ``actors_for_primitive("glyph_sun")`` enumerator keeps working —
    the disc actor is named ``glyph_sun`` and the 8 ray actors are
    ``glyph_sun_ray_0`` … ``glyph_sun_ray_7``.
    """
    direction = sun_direction_scene(state)
    distance = schematic_display_distance_m(state, SCENE_SUN_DISTANCE_M)
    target_pos = np.array(target_centroid_scene(state), dtype=np.float64)
    # S5: anchor relative to the lifted target centroid (not the world
    # origin) and grow the distance with altitude so the disc stays
    # visibly above the target. See ``scene/_display_distance.py``.
    pos = target_pos + direction * distance

    # Disc face points back toward the target (= camera-ish at iso pose).
    disc_normal = -direction
    disc = pv.Disc(
        center=tuple(pos),
        inner=0.0,
        outer=_DISC_OUTER_RADIUS_M,
        normal=tuple(disc_normal),
        r_res=1,
        c_res=48,
    )
    plotter.add_mesh(
        disc,
        color=_DISC_FILL_COLOR,
        lighting=False,
        name="glyph_sun",
    )

    e1, e2 = _orthonormal_basis(disc_normal)
    for i in range(_NUM_RAYS):
        angle = 2.0 * math.pi * i / _NUM_RAYS
        radial = math.cos(angle) * e1 + math.sin(angle) * e2
        start = pos + _RAY_INNER_M * radial
        end = pos + _RAY_OUTER_M * radial
        line = pv.Line(tuple(start), tuple(end), resolution=1)
        tube = line.tube(radius=_RAY_TUBE_RADIUS_M, n_sides=8)
        plotter.add_mesh(
            tube,
            color=style.SOLAR_FAMILY,
            lighting=False,
            name=f"glyph_sun_ray_{i}",
        )
