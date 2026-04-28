"""Box target mesh.

Phase 1: axis-aligned ``pv.Box`` sized by ``length × width × height``
along body X/Y/Z, matching ``radiant.source.shapes.box.Box``. Faceted
shading (``smooth_shading=False``) so the six facets read as separate
faces — this is intentional and matches v1's flat-shading choice.
"""

from __future__ import annotations

import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    half_l = state.target_length_m * 0.5
    half_w = state.target_width_m * 0.5
    half_h = state.target_height_m * 0.5
    mesh = pv.Box(bounds=(-half_l, half_l, -half_w, half_w, -half_h, half_h))
    # PBR + non-unit opacity wash out shading. See target/sphere.py and CU-034.
    plotter.add_mesh(
        mesh,
        color=style.TARGET_PBR_DIFFUSE_COLOR,
        smooth_shading=style.FACETED_SMOOTH_SHADING,
        pbr=True,
        metallic=style.TARGET_PBR_METALLIC,
        roughness=style.TARGET_PBR_ROUGHNESS,
        name="target",
    )
