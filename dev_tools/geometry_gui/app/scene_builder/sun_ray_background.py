"""Sun ray at the background point — dashed orange line B → sun, label `s_B`.

Phase 9 (PLAN.md §11). The illumination vector at the background point B is
parallel to `s_t` because the sun is at infinity, but it originates at B
rather than the target. We draw it as a dashed line so it is visually
distinguishable from `s_t`, and label it `s_B`.

Rule 19: own file.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from dev_tools.geometry_gui.app.scene_builder._arc_palette import arc_color_for
from dev_tools.geometry_gui.app.scene_builder.sun_glyph import SUN_DISPLAY_DISTANCE

_SUN_RAY_COLOR: Final[str] = arc_color_for("background")


def sun_ray_background_traces(
    background_pos_display: npt.NDArray[np.float64],
    sun_dir_scene: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Dashed orange line from B along the sun direction + `s_B` label.

    Endpoint distance matches `SUN_DISPLAY_DISTANCE` so the rays at the
    target and at B feel parallel and identical in length under the
    sun-at-infinity convention.
    """
    b = np.asarray(background_pos_display, dtype=np.float64)
    n = np.asarray(sun_dir_scene, dtype=np.float64)
    n = n / np.linalg.norm(n)
    end = b + SUN_DISPLAY_DISTANCE * n
    midpoint = 0.5 * (b + end)
    return [
        go.Scatter3d(
            x=[float(b[0]), float(end[0])],
            y=[float(b[1]), float(end[1])],
            z=[float(b[2]), float(end[2])],
            mode="lines",
            line={"color": _SUN_RAY_COLOR, "width": 3, "dash": "dot"},
            name="s_B (B → sun)",
            hoverinfo="name",
            showlegend=True,
        ),
        go.Scatter3d(
            x=[float(midpoint[0])],
            y=[float(midpoint[1])],
            z=[float(midpoint[2])],
            mode="text",
            text=["s_B"],
            textposition="bottom right",
            textfont={"size": 13, "color": _SUN_RAY_COLOR},
            hoverinfo="skip",
            showlegend=False,
        ),
    ]
