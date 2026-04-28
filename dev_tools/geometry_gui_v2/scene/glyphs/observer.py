"""Observer (satellite) glyph — diamond facing the boresight.

Phase 3 (PLAN_v2.md §11 step 6): a 4-sided ``vtk.vtkRegularPolygonSource``
diamond with white fill and ``SATELLITE_FAMILY`` outline. The diamond is
oriented so its normal points along the boresight (target → observer)
unit vector, which matches the user expectation that the satellite icon
"faces the camera looking toward the target".

Screen-space sizing (PLAN_v2.md §11 step 3) is a Phase 5 interactive
concern; for now the glyph has a fixed world-space radius so the static
goldens are deterministic.
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene._directions import observer_direction_scene
from dev_tools.geometry_gui_v2.scene._layout import SCENE_OBSERVER_DISTANCE_M

_DIAMOND_RADIUS_M = 0.30


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    direction = observer_direction_scene(state)
    pos = direction * SCENE_OBSERVER_DISTANCE_M
    diamond = pv.Polygon(
        center=tuple(pos),
        radius=_DIAMOND_RADIUS_M,
        normal=tuple(direction),
        n_sides=4,
    )
    plotter.add_mesh(
        diamond,
        color="#FFFFFF",
        show_edges=True,
        edge_color=style.SATELLITE_FAMILY,
        line_width=2.0,
        name="glyph_observer",
    )
