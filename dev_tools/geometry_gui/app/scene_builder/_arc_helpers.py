"""Shared helpers for arc-rendering modules.

Phase 9 (PLAN.md §11). Off-nadir, phase-angle, and solar-zenith arcs each
need the same primitive: a circular arc from one unit vector to another,
swept in the plane spanned by them, anchored at a 3D point. This helper
centralizes that math.

This file is *internal* to the scene-builder package and is not exported.
The four arc modules each own their own visible behavior (color, label,
position) per Rule 19; they share only the geometric primitive defined here.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
import numpy.typing as npt

# Single arc display radius for the whole figure (PLAN.md §11 frozen constants).
ARC_DISPLAY_RADIUS: Final[float] = 0.4

_N_SEGMENTS: Final[int] = 48


def arc_points(
    anchor: npt.NDArray[np.float64],
    u_start: npt.NDArray[np.float64],
    u_end: npt.NDArray[np.float64],
    radius: float = ARC_DISPLAY_RADIUS,
    n_segments: int = _N_SEGMENTS,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64], float]:
    """Sample an arc from `u_start` to `u_end` around `anchor`.

    Both inputs are direction vectors from the anchor; only their direction
    matters (they are normalized internally). The arc lies in the plane
    spanned by them, sweeping the smaller of the two possible angles.

    Returns (xs, ys, zs, swept_angle_rad). The arc starts on the ray along
    `u_start` at distance `radius` from `anchor` and ends on the ray along
    `u_end` at the same distance.

    Degenerate cases:
      * if either input has zero norm → returns empty arrays + 0.0
      * if the two directions are parallel (angle == 0) → returns empty
      * if the two directions are anti-parallel (angle == π) → arc is
        rendered through whichever perpendicular minimizes numerical error.
    """
    a = np.asarray(anchor, dtype=np.float64)
    u1 = np.asarray(u_start, dtype=np.float64)
    u2 = np.asarray(u_end, dtype=np.float64)

    n1 = float(np.linalg.norm(u1))
    n2 = float(np.linalg.norm(u2))
    if n1 == 0.0 or n2 == 0.0:
        empty = np.array([], dtype=np.float64)
        return empty, empty, empty, 0.0

    e1 = u1 / n1
    e2 = u2 / n2
    cos_theta = float(np.clip(np.dot(e1, e2), -1.0, 1.0))
    angle = math.acos(cos_theta)

    if angle == 0.0:
        empty = np.array([], dtype=np.float64)
        return empty, empty, empty, 0.0

    if abs(math.pi - angle) < 1e-12:
        helper = np.array([1.0, 0.0, 0.0]) if abs(e1[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        e_perp = helper - e1 * float(np.dot(helper, e1))
        e_perp /= np.linalg.norm(e_perp)
    else:
        e_perp = e2 - cos_theta * e1
        e_perp /= np.linalg.norm(e_perp)

    ts = np.linspace(0.0, angle, n_segments)
    samples = (
        np.cos(ts)[:, None] * e1[None, :] + np.sin(ts)[:, None] * e_perp[None, :]
    ) * radius + a[None, :]
    return samples[:, 0], samples[:, 1], samples[:, 2], angle
