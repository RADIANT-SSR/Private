"""Outer fade plane — softens the hard edge of the gridded ground cap.

T3 of the visual remediation: a much larger plane in the viewport-bg
color sits a hair below the gridded cap, so when the user pans far from
the target the cap doesn't end in a sharp rectangular edge against the
black void. The fade matches ``style.VIEWPORT_BACKGROUND_COLOR`` so it
disappears against the empty viewport, but the gridded cap reads as
floating on a continuous surface.

Rule 19: own file. The fade is a separate primitive from the gridded
cap (different mesh, different color, different draw order) so it gets
its own module.
"""

from __future__ import annotations

import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene._layout import GROUND_FADE_RADIUS_M


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    del state
    fade = pv.Plane(
        # Sit 0.001 m below the gridded cap so the cap renders on top
        # without z-fighting; the contact shadow at z=+0.001 is on the
        # other side of the cap, so all three primitives have unique z.
        center=(0.0, 0.0, -0.001),
        direction=(0.0, 0.0, 1.0),
        i_size=2.0 * GROUND_FADE_RADIUS_M,
        j_size=2.0 * GROUND_FADE_RADIUS_M,
        i_resolution=1,
        j_resolution=1,
    )
    plotter.add_mesh(
        fade,
        color=style.VIEWPORT_BACKGROUND_COLOR,
        lighting=False,
        opacity=1.0,
        name="ground_fade",
    )
