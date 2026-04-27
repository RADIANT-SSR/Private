"""Sun ray at the target — solid orange line target → sun glyph, label `s_t`.

Phase 9 (PLAN.md §11). The vector from the target to the sun is the
illumination geometry the radiometric chain consumes for the target term.
We draw it as a solid orange line and label it `s_t` near its midpoint.

The sun glyph itself sits at `SUN_DISPLAY_DISTANCE` along this vector
(see `sun_glyph.py`); this module's line endpoint is the same position.

Rule 19: own file. The deprecated cone-tipped sun arrow in `sun_arrow.py`
predates this redesign; it is no longer composed in `build_scene` (Phase 8
already removed the call). Its `sun_unit_vector_*` helpers are still used.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

_SUN_RAY_COLOR: Final[str] = "#d18a00"


def sun_ray_target_traces(
    target_pos_display: npt.NDArray[np.float64],
    sun_pos_display: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Solid orange line from target to sun glyph + `s_t` text label."""
    t = np.asarray(target_pos_display, dtype=np.float64)
    s = np.asarray(sun_pos_display, dtype=np.float64)
    midpoint = 0.5 * (t + s)
    return [
        go.Scatter3d(
            x=[float(t[0]), float(s[0])],
            y=[float(t[1]), float(s[1])],
            z=[float(t[2]), float(s[2])],
            mode="lines",
            line={"color": _SUN_RAY_COLOR, "width": 4},
            name="s_t (target → sun)",
            hoverinfo="name",
            showlegend=True,
        ),
        go.Scatter3d(
            x=[float(midpoint[0])],
            y=[float(midpoint[1])],
            z=[float(midpoint[2])],
            mode="text",
            text=["s_t"],
            textposition="top right",
            textfont={"size": 13, "color": _SUN_RAY_COLOR},
            hoverinfo="skip",
            showlegend=False,
        ),
    ]
