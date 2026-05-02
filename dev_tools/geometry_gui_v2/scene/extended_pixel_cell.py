"""Extended-regime pixel-cell ground footprint (overlay primitive).

Closes BLOCKER R9-B1: when ``state.regime_override == "extended"`` the
GUI must show a translucent square on the ground at the canonical
pixel-cell footprint location. Pre-this-module the ``extended_default``
canonical view was geometrically identical to ``sphere_default`` apart
from the regime tag on the target label, which gave the user no visual
cue that the target was being treated as an extended-source patch.

Design choices:

  * **Schematic, not-to-scale size.** The actual ground sampling distance
    at the default 600 km / 1 m focal-length / 10 µm pitch configuration
    is on the order of 6 m. The user-memory rule "show altitudes via
    leader-label text, never translate geometry" applies here too — we
    pick a scene-meter footprint size (4 m × 4 m) that reads clearly
    against the 10 m ground cap and doesn't dwarf default 1–2 m target
    bodies. The numerical GSD is surfaced in the right-dock readout.
  * **Translucent fill + visible edges.** The blocker text mandates
    "translucent square ... not as an opaque orange block hiding the
    geometry beneath." TARGET_COLOR at GRID_OPACITY (0.45) for the fill;
    edges in the same hue at full opacity so the cell boundary reads as
    a deliberate primitive, not as a rendering artifact.
  * **Z-offset above the ground cap.** The cap sits at z = 0 and the
    contact-shadow disc at z = 0.001. The footprint goes at z = 0.003 so
    all four ground primitives have unique z and never z-fight at the
    canonical camera distance.
  * **Additive overlay, not target replacement.** The target dispatcher
    keeps drawing the per-shape body; the footprint is a separate
    primitive added by the builder after target. This way the user can
    see both "the geometry being modeled" and "the pixel cell that
    classifies it as extended."

C7: zero Qt imports. Rule 19: one file, one primitive.
"""

from __future__ import annotations

from typing import Final

import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene import style

PIXEL_CELL_SIDE_M: Final[float] = 4.0
PIXEL_CELL_Z_OFFSET_M: Final[float] = 0.003
PIXEL_CELL_EDGE_WIDTH: Final[float] = 1.5


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    if state.regime_override != "extended":
        return
    cell = pv.Plane(
        center=(0.0, 0.0, PIXEL_CELL_Z_OFFSET_M),
        direction=(0.0, 0.0, 1.0),
        i_size=PIXEL_CELL_SIDE_M,
        j_size=PIXEL_CELL_SIDE_M,
        i_resolution=1,
        j_resolution=1,
    )
    plotter.add_mesh(
        cell,
        color=style.TARGET_COLOR,
        opacity=style.GRID_OPACITY,
        show_edges=True,
        edge_color=style.TARGET_COLOR,
        line_width=PIXEL_CELL_EDGE_WIDTH,
        lighting=False,
        name="extended_pixel_cell",
    )
