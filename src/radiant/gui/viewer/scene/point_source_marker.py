"""Point-source target indicator (overlay primitive).

Closes BLOCKER R9-B2: when ``state.regime_override == "point_source"``
the GUI must show a marker that is visually distinct from the regular
sub-pixel target indicator. Pre-this-module the ``point_source_default``
canonical view was geometrically identical to ``sphere_default`` apart
from the regime tag on the target label.

Design: a four-spoke "+" crosshair lying flat on the ground plane,
centered under the target. Each spoke is a thin tube in the
``ACCENT_COLOR`` (orange) so the marker reads as a deliberate annotation
distinct from the teal target body and the cool-gray ground grid. The
marker sits at z = ``MARKER_Z_OFFSET_M`` so it never z-fights with the
ground cap (z = 0), the contact-shadow disc (z = 0.001), or the
extended-pixel-cell footprint (z = 0.003).

The ground-plane placement (rather than at the lifted target centroid)
is intentional: a "point source" means a target whose angular extent
collapses to an ideal point on the focal plane, and the most legible
schematic for that is a survey-style crosshair on the ground beneath
the target. The leader label still names the target body itself.

C7: zero Qt imports. Rule 19: one file, one primitive.
"""

from __future__ import annotations

from typing import Final

import pyvista as pv

from radiant.gui.viewer.scene import style
from radiant.gui.viewer.viewer_state import ViewerState as SceneState

MARKER_SPOKE_LENGTH_M: Final[float] = 1.5
MARKER_TUBE_RADIUS_M: Final[float] = 0.04
MARKER_CENTER_RADIUS_M: Final[float] = 0.10
MARKER_Z_OFFSET_M: Final[float] = 0.005


def _spoke(start: tuple[float, float, float], end: tuple[float, float, float]) -> pv.PolyData:
    line = pv.Line(start, end, resolution=1)
    return line.tube(radius=MARKER_TUBE_RADIUS_M, n_sides=12)


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    if state.regime_override != "point_source":
        return
    z = MARKER_Z_OFFSET_M
    L = MARKER_SPOKE_LENGTH_M
    spokes = [
        _spoke((-L, 0.0, z), (L, 0.0, z)),
        _spoke((0.0, -L, z), (0.0, L, z)),
    ]
    for i, spoke in enumerate(spokes):
        plotter.add_mesh(
            spoke,
            color=style.ACCENT_COLOR,
            lighting=False,
            name=f"point_source_marker_spoke_{i}",
        )
    center = pv.Sphere(
        radius=MARKER_CENTER_RADIUS_M,
        center=(0.0, 0.0, z),
        theta_resolution=24,
        phi_resolution=24,
    )
    plotter.add_mesh(
        center,
        color=style.ACCENT_COLOR,
        lighting=False,
        name="point_source_marker_center",
    )
