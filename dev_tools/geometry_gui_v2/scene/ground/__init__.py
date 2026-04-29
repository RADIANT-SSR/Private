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
    """Round-2 R4: re-wire the gridded ``cap`` + outer ``fade`` plane.

    The Phase-7 diet had collapsed ground rendering to the contact-shadow
    disc only — the round-1 first-cut screenshot showed the target
    floating in empty dark space with no scale reference. Round 2
    restores the full ground composition: a 1-m grid cap under the
    target (teaches scale), a viewport-color fade plane below it that
    erases the hard rectangular edge of the cap, and the contact-shadow
    disc on top so the target visibly sits *on* the ground.

    Draw order (back to front, by z): fade (z = -0.5) → cap (z = 0)
    → contact_shadow (z = +0.001). The fade-cap separation is 0.5 m
    rather than 0.001 m so the depth buffer can resolve the two at
    the round-2 camera distance (~30 m) — see fade.py for the
    z-fighting incident that drove the gap up.
    """
    from dev_tools.geometry_gui_v2.scene.ground import cap, contact_shadow, fade

    cap.add_to_plotter(plotter, state)
    fade.add_to_plotter(plotter, state)
    contact_shadow.add_to_plotter(plotter, state)
