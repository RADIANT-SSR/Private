"""Canonical-view camera poses — front / back / left / right / top / bottom / iso.

Phase 5 (PLAN_v2.md §13 step 1): the view-cube widget animates the
camera to one of seven canonical poses on click. ``camera_pose_for``
returns the ``(position, focal_point, view_up)`` triple PyVista's
``Plotter.camera_position`` accepts.

All poses look at the target centroid (origin) at a fixed schematic
distance. The distance is large enough that all Phase 4 anchors
(observer at z=6 m, sun at z=9 m, background at z=12 m) fit in frame
without zoom adjustment.

Pure function. No PyVista dependency on the inputs; the *output*
shape matches PyVista's expected ``camera_position`` tuple but is
just a list of three 3-tuples — testable without a renderer.
"""

from __future__ import annotations

import math
from typing import Final

CANONICAL_DISTANCE_M: Final[float] = 14.0


def camera_pose_for(
    view: str,
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    """Return ``(position, focal_point, view_up)`` for the named view.

    ``view`` must be one of: front, back, left, right, top, bottom, iso.
    Raises ValueError for any other string — callers should pass an
    enum value (``CanonicalView.value``) so this is unreachable in the
    UI; the explicit raise is for unit-test clarity.
    """
    d = CANONICAL_DISTANCE_M
    focal = (0.0, 0.0, 0.0)

    if view == "front":
        return (d, 0.0, 0.0), focal, (0.0, 0.0, 1.0)
    if view == "back":
        return (-d, 0.0, 0.0), focal, (0.0, 0.0, 1.0)
    if view == "left":
        return (0.0, d, 0.0), focal, (0.0, 0.0, 1.0)
    if view == "right":
        return (0.0, -d, 0.0), focal, (0.0, 0.0, 1.0)
    if view == "top":
        return (0.0, 0.0, d), focal, (0.0, 1.0, 0.0)
    if view == "bottom":
        return (0.0, 0.0, -d), focal, (0.0, 1.0, 0.0)
    if view == "iso":
        # Phase 1 / 2 / 3 / 4 goldens are framed at this iso pose; matches
        # tests/test_scene_goldens_phase1.py exactly.
        return (
            (d * math.cos(math.radians(35.0)), d * math.sin(math.radians(35.0)), 0.5 * d),
            focal,
            (0.0, 0.0, 1.0),
        )
    raise ValueError(
        f"camera_pose_for: unknown view {view!r}. "
        f"Expected one of: front, back, left, right, top, bottom, iso."
    )
