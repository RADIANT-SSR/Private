"""Flat-plate target mesh.

Phase 1: ``pv.Plane`` of ``length × width`` lying in the body XY plane
with normal along +Z, matching ``radiant.source.shapes.flat_plate.FlatPlate``
(single-facet shape; projected_area = L·W·|cos θ|).

Faceted shading: a flat plate has one normal, so smooth shading is
meaningless here. Use the ``FACETED_SMOOTH_SHADING`` constant for
intent parity with the box.
"""

from __future__ import annotations

import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    mesh = pv.Plane(
        center=(0.0, 0.0, 0.0),
        direction=(0.0, 0.0, 1.0),
        i_size=state.target_length_m,
        j_size=state.target_width_m,
        i_resolution=1,
        j_resolution=1,
    )
    # PBR + non-unit opacity wash out shading. See target/sphere.py and CU-034.
    plotter.add_mesh(
        mesh,
        color=style.TARGET_PBR_DIFFUSE_COLOR,
        smooth_shading=style.FACETED_SMOOTH_SHADING,
        show_edges=True,
        edge_color=style.TARGET_COLOR,
        pbr=True,
        metallic=style.TARGET_PBR_METALLIC,
        roughness=style.TARGET_PBR_ROUGHNESS,
        name="target",
    )
