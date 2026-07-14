"""Geometric vector primitives.

Per Rule 19 / C5: one file per vector. The package ``__init__`` calls
each module's ``add_to_plotter`` in a fixed order so the builder remains
declarative.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from radiant.gui.viewer.viewer_state import ViewerState as SceneState

if TYPE_CHECKING:
    import pyvista as pv


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    from radiant.gui.viewer.scene.vectors import (
        boresight,
        sun_ray,
        sun_to_background,
        surface_normal,
    )

    boresight.add_to_plotter(plotter, state)
    surface_normal.add_to_plotter(plotter, state)
    sun_ray.add_to_plotter(plotter, state)
    sun_to_background.add_to_plotter(plotter, state)
