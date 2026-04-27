"""Shared helper for angle-projection arc rendering.

Phase 10 (PLAN.md §11). Each parent arc has a "shadow" companion arc
projected onto a reference plane. The plane is specified by an anchor
point and a unit normal. Projecting an arc point P amounts to:

    P' = P − (n · (P − anchor)) * n

This file is *internal* to the scene-builder package. The three projection
modules each own their visible behavior (color, plane, label) per Rule 19;
they share only the projection primitive defined here.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def project_points_onto_plane(
    xs: npt.NDArray[np.float64],
    ys: npt.NDArray[np.float64],
    zs: npt.NDArray[np.float64],
    plane_anchor: npt.NDArray[np.float64],
    plane_normal: npt.NDArray[np.float64],
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Drop each (x, y, z) sample onto the plane (anchor, normal)."""
    n = np.asarray(plane_normal, dtype=np.float64)
    n = n / np.linalg.norm(n)
    a = np.asarray(plane_anchor, dtype=np.float64)
    pts = np.stack([xs, ys, zs], axis=1)
    delta = pts - a[None, :]
    along = delta @ n
    projected = pts - along[:, None] * n[None, :]
    return projected[:, 0], projected[:, 1], projected[:, 2]
