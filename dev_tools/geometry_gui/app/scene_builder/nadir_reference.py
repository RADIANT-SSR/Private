"""Nadir reference — faint dashed vertical line from the observer downward.

Phase 9 (PLAN.md §11). At the observer's position the local-vertical (nadir)
direction is straight down toward the ground. The off-nadir arc (next module)
needs both the boresight and the nadir direction at the observer to anchor
its endpoints; this module supplies the visible nadir reference line.

In the Phase 8 display frame (+Z = local zenith at the target), nadir from
the observer means a line in the −Z direction starting at observer_pos and
extending until it reaches the same z as the target.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from dev_tools.geometry_gui.app.scene_builder._arc_palette import arc_color_for

_NADIR_COLOR: str = arc_color_for("observer")


def nadir_reference_traces(
    observer_pos_display: npt.NDArray[np.float64],
    target_pos_display: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Dashed grey line straight down from observer to target's altitude.

    The line drops vertically (−Z) until it reaches `target_pos_display.z`,
    so the off-nadir arc can be drawn between this line and the boresight at
    the observer. The label `nadir` floats next to the line's midpoint.
    """
    o = np.asarray(observer_pos_display, dtype=np.float64)
    t = np.asarray(target_pos_display, dtype=np.float64)
    end = np.array([o[0], o[1], t[2]], dtype=np.float64)
    midpoint = 0.5 * (o + end)
    return [
        go.Scatter3d(
            x=[float(o[0]), float(end[0])],
            y=[float(o[1]), float(end[1])],
            z=[float(o[2]), float(end[2])],
            mode="lines",
            line={"color": _NADIR_COLOR, "width": 2, "dash": "dash"},
            name="nadir reference",
            hoverinfo="name",
            showlegend=True,
        ),
        go.Scatter3d(
            x=[float(midpoint[0])],
            y=[float(midpoint[1])],
            z=[float(midpoint[2])],
            mode="text",
            text=["nadir"],
            textposition="middle left",
            textfont={"size": 11, "color": _NADIR_COLOR},
            hoverinfo="skip",
            showlegend=False,
        ),
    ]
