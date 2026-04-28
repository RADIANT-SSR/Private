"""Contact-shadow disc under the target.

Phase 1: a flat dark disc at z = +0.001 (above the ground cap to avoid
z-fighting), radius = ``CONTACT_SHADOW_RADIUS_FACTOR × target characteristic
extent``. Phase 2 keeps the same disc but enables soft-edge alpha.
"""

from __future__ import annotations

import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style


def _half_extent(state: SceneState) -> float:
    return max(
        state.target_radius_m,
        state.target_length_m * 0.5,
        state.target_width_m * 0.5,
        state.target_base_radius_m,
        0.5,
    )


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    radius = style.CONTACT_SHADOW_RADIUS_FACTOR * _half_extent(state)
    disc = pv.Disc(center=(0.0, 0.0, 0.001), inner=0.0, outer=radius, c_res=64)
    plotter.add_mesh(
        disc,
        color=style.CONTACT_SHADOW_COLOR,
        opacity=style.CONTACT_SHADOW_OPACITY,
        lighting=False,
        name="contact_shadow",
    )
