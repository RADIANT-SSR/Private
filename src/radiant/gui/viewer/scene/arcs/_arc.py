"""Shared great-arc tube helper — curved tube + cone arrowhead at the v2 end.

Lifted verbatim (path-rewritten) from the prototype ``scene/arcs/_arc.py`` (ADR-0007
Phase 7 Part B): every angle arc renders as a curved tube along the great circle from
``v1`` to ``v2`` with a small cone arrowhead at the ``v2`` end indicating the angular
direction.

Rule 19 carve-out: shared helper for the ``arcs/`` family per CLAUDE.md Rule 19's
"tightly coupled computations that share internal state or helper functions" exception.
Each named arc keeps its own file. This module imports no Qt and no physics stage.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
import pyvista as pv

from radiant.gui.viewer.scene import style

# Slerp sample count is geometric, not stylistic, so it stays local (the tube + tip
# dimensions live in ``scene/style.py`` alongside the other visual constants).
_NUM_SAMPLES = 32


def add_great_arc(
    plotter: pv.Plotter,
    v1: npt.NDArray[np.float64],
    v2: npt.NDArray[np.float64],
    radius: float,
    color: str,
    name: str,
    with_arrowhead: bool = True,
) -> None:
    """Curved tube along the shorter great arc from ``v1`` to ``v2``.

    Both inputs must be (or close to) unit vectors. If they are nearly colinear or
    antipodal the function returns silently — there is no visible arc to draw. With
    ``with_arrowhead`` (default True), a small cone is added at the ``v2`` end pointing
    along the arc's tangent.
    """
    a = v1 / max(np.linalg.norm(v1), 1e-12)
    b = v2 / max(np.linalg.norm(v2), 1e-12)
    cos_theta = float(np.clip(np.dot(a, b), -1.0, 1.0))
    theta = math.acos(cos_theta)
    if theta < 1e-3 or theta > math.pi - 1e-3:
        return
    sin_theta = math.sin(theta)
    ts = np.linspace(0.0, 1.0, _NUM_SAMPLES)
    points = np.empty((_NUM_SAMPLES, 3), dtype=np.float64)
    for i, t in enumerate(ts):
        s1 = math.sin((1.0 - t) * theta) / sin_theta
        s2 = math.sin(t * theta) / sin_theta
        points[i] = (s1 * a + s2 * b) * radius
    spline = pv.Spline(points, n_points=_NUM_SAMPLES)
    tube = spline.tube(radius=style.ARC_TUBE_RADIUS_M)
    plotter.add_mesh(tube, color=color, name=name)

    if with_arrowhead:
        # Arc tangent at v2: derivative of slerp at t=1 → (b cos θ - a) / sin θ, then
        # scaled by radius. Direction-only is what we need for the cone.
        tangent = (b * math.cos(theta) - a) / sin_theta
        tangent /= max(np.linalg.norm(tangent), 1e-12)
        tip_center = points[-1] + tangent * (style.ARC_TIP_HEIGHT_M * 0.5)
        cone = pv.Cone(
            center=tuple(tip_center),
            direction=tuple(tangent),
            height=style.ARC_TIP_HEIGHT_M,
            radius=style.ARC_TIP_RADIUS_M,
            resolution=24,
        )
        plotter.add_mesh(cone, color=color, name=f"{name}_tip")
