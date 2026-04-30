"""Ground cap — local horizontal plane under the target.

T3 of the visual remediation (PLAN_v2_remediation_agent.md §4):
the Phase-1 8×8 alternating-checker placeholder reads as a "rendering
artifact" rather than a "ground reference." This rewrite swaps it for a
1-m square grid with major lines every 5 m, alpha-modulated by
``style.GRID_OPACITY``. The grid teaches scale; the fade plane in
``ground/fade.py`` hides the hard edge of the textured region.

The ``SceneState`` does not carry ``target_x_m`` / ``target_y_m`` (the
target sits at the origin in scene coordinates per ``_layout.py``), so
the cap centers on (0, 0, 0) regardless of state. The schematic
target altitude over the ground cap is fixed by the v2 origin
convention.

Rule 19: own file (cap, fade, contact-shadow each separate).
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene._layout import GROUND_CAP_RADIUS_M

_TEXTURE_SIZE = 512
_TEXTURE_METERS_PER_SIDE = 2.0 * GROUND_CAP_RADIUS_M
_MINOR_SPACING_M = 1.0
_MAJOR_EVERY = 5  # major line every 5 minor cells


def _grid_texture() -> pv.Texture:
    """Procedural grid: light-gray base, transparent cells, opaque grid lines.

    A pixel is "on a line" when its world-space coordinate falls within
    one texture-pixel of an integer (minor) or 5-integer (major) gridline.
    Major lines get a 50%-stronger alpha than minors.
    """
    arr = np.zeros((_TEXTURE_SIZE, _TEXTURE_SIZE, 4), dtype=np.uint8)
    arr[..., :3] = 200  # light-gray base
    # Solid base alpha so the ground reads as a continuous surface, not
    # transparent grid lines floating over the void. Grid lines stamp on
    # top with stronger alpha for the scale reference.
    arr[..., 3] = int(round(255 * style.GROUND_CAP_BASE_OPACITY))
    px_per_meter = _TEXTURE_SIZE / _TEXTURE_METERS_PER_SIDE
    minor_step_px = max(int(round(px_per_meter * _MINOR_SPACING_M)), 1)
    minor_alpha = int(round(255 * style.GRID_OPACITY))
    major_alpha = int(round(255 * style.GRID_OPACITY * 1.5))
    # Stamp horizontal + vertical lines.
    for i in range(0, _TEXTURE_SIZE, minor_step_px):
        is_major = (i // minor_step_px) % _MAJOR_EVERY == 0
        a = major_alpha if is_major else minor_alpha
        arr[i, :, 3] = a
        arr[:, i, 3] = a
    return pv.Texture(arr)


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    del state  # the cap is target-centric; no SceneState fields read.
    cap = pv.Plane(
        center=(0.0, 0.0, 0.0),
        direction=(0.0, 0.0, 1.0),
        i_size=2.0 * GROUND_CAP_RADIUS_M,
        j_size=2.0 * GROUND_CAP_RADIUS_M,
        i_resolution=1,
        j_resolution=1,
    )
    cap.texture_map_to_plane(inplace=True)
    plotter.add_mesh(
        cap,
        texture=_grid_texture(),
        lighting=False,
        opacity=1.0,
        name="ground_cap",
    )
