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

from typing import TYPE_CHECKING

import pyvista as pv

from radiant.gui.viewer.scene._layout import GROUND_FADE_RADIUS_M
from radiant.gui.viewer.viewer_state import ViewerState as SceneState

if TYPE_CHECKING:
    from radiant.gui.viewer.scene.chrome import SceneChrome


def add_to_plotter(plotter: pv.Plotter, state: SceneState, chrome: SceneChrome) -> None:
    del state
    fade = pv.Plane(
        # Sit 0.5 m below the gridded cap. Round-2 found that the
        # original 0.001 m offset z-fought with the cap at the new
        # camera distance (~30 m) — depth-buffer precision can't
        # distinguish 0.001 m at that range, so the fade ended up
        # randomly winning per-pixel and hiding the cap entirely.
        # 0.5 m is well outside any plausible depth-buffer noise floor
        # but still far enough below the cap that the fade is visually
        # imperceptible (the cap occludes any view down toward it).
        # Contact shadow at z=+0.001 is on the other side of the cap.
        center=(0.0, 0.0, -0.5),
        direction=(0.0, 0.0, 1.0),
        i_size=2.0 * GROUND_FADE_RADIUS_M,
        j_size=2.0 * GROUND_FADE_RADIUS_M,
        i_resolution=1,
        j_resolution=1,
    )
    actor = plotter.add_mesh(
        fade,
        color=chrome.viewport_bg,
        lighting=False,
        opacity=1.0,
        name="ground_fade",
    )
    # Critical: the fade plane spans 500 m to read as an infinite
    # backdrop, but if it contributes to the renderer's bounds then
    # ``reset_camera()`` frames a 1000 m disc and the actual scene
    # (target ~1 m, observer @ 6 m, sun @ 9 m) collapses to a sub-pixel
    # speck. Excluding the fade from bounds keeps the visual but lets
    # the auto-camera frame the meaningful primitives.
    actor.SetUseBounds(False)
