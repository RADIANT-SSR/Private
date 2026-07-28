"""Angle-annotation catalog for the 2D schematic — the single Qt-free source.

An *angle annotation* is a revealable arc plus the numeric value pinned beside it. This
module owns **which** angles the schematic can annotate, each one's conventional symbol,
its reference-frame split (target-frame vs ground-frame, matching the Phase-5
:class:`~radiant.gui.widgets.geometry_readout.GeometryReadout` grouping), and which
``stage_outputs["geometry"]`` key supplies its *value* (arch doc §6.3 — the stage is the
single source of angle truth; the scene geometry only *draws* the arc).

  =================  =======  ========  ==================================
  name               symbol   frame     value source (stage output key)
  =================  =======  ========  ==================================
  off_nadir          η        ground    ``eta_rad``
  sun_zenith         θ_s      target    ``theta_s_rad``
  relative_azimuth   Δφ       target    ``delta_phi_rad``
  phase_angle        α_t      target    *(none — symbol only; §6.3)*
  path_zenith        θ_o      target    ``theta_o_rad``
  lower_zenith       ζ_low    target    ``theta_o_rad`` / ``eta_rad``, via
                                        :func:`lower_zenith_rad`
  =================  =======  ========  ==================================

The last two are the ADR-0011 generalized-geometry annotations. **θ_o** is the canonical
target-side path zenith on the closed domain [0, π] — acute for a down-looking scene,
obtuse for an up-looking one; it is a *different vertex* of the viewing triangle from the
sensor-side off-nadir η, so the two arcs differ by the Earth-centre central angle and are
annotated separately. **ζ_low** is the path zenith at the segment's **lower** endpoint —
the quantity every ADR-0011 §3 path segment is keyed to.

Besides the arcs the catalog names one **leader-pill** annotation, the level-arm tangent
sag :data:`LEVEL_SAG_SYMBOL` (Δh). It is not an arc and has no toggle: it is drawn like the
h_s / h_t altitude pills whenever the scene is a level arm, and hidden otherwise. Its value
is derived from the stage's θ_o + lower-endpoint altitude through the **core** horizon-guard
helper (``radiant.core.viewing_triangle.classify_horizon_topology``), so the schematic never
restates the tangent-depression formula.

The catalog carries no drawing code (that is :mod:`radiant.gui.viewer.schematic_view`,
keyed off :attr:`AngleAnnotation.name`) and no physics stage import — it is a plain data
table plus the frame constants. Colours come from the one allowlisted glyph palette
(:mod:`radiant.gui.viewer.scene.palette`); this module holds no colour literal. It
replaces the retired VTK ``scene/angle_annotations.py`` (CU-132), which drew arcs into a
``pyvista.Plotter``; the 2D schematic needs only the catalog, not the plotter drawing.

A ``None`` ``stage_key`` renders the symbol alone, never a fabricated number (the
phase-angle case — there is no stage-output phase angle, so §6.3 forbids inventing one).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from radiant.gui.viewer.scene import palette

# Reference-frame tags. "target" = angles referenced at the target's local vertical;
# "ground" = the sensor-side / platform-frame angles. These MATCH the semantics of
# ``geometry_readout``'s target-frame / ground-frame split (Phase 5 task 2).
FRAME_TARGET: Final[str] = "target"
FRAME_GROUND: Final[str] = "ground"

#: Symbol of the level-arm tangent-sag leader pill (a length, not an angle — see the
#: module docstring). Kept here so the schematic's pill and this catalog cannot drift.
LEVEL_SAG_SYMBOL: Final[str] = "Δh"

#: LOS directions the stage derives (ADR-0011 decision 1). ``"up"`` is the one that makes
#: the SENSOR the path's lower endpoint; ``"down"`` and ``"level"`` leave the target there.
LOS_DOWN: Final[str] = "down"
LOS_UP: Final[str] = "up"
LOS_LEVEL: Final[str] = "level"


def lower_zenith_rad(theta_o_rad: float, eta_rad: float, los_direction: str) -> float:
    """The path zenith ζ_low at the segment's **lower** endpoint [rad], from stage values.

    A fixed, direction-keyed transform of two stage outputs — never a scene
    recomputation (§6.3). Which endpoint is the lower one is read off the
    stage-published ``los_direction`` (ADR-0011 decision 1, derived from the altitude
    pair), and the transform follows from which vertex of the viewing triangle that is:

    * ``"down"`` — the **target** is the lower endpoint and θ_o is already its zenith,
      so ``ζ_low = θ_o`` exactly.
    * ``"level"`` — both endpoints sit at the same altitude, so both see the path at the
      same zenith: ``ζ_low = θ_o``. The isoceles triangle gives ``η = π − θ_o`` exactly
      (``core.viewing_triangle.eta_from_theta_o``), so the up-looking form ``π − η`` returns
      the same value here — the two branches meet continuously at equal altitudes.
    * ``"up"`` — the **sensor** is the lower endpoint. The stage's off-nadir η is measured
      from the sensor's *nadir* and is the obtuse branch for an up-looking scene
      (``core.viewing_triangle.eta_from_theta_o``), so the sensor's zenith to the target is
      its supplement: ``ζ_low = π − η``.

    Note the up-looking case is **not** ``π − θ_o``: θ_o and η are read at different
    vertices of the same spherical triangle, and they differ by the Earth-centre central
    angle. For a ground sensor viewing a 400 km target at θ_o = 150°, ``π − η`` = 32.10°
    while ``π − θ_o`` = 30.00° — a 2.1° error, far outside any display tolerance. The
    exact identity ``θ_o = π − ζ_up`` (``core.viewing_triangle.LowerEndpointSolution``)
    is what ``π − η`` reproduces.
    """
    if los_direction == LOS_UP:
        return math.pi - eta_rad
    return theta_o_rad


@dataclass(frozen=True)
class AngleAnnotation:
    """One annotatable angle: its symbol, frame, stage-truth key, and arc colour.

    Attributes
    ----------
    name:
        Stable reveal identifier (matches the schematic's ``_draw_angle_arcs`` dispatch
        and the side-panel toggle).
    symbol:
        The conventional glyph (η, θ_s, Δφ, α_t) shown in the pinned label and the toggle.
    frame:
        :data:`FRAME_TARGET` or :data:`FRAME_GROUND` — the reference-frame split.
    stage_key:
        The ``stage_outputs["geometry"]`` key whose value the annotation displays, or
        ``None`` when the angle has no stage-output truth (phase angle — symbol only).
        ``lower_zenith`` records ``theta_o_rad`` here (its down/level source and the key
        that fixes its reference-frame grouping) but displays that key **through**
        :func:`lower_zenith_rad`, which swaps to ``eta_rad`` for an up-looking scene.
    color:
        The arc's family colour (also the pinned-label text colour).
    """

    name: str
    symbol: str
    frame: str
    stage_key: str | None
    color: str


_CATALOG: Final[tuple[AngleAnnotation, ...]] = (
    AngleAnnotation(
        name="off_nadir",
        symbol="η",
        frame=FRAME_GROUND,
        stage_key="eta_rad",
        color=palette.SATELLITE_FAMILY,
    ),
    AngleAnnotation(
        name="sun_zenith",
        symbol="θ_s",
        frame=FRAME_TARGET,
        stage_key="theta_s_rad",
        color=palette.SOLAR_FAMILY,
    ),
    AngleAnnotation(
        name="relative_azimuth",
        symbol="Δφ",
        frame=FRAME_TARGET,
        stage_key="delta_phi_rad",
        color=palette.AZIMUTH_FAMILY,
    ),
    AngleAnnotation(
        name="phase_angle",
        symbol="α_t",
        frame=FRAME_TARGET,
        stage_key=None,
        color=palette.TARGET_VECTOR_FAMILY,
    ),
    # -- ADR-0011 generalized viewing geometry ---------------------------------
    # Both are path zeniths (measured from a local vertical to the path), so both group
    # with the target-frame angles the readout puts ``theta_o_rad`` in.
    AngleAnnotation(
        name="path_zenith",
        symbol="θ_o",
        frame=FRAME_TARGET,
        stage_key="theta_o_rad",
        color=palette.SURFACE_FAMILY,
    ),
    AngleAnnotation(
        name="lower_zenith",
        symbol="ζ_low",
        frame=FRAME_TARGET,
        stage_key="theta_o_rad",
        color=palette.TARGET_COLOR,
    ),
)

_BY_NAME: Final[dict[str, AngleAnnotation]] = {a.name: a for a in _CATALOG}


def annotations() -> tuple[AngleAnnotation, ...]:
    """Every annotatable angle, in catalog order."""
    return _CATALOG


def annotation(name: str) -> AngleAnnotation:
    """The annotation for *name* (KeyError if unknown — programming error)."""
    return _BY_NAME[name]


__all__ = [
    "AngleAnnotation",
    "FRAME_TARGET",
    "FRAME_GROUND",
    "LEVEL_SAG_SYMBOL",
    "LOS_DOWN",
    "LOS_UP",
    "LOS_LEVEL",
    "annotations",
    "annotation",
    "lower_zenith_rad",
]
