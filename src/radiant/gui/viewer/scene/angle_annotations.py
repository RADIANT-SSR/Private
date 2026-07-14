"""Angle-annotation catalog + on-demand render orchestration (Part B, click-to-reveal).

An *angle annotation* is a revealable arc plus the numeric value pinned beside it. This
module is the single Qt-free source of **which** angles the 3D scene can annotate, how
each splits by reference frame (target-frame vs ground-frame, matching the Phase-5
:class:`~radiant.gui.widgets.geometry_readout.GeometryReadout` grouping), and which
``stage_outputs["geometry"]`` key supplies each one's *value* (arch doc §6.3 — the stage
is the single source of angle truth; the scene geometry only *draws* the arc).

  ============  =======  ========  ==================================
  name          symbol   frame     value source (stage output key)
  ============  =======  ========  ==================================
  off_nadir     η        ground    ``eta_rad``
  sun_zenith    θ_s      target    ``theta_s_rad``
  phase_angle   α_t      target    *(none — symbol only; §6.3)*
  ============  =======  ========  ==================================

The catalog owns the arc **endpoints** (so the value label sits at the arc midpoint) and
delegates the tube drawing to :mod:`radiant.gui.viewer.scene.arcs`. The numeric value
*text* is passed in by the caller (the viewer widget formats it from the stage output via
``radiant.gui.param_format`` — this scene module stays free of the api layer). A ``None``
value renders the symbol alone, never a fabricated number.

Frame constants match ``GeometryReadout``'s group titles so a test can assert the split is
consistent across the readout and the scene. No Qt, no physics stage.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import numpy as np
import numpy.typing as npt

from radiant.gui.viewer.scene import arcs, style
from radiant.gui.viewer.scene._directions import (
    observer_direction_scene,
    sun_direction_scene,
)
from radiant.gui.viewer.scene._layout import ARC_RADIUS_M

if TYPE_CHECKING:
    import pyvista as pv

    from radiant.gui.viewer.viewer_state import ViewerState as SceneState

# Reference-frame tags. "target" = angles referenced at the target's local vertical;
# "ground" = the sensor-side / platform-frame angles. These MATCH the semantics of
# ``geometry_readout``'s target-frame / ground-frame split (Phase 5 task 2).
FRAME_TARGET: Final[str] = "target"
FRAME_GROUND: Final[str] = "ground"

_ZENITH: Final[np.ndarray] = np.array([0.0, 0.0, 1.0], dtype=np.float64)


@dataclass(frozen=True)
class AngleAnnotation:
    """One annotatable angle: its arc, symbol, frame, and stage-truth key.

    Attributes
    ----------
    name:
        Stable reveal identifier (matches an ``arcs.arc_names()`` entry).
    symbol:
        The conventional glyph (η, θ_s, α_t) shown in the pinned label and the toggle.
    frame:
        :data:`FRAME_TARGET` or :data:`FRAME_GROUND` — the reference-frame split.
    stage_key:
        The ``stage_outputs["geometry"]`` key whose value the annotation displays, or
        ``None`` when the angle has no stage-output truth (phase angle — symbol only).
    color:
        The arc's family colour (also the pinned-label text colour).
    endpoints:
        Returns the two unit vectors the arc spans (used to place the value label at the
        arc midpoint).
    """

    name: str
    symbol: str
    frame: str
    stage_key: str | None
    color: str
    endpoints: Callable[[SceneState], tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]


def _off_nadir_endpoints(
    state: SceneState,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    return _ZENITH, observer_direction_scene(state)


def _sun_zenith_endpoints(
    state: SceneState,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    return _ZENITH, sun_direction_scene(state)


def _phase_endpoints(
    state: SceneState,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    return sun_direction_scene(state), observer_direction_scene(state)


_CATALOG: Final[tuple[AngleAnnotation, ...]] = (
    AngleAnnotation(
        name="off_nadir",
        symbol="η",
        frame=FRAME_GROUND,
        stage_key="eta_rad",
        color=style.SATELLITE_FAMILY,
        endpoints=_off_nadir_endpoints,
    ),
    AngleAnnotation(
        name="sun_zenith",
        symbol="θ_s",
        frame=FRAME_TARGET,
        stage_key="theta_s_rad",
        color=style.SOLAR_FAMILY,
        endpoints=_sun_zenith_endpoints,
    ),
    AngleAnnotation(
        name="phase_angle",
        symbol="α_t",
        frame=FRAME_TARGET,
        stage_key=None,
        color=style.TARGET_VECTOR_FAMILY,
        endpoints=_phase_endpoints,
    ),
)

_BY_NAME: Final[dict[str, AngleAnnotation]] = {a.name: a for a in _CATALOG}


def annotations() -> tuple[AngleAnnotation, ...]:
    """Every annotatable angle, in catalog order."""
    return _CATALOG


def annotation(name: str) -> AngleAnnotation:
    """The annotation for *name* (KeyError if unknown — programming error)."""
    return _BY_NAME[name]


def _slerp_midpoint(
    a: npt.NDArray[np.float64], b: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    """Unit vector at the great-arc midpoint between ``a`` and ``b``."""
    a = a / max(np.linalg.norm(a), 1e-12)
    b = b / max(np.linalg.norm(b), 1e-12)
    cos_theta = float(np.clip(np.dot(a, b), -1.0, 1.0))
    theta = math.acos(cos_theta)
    if theta < 1e-3:
        return a.copy()
    if theta > math.pi - 1e-3:
        up = np.array([0.0, 0.0, 1.0]) if abs(a[2]) < 0.95 else np.array([1.0, 0.0, 0.0])
        perp = np.cross(a, up)
        return perp / max(np.linalg.norm(perp), 1e-12)
    sin_theta = math.sin(theta)
    s = math.sin(0.5 * theta) / sin_theta
    mid = (a + b) * s
    return mid / max(np.linalg.norm(mid), 1e-12)


def value_label_actor_name(name: str) -> str:
    """The actor name of the pinned numeric value label for annotation *name*."""
    return f"lbl_arc_value_{name}"


def add_angle_annotation(
    plotter: pv.Plotter,
    state: SceneState,
    name: str,
    value_text: str | None,
) -> None:
    """Reveal one angle: draw its arc tube and pin its ``symbol[ = value]`` label.

    *value_text* is the pre-formatted stage-output value (with unit) the caller read from
    ``stage_outputs["geometry"]``; ``None`` renders the symbol alone (the phase-angle
    case). The label sits at the arc midpoint on the ``ARC_RADIUS_M`` sphere.
    """
    ann = _BY_NAME[name]
    arcs.add_arc(plotter, state, name)

    v1, v2 = ann.endpoints(state)
    mid = _slerp_midpoint(v1, v2) * (ARC_RADIUS_M * 1.08)
    text = ann.symbol if value_text is None else f"{ann.symbol} = {value_text}"
    plotter.add_point_labels(
        mid.reshape(1, 3),
        [text],
        name=value_label_actor_name(name),
        font_size=style.ARC_VALUE_LABEL_FONT_SIZE,
        text_color=ann.color,
        show_points=False,
        shape=None,
        always_visible=True,
    )


__all__ = [
    "AngleAnnotation",
    "FRAME_TARGET",
    "FRAME_GROUND",
    "annotations",
    "annotation",
    "add_angle_annotation",
    "value_label_actor_name",
]
