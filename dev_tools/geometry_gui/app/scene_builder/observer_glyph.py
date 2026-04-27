"""Observer glyph — labeled satellite marker at the head of the boresight.

Phase 8 redesign (PLAN.md §11): the observer is no longer placed at its true
display radius (which scales with altitude / Earth radius). Instead it sits at
a fixed `OBSERVER_DISPLAY_DISTANCE` from the target along the *true* boresight
direction so the geometry is readable. The real altitude is shown verbatim in
the glyph's label per PLAN.md C7 (distances illustrative; angles physical).
"""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

# Display-unit distance from the target to the observer glyph.
OBSERVER_DISPLAY_DISTANCE: Final[float] = 4.0


def observer_position_illustrative(
    target_pos_display: npt.NDArray[np.float64],
    boresight_unit_scene: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Place the observer at `OBSERVER_DISPLAY_DISTANCE` along `−boresight`.

    `boresight_unit_scene` points *from observer toward target* (the standard
    observer-direction convention). The glyph therefore sits at
    `target_pos − OBSERVER_DISPLAY_DISTANCE × boresight_unit`.
    """
    n = np.asarray(boresight_unit_scene, dtype=np.float64)
    n = n / np.linalg.norm(n)
    return np.asarray(target_pos_display, dtype=np.float64) - OBSERVER_DISPLAY_DISTANCE * n


def observer_glyph_traces(
    observer_pos_display: npt.NDArray[np.float64],
    altitude_m: float,
) -> list[go.Scatter3d]:
    """Diamond marker plus a `Satellite, X km alt` text label."""
    altitude_km = altitude_m / 1_000.0
    label = f"Satellite ({altitude_km:.0f} km alt)"
    pos = np.asarray(observer_pos_display, dtype=np.float64)
    return [
        go.Scatter3d(
            x=[float(pos[0])],
            y=[float(pos[1])],
            z=[float(pos[2])],
            mode="markers+text",
            marker={"size": 9, "symbol": "diamond", "color": "#1f3b8b"},
            text=[label],
            textposition="top center",
            textfont={"size": 12, "color": "#1f3b8b"},
            name=label,
            hoverinfo="name",
            showlegend=True,
        )
    ]
