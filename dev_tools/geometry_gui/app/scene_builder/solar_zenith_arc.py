"""Solar zenith arc θ_sun,B — drawn at B between n_B and s_B.

Phase 9 (PLAN.md §11). At the background point B, the solar-zenith angle is
the angle between the local surface normal `n_B` (pointing up from the
ground) and the sun direction `s_B`. It governs the cosine factor in the
ground irradiance computation.

We draw the arc anchored at B, swept in the plane spanned by n_B and s_B,
labeled with θ_sun,B in degrees.

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


def solar_zenith_at_b_rad(
    n_b: npt.NDArray[np.float64],
    s_b: npt.NDArray[np.float64],
) -> float:
    """θ_sun,B = arccos(n_B · s_B), inputs normalized internally."""
    a = np.asarray(n_b, dtype=np.float64)
    b = np.asarray(s_b, dtype=np.float64)
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    return math.acos(float(np.clip(np.dot(a, b), -1.0, 1.0)))


def solar_zenith_arc_traces(
    background_pos_display: npt.NDArray[np.float64],
    surface_normal_b: npt.NDArray[np.float64],
    sun_dir_scene: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Arc + θ_sun,B label at the background point."""
    p = np.asarray(background_pos_display, dtype=np.float64)
    radius = arc_radius_for("solar_zenith_b")
    color = arc_color_for("background")
    xs, ys, zs, swept = arc_points(p, surface_normal_b, sun_dir_scene, radius=radius)
    if xs.size == 0:
        return []

    expected = solar_zenith_at_b_rad(surface_normal_b, sun_dir_scene)
    assert math.isclose(swept, expected, abs_tol=1e-9), (
        f"solar_zenith_arc: swept {swept} rad != θ_sun,B {expected} rad"
    )

    theta_deg = math.degrees(swept)
    label_x = float(xs[len(xs) // 2])
    label_y = float(ys[len(ys) // 2])
    label_z = float(zs[len(zs) // 2])

    arc_name = f"theta_sun_B = {theta_deg:.1f} deg"
    label_name = f"theta_sun_B label ({theta_deg:.1f} deg)"
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
        text=[label_for("solar_zenith_b")],
        textposition="middle right",
        textfont={"size": 12, "color": color},
        name=label_name,
        hoverinfo="skip",
        showlegend=False,
    )
    return [arc, text]
