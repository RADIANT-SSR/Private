"""Phase angle arc α_t — drawn at the target between (−o) and s_t.

Phase 9 (PLAN.md §11). The phase angle is the angle at the target between
the incoming illumination direction (from sun, i.e. opposite of `s_t` at
target) and the outgoing observation direction (target → observer, i.e.
−boresight). It is fundamental to BRDF / phase-function calculations.

We draw a small arc at the target spanning the angle between the unit
vector `target → observer` and the unit vector `target → sun`. The label
reports α_t in degrees.

Rule 19: own file.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from dev_tools.geometry_gui.app.scene_builder._arc_helpers import arc_points
from dev_tools.geometry_gui.app.scene_builder._arc_labels import label_for
from dev_tools.geometry_gui.app.scene_builder._arc_palette import arc_color_for
from dev_tools.geometry_gui.app.scene_builder._arc_radii import arc_radius_for


def phase_angle_rad(
    view_dir_target_to_observer: npt.NDArray[np.float64],
    sun_dir_target_to_sun: npt.NDArray[np.float64],
) -> float:
    """Phase angle α_t in radians from the two unit-or-arbitrary vectors.

    α_t = arccos(o · s_t), where o and s_t are normalized internally.
    """
    o = np.asarray(view_dir_target_to_observer, dtype=np.float64)
    s = np.asarray(sun_dir_target_to_sun, dtype=np.float64)
    o = o / np.linalg.norm(o)
    s = s / np.linalg.norm(s)
    return math.acos(float(np.clip(np.dot(o, s), -1.0, 1.0)))


def phase_angle_arc_traces(
    target_pos_display: npt.NDArray[np.float64],
    view_dir_target_to_observer: npt.NDArray[np.float64],
    sun_dir_target_to_sun: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Arc + α_t label at the target."""
    t = np.asarray(target_pos_display, dtype=np.float64)
    radius = arc_radius_for("phase_angle")
    color = arc_color_for("target")
    xs, ys, zs, swept = arc_points(
        t, view_dir_target_to_observer, sun_dir_target_to_sun, radius=radius
    )
    if xs.size == 0:
        return []

    expected = phase_angle_rad(view_dir_target_to_observer, sun_dir_target_to_sun)
    assert math.isclose(swept, expected, abs_tol=1e-9), (
        f"phase_angle_arc: swept {swept} rad != α_t {expected} rad"
    )

    alpha_deg = math.degrees(swept)
    label_x = float(xs[len(xs) // 2])
    label_y = float(ys[len(ys) // 2])
    label_z = float(zs[len(zs) // 2])

    arc_name = f"alpha_t = {alpha_deg:.1f} deg"
    label_name = f"alpha_t label ({alpha_deg:.1f} deg)"
    arc = go.Scatter3d(
        x=xs,
        y=ys,
        z=zs,
        mode="lines",
        line={"color": color, "width": 3},
        name=arc_name,
        hoverinfo="name",
        showlegend=True,
    )
    text = go.Scatter3d(
        x=[label_x],
        y=[label_y],
        z=[label_z],
        mode="text",
        text=[label_for("phase_angle")],
        textposition="middle right",
        textfont={"size": 12, "color": color},
        name=label_name,
        hoverinfo="skip",
        showlegend=False,
    )
    return [arc, text]
