"""Extended-cell target mesh.

The "extended" regime in RADIANT is not a discrete shape in
``radiant.source.shapes``; it is a *regime* of the scene. Visually the
GUI represents it as a checkerboard ground patch at the target's
location, the size of one detector ground footprint (GSD).

Phase 1 ships a placeholder ``pv.Plane`` at the ground plane. Phase 2
replaces the texture with a procedural checkerboard at
``style.GRID_OPACITY``.

Note: ``state.target_shape`` does not include "extended_cell" today
(``ShapeKind`` is the five concrete shapes). This module exists so the
Phase-2 / Phase-4 work has a single drop-in once the scene supports an
"extended" regime selector visually distinct from the per-shape modes.
The dispatcher in ``target/__init__.py`` does *not* call this module
yet; it is wired in when the regime selector grows that view.
"""

from __future__ import annotations

import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    # GSD (ground sampling distance) drives the cell size. Phase 1 uses a
    # 1 m placeholder until the regime selector wires the view-model GSD
    # through (Phase 4 acceptance for the readout panel).
    cell_size = max(state.target_radius_m, 1.0)
    mesh = pv.Plane(
        center=(0.0, 0.0, 0.0),
        direction=(0.0, 0.0, 1.0),
        i_size=cell_size,
        j_size=cell_size,
        i_resolution=4,
        j_resolution=4,
    )
    plotter.add_mesh(
        mesh,
        color=style.TARGET_COLOR,
        opacity=style.TARGET_OPACITY,
        show_edges=True,
        edge_color=style.TARGET_COLOR,
        name="target",
    )
