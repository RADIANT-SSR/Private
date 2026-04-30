"""Cylinder target mesh.

Phase 1: ``pv.Cylinder`` along the body +Z axis (matches the convention in
``radiant.source.shapes.cylinder.Cylinder``: length runs along the body
axis with the radius in the perpendicular plane). Body-frame rotation
into the scene frame ships in Phase 2 with the body-axes triad; Phase 1
draws the cylinder in its body frame for shape-identification purposes.
"""

from __future__ import annotations

import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene.target._pose import apply_target_pose


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    mesh = pv.Cylinder(
        center=(0.0, 0.0, 0.0),
        direction=(0.0, 0.0, 1.0),
        radius=state.target_radius_m,
        height=state.target_length_m,
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
