"""Pin at the target position in display coordinates."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go


def target_marker_traces(
    target_pos_display: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Single small marker at the target position."""
    return [
        go.Scatter3d(
            x=[float(target_pos_display[0])],
            y=[float(target_pos_display[1])],
            z=[float(target_pos_display[2])],
            mode="markers",
            marker={"size": 5, "symbol": "circle", "color": "red"},
            name="Target",
        )
    ]
