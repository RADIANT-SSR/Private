"""Angle-arc primitives — off-nadir (η), sun-zenith (θ_s), phase-angle (α_t).

Per Rule 19 / the prototype C5: one file per arc. Each arc is the curved tube along the
great circle on a unit sphere centred on the target, between the two relevant unit vectors
(computed by :mod:`radiant.gui.viewer.scene._directions`).

Part B renders arcs **on demand** (click-to-reveal): :func:`add_arc` draws exactly one
named arc, dispatched through :data:`ARC_ADDERS`. The whole-set :func:`add_to_plotter`
(all three) is retained for callers that want every arc at once. This package imports no
Qt and no physics stage.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    import pyvista as pv

    from radiant.gui.viewer.viewer_state import ViewerState as SceneState

# Short reveal name → the module-level ``add_to_plotter`` that draws that arc. The names
# are the stable public identifiers the viewer's reveal API and the angle-annotation
# catalog key on (they match ``angle_annotations.AngleAnnotation.name``).
_ARC_NAMES: Final[tuple[str, ...]] = ("off_nadir", "sun_zenith", "phase_angle")


def add_arc(plotter: pv.Plotter, state: SceneState, name: str) -> None:
    """Draw the single named arc onto *plotter*.

    Raises ``KeyError`` for an unknown *name* — callers pass a name from
    :func:`arc_names`, so an unknown name is a programming error, not user input.
    """
    ARC_ADDERS[name](plotter, state)


def arc_names() -> tuple[str, ...]:
    """The reveal names of every available arc (stable order)."""
    return _ARC_NAMES


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    """Draw every arc at once (whole-set convenience; Part A parity)."""
    for name in _ARC_NAMES:
        add_arc(plotter, state, name)


def _adders() -> dict[str, Callable[[pv.Plotter, SceneState], None]]:
    from radiant.gui.viewer.scene.arcs import off_nadir, phase_angle, sun_zenith

    return {
        "off_nadir": off_nadir.add_to_plotter,
        "sun_zenith": sun_zenith.add_to_plotter,
        "phase_angle": phase_angle.add_to_plotter,
    }


class _LazyAdders:
    """Lazily resolve the per-arc adders so importing ``arcs`` needs no PyVista."""

    def __getitem__(self, name: str) -> Callable[[pv.Plotter, SceneState], None]:
        return _adders()[name]


ARC_ADDERS: Final[_LazyAdders] = _LazyAdders()


__all__ = ["add_arc", "add_to_plotter", "arc_names", "ARC_ADDERS"]
