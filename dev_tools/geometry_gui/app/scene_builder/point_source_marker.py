"""Point-source marker — used in the POINT_SOURCE regime in place of a target mesh.

Per the Phase-4 spec: "render target as a single emissive dot ... no projected
area is meaningful here." The radiometry path uses
`T7IntensityAtSource.REFERENCE_AREA_M2` (a fixed fictional reference area —
currently 1e-12 m² in `radiant.core.descriptors`) and treats the source as
unresolved. The dot makes the visual contract clear: there is nothing to
shade or rotate.

The trace name carries the reference area so the developer sees what the
radiometry will use on hover.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from radiant.core.descriptors import T7IntensityAtSource


def point_source_traces(
    target_pos_display: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """A single bright marker at the target position."""
    ref_area_m2 = T7IntensityAtSource.REFERENCE_AREA_M2
    return [
        go.Scatter3d(
            x=[float(target_pos_display[0])],
            y=[float(target_pos_display[1])],
            z=[float(target_pos_display[2])],
            mode="markers",
            marker={
                "size": 12,
                "symbol": "circle",
                "color": "yellow",
                "line": {"color": "black", "width": 1},
            },
            name=f"Point source (ref. area = {ref_area_m2:.2e} m^2)",
            showlegend=True,
        )
    ]
