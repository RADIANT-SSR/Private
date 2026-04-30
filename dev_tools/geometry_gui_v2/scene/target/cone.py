"""Cone target mesh.

Phase 1: ``pv.Cone`` with apex on body +Z, base at z = 0 (matches
``radiant.source.shapes.cone.Cone``: base radius + height with the axis
of symmetry along the body axis).
"""

from __future__ import annotations

import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene.target._pose import apply_target_pose


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    mesh = pv.Cone(
        center=(0.0, 0.0, state.target_height_m * 0.5),
        direction=(0.0, 0.0, 1.0),
        height=state.target_height_m,
        radius=state.target_base_radius_m,
        resolution=48,
    )
    apply_target_pose(mesh, state)
    # PBR + non-unit opacity wash out shading. See target/sphere.py and CU-034.
    plotter.add_mesh(
        mesh,
        color=style.TARGET_PBR_DIFFUSE_COLOR,
        smooth_shading=style.SMOOTH_SHAPE_SMOOTH_SHADING,
        pbr=True,
        metallic=style.TARGET_PBR_METALLIC,
        roughness=style.TARGET_PBR_ROUGHNESS,
        name="target",
    )
