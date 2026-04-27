"""Master Cartesian X/Y/Z triad at the scene origin.

Phase 10 (PLAN.md §11). The body-axes module already shows the *target*
body frame at the target's display position. This module is its master-frame
counterpart: three unit-length scatter lines from the scene origin along +X,
+Y, +Z with one text label at each tip. Off by default; togglable from the
controls panel under the `world_axes` group.

Display length is intentionally smaller than the body-axes length so that
when both are on, the master triad doesn't visually compete with the body
frame at the target.

Rule 19: own file.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import plotly.graph_objects as go

WORLD_AXIS_DISPLAY_LENGTH: Final[float] = 1.2

_X_COLOR: Final[str] = "#c03030"
_Y_COLOR: Final[str] = "#30a030"
_Z_COLOR: Final[str] = "#3050c0"


def _axis_traces(
    color: str, axis_name: str, direction: tuple[float, float, float]
) -> list[go.Scatter3d]:
    end = np.array(direction, dtype=np.float64) * WORLD_AXIS_DISPLAY_LENGTH
    return [
        go.Scatter3d(
            x=[0.0, float(end[0])],
            y=[0.0, float(end[1])],
            z=[0.0, float(end[2])],
            mode="lines",
            line={"color": color, "width": 4},
            name=f"world {axis_name}",
            hoverinfo="name",
            showlegend=True,
        ),
        go.Scatter3d(
            x=[float(end[0])],
            y=[float(end[1])],
            z=[float(end[2])],
            mode="text",
            text=[axis_name],
            textposition="top center",
            textfont={"size": 13, "color": color},
            hoverinfo="skip",
            showlegend=False,
        ),
    ]


def world_axes_triad_traces() -> list[go.Scatter3d]:
    """Three orthogonal unit lines from the origin: +X red, +Y green, +Z blue."""
    return [
        *_axis_traces(_X_COLOR, "X", (1.0, 0.0, 0.0)),
        *_axis_traces(_Y_COLOR, "Y", (0.0, 1.0, 0.0)),
        *_axis_traces(_Z_COLOR, "Z", (0.0, 0.0, 1.0)),
    ]
