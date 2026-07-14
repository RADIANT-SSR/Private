"""Sphere target mesh.

Phase 1: flat-shaded ``pv.Sphere`` at the world origin, sized from
``state.target_radius_m``. PBR shading and light wiring land in Phase 2.

Rule 19: one file, one primitive.
"""

from __future__ import annotations

import pyvista as pv

from radiant.gui.viewer.scene import style
from radiant.gui.viewer.scene.target._pose import apply_target_pose
from radiant.gui.viewer.viewer_state import ViewerState as SceneState


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    mesh = pv.Sphere(radius=state.target_radius_m, theta_resolution=48, phi_resolution=48)
    apply_target_pose(mesh, state)
    # PBR + non-unit opacity wash out the terminator (PyVista PBR composites
    # translucency before lighting). TARGET_OPACITY (0.92, ported from v1
    # Plotly) is kept in style.py for non-PBR overlays (selection highlight)
    # but is intentionally not applied to the PBR body. See CU-034.
    plotter.add_mesh(
        mesh,
        color=style.TARGET_PBR_DIFFUSE_COLOR,
        smooth_shading=style.SMOOTH_SHAPE_SMOOTH_SHADING,
        pbr=True,
        metallic=style.TARGET_PBR_METALLIC,
        roughness=style.TARGET_PBR_ROUGHNESS,
        name="target",
    )
