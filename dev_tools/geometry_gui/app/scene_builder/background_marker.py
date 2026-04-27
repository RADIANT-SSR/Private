"""Background marker — Phase 6.

Draws a colored ring around the target marker, color-coded by
`state.background_kind`. The tooltip on the ring names the corresponding
RADIANT descriptor class (from `radiant.core.descriptors`) so a developer
can confirm at a glance which descriptor the radiometric chain would use.

`background_kind == "none"` produces no trace; the GUI is silent rather
than drawing an empty ring.

Caveat: the GUI's `background_kind` is a four-way enum keyed to descriptor
classes by name. The descriptor classes themselves are the source of truth;
this module only displays which one the slider has selected.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from radiant.core.descriptors import (
    AtApertureBackground,
    ColdSpaceBackground,
    GroundBackground,
    UserSpectralBackground,
)

from dev_tools.geometry_gui.app.state import BackgroundKind, SceneState

# Ring sits just outside the target shape's display radius (1.0) so the
# shape mesh is not occluded by the marker (Phase 8 redesign, PLAN.md §11).
_RING_DISPLAY_RADIUS: Final[float] = 1.75
_RING_N_SEGMENTS: Final[int] = 64

# background_kind → (color, descriptor class name shown on hover).
# `UserSpectralBackground` is *not* selectable from the current dropdown
# (PLAN.md §"Sliders") but is included in the descriptor table for
# completeness and to keep the docstring's class list accurate.
_BACKGROUND_DISPLAY: Final[dict[BackgroundKind, tuple[str, str]]] = {
    "none": ("", ""),
    "cold_space": ("darkblue", ColdSpaceBackground.__name__),
    "ground": ("saddlebrown", GroundBackground.__name__),
    "at_aperture": ("dimgray", AtApertureBackground.__name__),
}

# Cross-check: the descriptor names referenced above must actually exist
# in `radiant.core.descriptors`. Keep the import and the table in lock-step.
_ = UserSpectralBackground  # imported for the docstring class list


def background_marker_traces(
    state: SceneState,
    target_pos_display: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Ring around the target colored by `state.background_kind`.

    Returns `[]` for `background_kind == "none"` so the scene draws nothing.
    Otherwise returns a single `Scatter3d` line trace describing the ring
    in the local horizontal plane (z = target z).
    """
    kind = state.background_kind
    color, descriptor_name = _BACKGROUND_DISPLAY[kind]
    if kind == "none":
        return []

    angles = np.linspace(0.0, 2.0 * np.pi, _RING_N_SEGMENTS, endpoint=True)
    cx, cy, cz = (
        float(target_pos_display[0]),
        float(target_pos_display[1]),
        float(target_pos_display[2]),
    )
    xs = cx + _RING_DISPLAY_RADIUS * np.cos(angles)
    ys = cy + _RING_DISPLAY_RADIUS * np.sin(angles)
    zs = np.full_like(angles, cz)

    label = f"Background: {kind} ({descriptor_name})"
    return [
        go.Scatter3d(
            x=xs,
            y=ys,
            z=zs,
            mode="lines",
            line=dict(color=color, width=5),
            name=label,
            hoverinfo="name",
            showlegend=True,
        )
    ]
