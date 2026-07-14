"""Contact-shadow disc under the target.

Phase 1: a flat dark disc at z = +0.001 (above the ground cap to avoid
z-fighting), radius = ``CONTACT_SHADOW_RADIUS_FACTOR × target characteristic
extent``. Phase 2 keeps the same disc but enables soft-edge alpha.
"""

from __future__ import annotations

import pyvista as pv

from radiant.gui.viewer.scene import style
from radiant.gui.viewer.viewer_state import ViewerState as SceneState


def _half_extent(state: SceneState) -> float:
    return max(
        state.target_radius_m,
        state.target_length_m * 0.5,
        state.target_width_m * 0.5,
        state.target_base_radius_m,
        0.5,
    )


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    # Phase-7 diet: widen and stretch the shadow into a soft horizontal
    # ellipse (3× wider than tall in scene-X) so it reads as the only
    # ground reference now that the grid is gone. Disc is at z = +0.001
    # to sit just above the conceptual ground plane.
    base_radius = style.CONTACT_SHADOW_RADIUS_FACTOR * _half_extent(state)
    radius = base_radius * 1.6
    disc = pv.Disc(center=(0.0, 0.0, 0.001), inner=0.0, outer=radius, c_res=96)
    disc.scale([1.0, 0.55, 1.0], inplace=True)
    plotter.add_mesh(
        disc,
        color=style.CONTACT_SHADOW_COLOR,
        opacity=style.CONTACT_SHADOW_OPACITY,
        lighting=False,
        name="contact_shadow",
    )
