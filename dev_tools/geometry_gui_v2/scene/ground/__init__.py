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
    """Phase-7 diet: only the contact-shadow disc renders by default.

    The gridded ``cap`` and the ``fade`` plane are intentionally not
    invoked here; the gridded ground reads as "engineering plot" rather
    than the soft "object sits on something" the reference design calls
    for. The two modules are retained on disk so a future high-detail
    mode can opt back in without re-implementing them (Rule 19 — they
    are independent primitives, kept independently).
    """
    from dev_tools.geometry_gui_v2.scene.ground import contact_shadow

    contact_shadow.add_to_plotter(plotter, state)
