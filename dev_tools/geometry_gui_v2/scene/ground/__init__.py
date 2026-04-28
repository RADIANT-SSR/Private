"""Ground primitives — outer fade, gridded cap, and contact-shadow disc.

Per Rule 19 / C5: one file per ground primitive. T3 of the visual
remediation adds the outer fade plane (``fade.py``) so the gridded cap
no longer ends in a hard rectangular edge against the void.

Draw order (back to front): fade → cap → contact_shadow. The fade sits
at z = -0.001, the cap at z = 0 with the grid texture on top, and the
contact-shadow disc at z = +0.001 so all three primitives have unique
z and never z-fight.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dev_tools.geometry_gui_v2.app.state import SceneState

if TYPE_CHECKING:
    import pyvista as pv


def add_to_plotter(plotter: "pv.Plotter", state: SceneState) -> None:
    from dev_tools.geometry_gui_v2.scene.ground import cap, contact_shadow, fade

    fade.add_to_plotter(plotter, state)
    cap.add_to_plotter(plotter, state)
    contact_shadow.add_to_plotter(plotter, state)
