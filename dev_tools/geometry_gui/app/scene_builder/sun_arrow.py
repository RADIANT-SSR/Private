"""Sun-direction arrow — Phase 6.

Draws an arrow originating at the target and pointing **toward the sun**.
The arrow direction is computed in the target's *local horizontal frame*
from `state.solar_zenith_rad` (theta_s) and `state.relative_azimuth_rad`
(delta_phi), then rotated into the scene-display frame using the target's
position on the (display-scaled) Earth.

Local horizontal frame at the target
------------------------------------
Convention: target sits at the +Z pole of the display Earth (see
`build_scene.target_position_display`). At that point the local-zenith
direction equals the global +Z, the local-east is +X, and the local-north
is +Y. The sun unit vector in that local frame is:

    n_sun_local = ( sin(theta_s) * cos(delta_phi),
                    sin(theta_s) * sin(delta_phi),
                    cos(theta_s) )

Because the target sits on the Z-axis pole, the local-horizontal axes
already coincide with the global X/Y/Z, so no further rotation is needed
to express `n_sun` in the scene-display frame. (If a future phase moves
the target off the +Z pole, this is the place that needs a local→scene
rotation; the docstring above and PLAN.md §8 G1 record the assumption.)

Caveat (PLAN.md §8 G1)
----------------------
The sun zenith and azimuth are *only* GUI sliders today — they do not
have entries in the production parameter schema. This dev tool is the
sole consumer; do not import these values from anywhere else.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from dev_tools.geometry_gui.app.state import SceneState

# Display length of the sun arrow (same family of magnitudes as the body
# axes / target shape). Long enough to read from the default camera but
# short enough not to dominate the frame.
SUN_ARROW_DISPLAY_LENGTH: Final[float] = 0.5

# Cone tip dimensions (display units). Roughly 20% of the shaft length.
_TIP_LENGTH: Final[float] = SUN_ARROW_DISPLAY_LENGTH * 0.18
_TIP_RADIUS: Final[float] = _TIP_LENGTH * 0.4

_SUN_COLOR: Final[str] = "gold"


def sun_unit_vector_local(state: SceneState) -> npt.NDArray[np.float64]:
    """Return the unit vector pointing *toward* the sun in the local
    horizontal frame at the target (+X east, +Y north, +Z zenith)."""
    theta = state.solar_zenith_rad
    phi = state.relative_azimuth_rad
    return np.array(
        [
            math.sin(theta) * math.cos(phi),
            math.sin(theta) * math.sin(phi),
            math.cos(theta),
        ],
        dtype=np.float64,
    )


def sun_unit_vector_scene(state: SceneState) -> npt.NDArray[np.float64]:
    """Sun unit vector expressed in scene-display coordinates.

    With the target pinned to the +Z pole of the display Earth (see module
    docstring), the local-horizontal axes coincide with the global axes
    and this function returns `sun_unit_vector_local(state)` unchanged.
    """
    return sun_unit_vector_local(state)


def sun_arrow_traces(
    state: SceneState,
    target_pos_display: npt.NDArray[np.float64],
) -> list[go.Scatter3d | go.Cone]:
    """Arrow from `target_pos_display` along the sun direction.

    The shaft is a `Scatter3d` line; the tip is a `Cone` for the arrowhead.
    Hover text on both reports `theta_s` and `delta_phi` in degrees so a
    developer can read the configuration straight off the scene.
    """
    n_sun = sun_unit_vector_scene(state)
    origin = np.asarray(target_pos_display, dtype=np.float64)
    tip_base = origin + n_sun * SUN_ARROW_DISPLAY_LENGTH
    tip_apex = origin + n_sun * (SUN_ARROW_DISPLAY_LENGTH + _TIP_LENGTH)

    theta_deg = math.degrees(state.solar_zenith_rad)
    phi_deg = math.degrees(state.relative_azimuth_rad)
    label = f"Sun (theta_s = {theta_deg:.1f} deg, delta_phi = {phi_deg:.1f} deg)"

    shaft = go.Scatter3d(
        x=[origin[0], tip_base[0]],
        y=[origin[1], tip_base[1]],
        z=[origin[2], tip_base[2]],
        mode="lines",
        line=dict(color=_SUN_COLOR, width=6),
        name=label,
        hoverinfo="name",
        showlegend=True,
    )
    tip = go.Cone(
        x=[tip_base[0]],
        y=[tip_base[1]],
        z=[tip_base[2]],
        u=[(tip_apex[0] - tip_base[0])],
        v=[(tip_apex[1] - tip_base[1])],
        w=[(tip_apex[2] - tip_base[2])],
        sizemode="absolute",
        sizeref=_TIP_RADIUS * 2.0,
        anchor="tail",
        colorscale=[[0.0, _SUN_COLOR], [1.0, _SUN_COLOR]],
        showscale=False,
        name=label,
        hoverinfo="name",
        showlegend=False,
    )
    return [shaft, tip]
