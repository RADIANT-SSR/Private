"""Ground cap — local horizontal plane under the target.

Phase 2 (PLAN_v2.md §10 step 5): a flat ``pv.Plane`` at z = 0 with a
procedural checker texture at ``style.GRID_OPACITY``. The grid teaches
scale without dominating; opacity is intentionally low so the cap reads
as a recessive ground reference, not a dominant feature.

The texture is generated per-call from a small numpy array (8×8 cells
upsampled to 512×512 by PyVista's texture filter — the discrete cells
preserve sharp edges).
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene._layout import GROUND_CAP_RADIUS_M

_TEXTURE_SIZE = 512
_TEXTURE_CELLS = 8


def _checker_texture() -> pv.Texture:
    """Build an 8×8 alternating-gray checker tile, alpha-modulated by
    ``style.GRID_OPACITY``."""
    cell = _TEXTURE_SIZE // _TEXTURE_CELLS
    base = np.zeros((_TEXTURE_SIZE, _TEXTURE_SIZE, 4), dtype=np.uint8)
    for i in range(_TEXTURE_CELLS):
        for j in range(_TEXTURE_CELLS):
            shade = 80 if (i + j) % 2 == 0 else 110
            base[
                i * cell : (i + 1) * cell,
                j * cell : (j + 1) * cell,
                0:3,
            ] = shade
    base[:, :, 3] = int(round(255 * style.GRID_OPACITY))
    return pv.Texture(base)


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    del state  # Phase 2 keeps the cap at a fixed schematic size.
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
        texture=_checker_texture(),
        lighting=False,
        opacity=1.0,
        name="ground_cap",
    )
