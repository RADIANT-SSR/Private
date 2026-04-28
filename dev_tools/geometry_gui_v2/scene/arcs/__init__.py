"""Angle-arc primitives — off-nadir, phase-angle (alpha_t), sun-zenith.

Per Rule 19 / C5: one file per arc. Each arc is the curved tube along
the great circle on a unit sphere centered on the target, between the
two relevant unit vectors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dev_tools.geometry_gui_v2.app.state import SceneState

if TYPE_CHECKING:
    import pyvista as pv


def add_to_plotter(plotter: "pv.Plotter", state: SceneState) -> None:
    from dev_tools.geometry_gui_v2.scene.arcs import off_nadir, phase_angle, sun_zenith

    off_nadir.add_to_plotter(plotter, state)
    phase_angle.add_to_plotter(plotter, state)
    sun_zenith.add_to_plotter(plotter, state)
