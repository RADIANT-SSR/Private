"""Leader line from an arc's physical vertex to its offset center.

Phase 12 (PLAN.md §13). When a target-anchored arc is shifted outward
along its bisector by `_arc_offsets.shifted_anchor`, the visual link
between "this arc" and "the vertex it measures" is lost. A thin dashed
leader line restores the link: it runs from the physical vertex to the
arc's geometric center, drawn in the parent's palette color at the same
alpha used by Phase-11 projections so the eye treats it as a guide
rather than a measurement.

Skip the leader entirely when the offset is zero — the arc already sits
at the vertex.

Rule 19: own file.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from dev_tools.geometry_gui.app.scene_builder._arc_palette import PROJECTION_ALPHA


def arc_leader_line_traces(
    physical_vertex: npt.NDArray[np.float64],
    arc_center: npt.NDArray[np.float64],
    color: str,
    *,
    leader_name: str,
) -> list[go.Scatter3d]:
    """One thin dashed Scatter3d from `physical_vertex` to `arc_center`.

    Returns an empty list when the two points coincide (offset = 0), so
    callers can unconditionally extend their trace list.
    """
    v = np.asarray(physical_vertex, dtype=np.float64)
    c = np.asarray(arc_center, dtype=np.float64)
    if float(np.linalg.norm(c - v)) < 1e-12:
        return []
    return [
        go.Scatter3d(
            x=[float(v[0]), float(c[0])],
            y=[float(v[1]), float(c[1])],
            z=[float(v[2]), float(c[2])],
            mode="lines",
            line={"color": color, "width": 1, "dash": "dot"},
            opacity=PROJECTION_ALPHA,
            name=leader_name,
            hoverinfo="skip",
            showlegend=False,
        )
    ]
