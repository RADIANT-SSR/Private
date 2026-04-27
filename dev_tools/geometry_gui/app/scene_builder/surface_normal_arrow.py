"""Surface normal arrow n_B at the background point.

Phase 9 (PLAN.md §11). The local surface normal at B points straight up
along +Z in our flat-ground display convention. We draw it as a short
arrow with shaft + cone tip (matching the legacy sun_arrow construction)
and label it `n_B`.

Rule 19: own file.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from dev_tools.geometry_gui.app.scene_builder._arc_palette import arc_color_for

_ARROW_LENGTH: Final[float] = 0.6
_TIP_LENGTH: Final[float] = _ARROW_LENGTH * 0.18
_TIP_RADIUS: Final[float] = _TIP_LENGTH * 0.4
_NORMAL_COLOR: Final[str] = arc_color_for("background")

# Surface normal in display coordinates: +Z (zenith) for flat ground.
SURFACE_NORMAL_AT_B: Final[npt.NDArray[np.float64]] = np.array(
    [0.0, 0.0, 1.0], dtype=np.float64
)


def surface_normal_arrow_traces(
    background_pos_display: npt.NDArray[np.float64],
) -> list[go.Scatter3d | go.Cone]:
    """Short up-arrow anchored at B + `n_B` label."""
    base = np.asarray(background_pos_display, dtype=np.float64)
    n = SURFACE_NORMAL_AT_B
    tip_base = base + n * _ARROW_LENGTH
    tip_apex = base + n * (_ARROW_LENGTH + _TIP_LENGTH)

    shaft = go.Scatter3d(
        x=[float(base[0]), float(tip_base[0])],
        y=[float(base[1]), float(tip_base[1])],
        z=[float(base[2]), float(tip_base[2])],
        mode="lines",
        line={"color": _NORMAL_COLOR, "width": 4},
        name="n_B (surface normal)",
        hoverinfo="name",
        showlegend=True,
    )
    tip = go.Cone(
        x=[float(tip_base[0])],
        y=[float(tip_base[1])],
        z=[float(tip_base[2])],
        u=[float(tip_apex[0] - tip_base[0])],
        v=[float(tip_apex[1] - tip_base[1])],
        w=[float(tip_apex[2] - tip_base[2])],
        sizemode="absolute",
        sizeref=_TIP_RADIUS * 2.0,
        anchor="tail",
        colorscale=[[0.0, _NORMAL_COLOR], [1.0, _NORMAL_COLOR]],
        showscale=False,
        name="n_B (tip)",
        hoverinfo="name",
        showlegend=False,
    )
    label = go.Scatter3d(
        x=[float(tip_apex[0])],
        y=[float(tip_apex[1])],
        z=[float(tip_apex[2])],
        mode="text",
        text=["n_B"],
        textposition="top center",
        textfont={"size": 12, "color": _NORMAL_COLOR},
        hoverinfo="skip",
        showlegend=False,
    )
    return [shaft, tip, label]
