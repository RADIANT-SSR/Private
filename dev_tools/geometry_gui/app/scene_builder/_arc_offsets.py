"""Per-anchor outward offsets for angle-arc rendering.

Phase 12 (PLAN.md §13). Phase 11 placed each arc at its physical vertex
(target center, B, observer chip, sun chip) with a per-group radius.
For target-anchored arcs (α_t, θ_s, Δφ) the radius is too small to clear
the target mesh, so the arc reads as clipping through the shape. This
module supplies a per-anchor *outward offset* that translates the arc's
center along the bisector of its two direction vectors before the arc
helper draws it. The arc's swept angle and direction-vector geometry are
unchanged — only the anchor moves.

Anchors with offset 0.0 (observer, background, sun) are already in clear
space and do not shift; the table form lets each tune independently if
a future scenario grows them.

This file is internal to the scene-builder package.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt

# Outward-offset distance per anchor, in display units. Target value is
# sized to clear the worst-case mesh half-extent (cone diagonal ≈ 1.12 in
# `target_shape_meshes/`) plus margin. Coupled to `target_shape_meshes/*`
# display geometry — any change there must re-validate this constant.
ARC_OUTWARD_OFFSETS: Final[dict[str, float]] = {
    "observer": 0.0,
    "target": 1.9,
    "background": 0.0,
    "sun": 0.0,
}


def offset_for(anchor_kind: str) -> float:
    """Outward offset for `anchor_kind`. Raises KeyError on unknown keys."""
    return ARC_OUTWARD_OFFSETS[anchor_kind]


def bisector(
    u1: npt.NDArray[np.float64],
    u2: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Unit bisector of two direction vectors. Both inputs normalized internally.

    Falls back to a perpendicular helper for the anti-parallel edge case
    (sum has zero norm). Currently no live arc spans 180°, but the helper
    must remain finite to keep `shifted_anchor` total.
    """
    a = np.asarray(u1, dtype=np.float64)
    b = np.asarray(u2, dtype=np.float64)
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    s = a + b
    n = float(np.linalg.norm(s))
    if n < 1e-12:
        helper = (
            np.array([1.0, 0.0, 0.0], dtype=np.float64)
            if abs(a[0]) < 0.9
            else np.array([0.0, 1.0, 0.0], dtype=np.float64)
        )
        s = helper - a * float(np.dot(helper, a))
        n = float(np.linalg.norm(s))
    return s / n


def shifted_anchor(
    anchor: npt.NDArray[np.float64],
    u1: npt.NDArray[np.float64],
    u2: npt.NDArray[np.float64],
    anchor_kind: str,
) -> npt.NDArray[np.float64]:
    """Translate `anchor` along the (u1, u2) bisector by `offset_for(anchor_kind)`.

    With a zero offset (observer / background / sun today) returns the
    anchor unchanged. The arc helper is unaware of this shift — callers
    pass the shifted anchor directly to `arc_points`.
    """
    a = np.asarray(anchor, dtype=np.float64)
    d = offset_for(anchor_kind)
    if d == 0.0:
        return a.copy()
    return a + d * bisector(u1, u2)
