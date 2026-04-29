"""Default framing policy — extent-driven camera distance.

R2 of round-2 visual remediation: replace the hardcoded
``CANONICAL_DISTANCE_M = 14.0`` with a distance computed from the
actual scene's bounding box so the scene fills the majority of the
canvas regardless of target size or sun/observer geometry.

Inputs we bound:
  * Target body (shape-aware half-extent — sphere radius, cylinder
    half-length, box half-diagonal, etc.)
  * Observer glyph at its *display* position (``SCENE_OBSERVER_DISTANCE_M``
    along the observer direction unit vector — not the physical 600 km
    altitude).
  * Sun glyph at its display position.
  * Background marker at its display position, but only when
    ``state.background_kind != "none"`` (the marker is gated off in
    the default state).

We deliberately exclude the ground cap and fade plane: the cap is
``GROUND_CAP_RADIUS_M = 10 m`` and the fade is 500 m, both of which
would dominate any extent computation. Their job is to *fill* the
background, not to drive framing. The contact-shadow disc on the
ground is similarly not load-bearing for framing.

Pure function. No PyVista or Qt imports. Returns plain numpy arrays
so it is testable without a renderer.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
import numpy.typing as npt

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene._directions import (
    background_direction_scene,
    observer_direction_scene,
    sun_direction_scene,
)
from dev_tools.geometry_gui_v2.scene._layout import (
    SCENE_BACKGROUND_DISTANCE_M,
    SCENE_OBSERVER_DISTANCE_M,
    SCENE_SUN_DISTANCE_M,
)

# Multiplier on the half-extent that gives the camera distance. Empirically
# tuned for PyVista's default 30° vertical FOV at the round-2 isometric
# pose so that:
#   * The full bbox (target + observer + sun) fits within the canvas
#     without clipping on any axis.
#   * The scene fills ≥50% of both canvas dimensions (round-2 plan §3).
# Tuning history: 2.0 clipped the sun/arcs above the canvas top;
# 4.0 fits everything with ~80% canvas fill. R9 re-verifies across all
# 9 canonical views.
DISTANCE_EXTENT_MULTIPLIER: Final[float] = 4.0

# Floor on scene extent. Without this, a degenerate state (zero target,
# observer at zero distance) would produce a zero distance and a
# divide-by-zero downstream.
_MIN_EXTENT_M: Final[float] = 1.0


def _target_half_extent(state: SceneState) -> float:
    """Largest half-dimension of the target's axis-aligned bounding box.

    Shape-aware: sphere uses radius; cylinder uses max(radius, length/2);
    box/flat-plate use half of the longest edge; cone uses
    max(base_radius, height/2). Conservative — for off-axis primitives
    the diagonal would be slightly larger, but the framing policy
    multiplies by 2.0 so the slack is more than enough.
    """
    kind = state.target_shape
    if kind == "sphere":
        return state.target_radius_m
    if kind == "cylinder":
        return max(state.target_radius_m, state.target_length_m / 2.0)
    if kind == "cone":
        return max(state.target_base_radius_m, state.target_height_m / 2.0)
    if kind == "box":
        return max(
            state.target_width_m / 2.0,
            state.target_length_m / 2.0,
            state.target_height_m / 2.0,
        )
    if kind == "flat_plate":
        return max(state.target_width_m / 2.0, state.target_length_m / 2.0)
    return 1.0


def scene_bounds(
    state: SceneState,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Axis-aligned bounding box of every primitive that affects framing.

    Returns ``(bbox_min, bbox_max)`` — each a length-3 ``np.ndarray``.

    Includes the target body half-extent expressed as a cube around
    the origin (the target centroid is always at the origin in the
    visual scene frame), the observer glyph at its display position,
    the sun glyph at its display position, and — when not gated off —
    the background marker at its display position. Excludes the ground
    cap, fade plane, and contact shadow (see module docstring).
    """
    points: list[np.ndarray] = []

    # Target — model as a cube around the origin at its half-extent.
    half = _target_half_extent(state)
    points.append(np.array([+half, +half, +half], dtype=np.float64))
    points.append(np.array([-half, -half, -half], dtype=np.float64))

    # Observer / sun glyphs at display positions.
    points.append(observer_direction_scene(state) * SCENE_OBSERVER_DISTANCE_M)
    points.append(sun_direction_scene(state) * SCENE_SUN_DISTANCE_M)

    # Background only when active — matches the gating in
    # ``scene/glyphs/background.py`` and ``scene/vectors/sun_to_background.py``.
    if state.background_kind != "none":
        points.append(background_direction_scene(state) * SCENE_BACKGROUND_DISTANCE_M)

    stacked = np.stack(points, axis=0)
    return stacked.min(axis=0), stacked.max(axis=0)


def scene_extent_m(state: SceneState) -> float:
    """Half of the largest bounding-box dimension, in scene meters.

    The "scene extent" is what ``set_default_camera`` multiplies by
    ``DISTANCE_EXTENT_MULTIPLIER`` to choose the camera distance.
    Floor at ``_MIN_EXTENT_M`` so a degenerate state still produces
    a usable view.
    """
    bbox_min, bbox_max = scene_bounds(state)
    sizes = bbox_max - bbox_min
    extent = float(np.max(sizes) / 2.0)
    return max(extent, _MIN_EXTENT_M)


def default_camera_distance_m(state: SceneState) -> float:
    """Camera distance the default-camera helper should use for ``state``.

    ``DISTANCE_EXTENT_MULTIPLIER × scene_extent_m(state)``. The
    multiplier is tuned for PyVista's default vertical FOV of 30°; if
    a future change pushes the FOV elsewhere the multiplier needs a
    matching update (callers can override via ``set_default_camera``'s
    ``distance`` argument).
    """
    return DISTANCE_EXTENT_MULTIPLIER * scene_extent_m(state)


def scene_centroid(state: SceneState) -> npt.NDArray[np.float64]:
    """Centroid of the framing bounding box.

    ``set_default_camera`` looks toward the *target centroid* (origin)
    rather than this AABB centroid — the user's mental model is "I am
    looking at the target". But the recenter action and any future
    "fit-to-content" mode will use this centroid to keep the AABB
    centered when off-origin glyphs are far from the target.
    """
    bbox_min, bbox_max = scene_bounds(state)
    return (bbox_min + bbox_max) / 2.0
