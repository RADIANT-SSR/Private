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
  =================  =======  ========  ==================================

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

from dataclasses import dataclass
from typing import Final

from radiant.gui.viewer.scene import palette

# Reference-frame tags. "target" = angles referenced at the target's local vertical;
# "ground" = the sensor-side / platform-frame angles. These MATCH the semantics of
# ``geometry_readout``'s target-frame / ground-frame split (Phase 5 task 2).
FRAME_TARGET: Final[str] = "target"
FRAME_GROUND: Final[str] = "ground"


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
    "annotations",
    "annotation",
]
