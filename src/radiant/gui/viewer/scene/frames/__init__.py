"""Reference-frame triads — the target body-axes RPY gizmo (Part B).

Per Rule 19 / the prototype C5: one file per frame triad. The production viewer lifts only
the body-axes triad (the target orientation gizmo); the prototype's world-axes frame was
relocated to a screen-space gnomon corner widget that stays behind (ADR-0007 lift table —
the ``widgets/`` corner widgets are out of the Part-B scope).

This package imports no Qt and no physics stage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyvista as pv

    from radiant.gui.viewer.viewer_state import ViewerState as SceneState


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    from radiant.gui.viewer.scene.frames import body_axes

    body_axes.add_to_plotter(plotter, state)


__all__ = ["add_to_plotter"]
