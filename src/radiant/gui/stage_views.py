"""Per-stage contextual-center composition spec (arch doc §4.4 / §4.4.1 / §4.7).

When a signal-chain stage is selected in the strip, the center column shows **that
stage's contextual view and nothing else** (arch doc §4.4): its outputs readout, its
plot(s), and any relocated detail content (the MTF per-term table, the noise-budget
table, the geometry angle readout). This module is the single, **Qt-free** source of
what each stage's center composite contains — the relocation map of §4.7 turned into
data. No Qt, no matplotlib, no plotting logic lives here; the
:class:`~radiant.gui.widgets.stage_center.StageCenter` reads this spec and assembles the
composite from existing widgets, and every figure it draws is one call on the public
``result.plot.*`` surface (one GUI action ↔ one API call, GUI plan §4.1).

Every content item is a **[exists]** surface today (arch doc §4.4.1): the shipped
``result.plot.*`` accessors (``mtf``, ``noise_budget``, ``psf``, ``mtf_budget``,
``spectral_source``, ``spectral_atmosphere``, ``spectral_inband``), the metric surface,
and the ``stage_outputs`` scalar readouts. Bespoke per-stage content that needs a new
framework capability — the Optics pupil/coating maps (Gaps 89/90), the Source
pre-atmosphere emission spectrum (Gap 91), and the per-λ noise decomposition (Gap 92) —
is **not** built here; those are separate later per-stage tasks. Platform and Readout are
v1-minimal (owner-ratified): an outputs readout plus a themed note, no invented content.

Being pure data, the composition table is unit-tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final


@dataclass(frozen=True, slots=True)
class PlotSpec:
    """One plot section in a stage's center composite.

    Attributes
    ----------
    title:
        The human title shown above the figure.
    method:
        The ``result.plot.*`` accessor name to call (``"mtf"`` / ``"psf"`` /
        ``"spectral_source"`` / …) — the one API call that produces the figure.
    """

    title: str
    method: str


@dataclass(frozen=True, slots=True)
class StageComposition:
    """What one stage's contextual-center composite contains (arch doc §4.4).

    All fields are additive sections rendered top-to-bottom in this order: outputs
    readout, embedded relocated widget (geometry readout / MTF panel / noise panel),
    plot section(s), performance-metric readout, themed note. A stage sets only the
    sections it owns; the rest stay empty.

    Attributes
    ----------
    title:
        The stage heading shown at the top of the center.
    geometry_readout:
        Show the geometry angle/range readout (Geometry only).
    mtf_panel:
        Embed the MTF per-term table + overlay (relocated from the MTF detail tab).
    noise_panel:
        Embed the noise per-term table + bars + click-to-explain (relocated from the
        Noise Budget detail tab).
    outputs:
        Show a scalar readout of ``stage_outputs["<stage>"]`` (values with units).
    metrics:
        Show the performance-metric readout (Performance only).
    plots:
        Zero or more plot sections, each a :class:`PlotSpec`.
    note:
        An optional themed note (deferred content / v1-minimal rationale).
    """

    title: str
    geometry_readout: bool = False
    mtf_panel: bool = False
    noise_panel: bool = False
    outputs: bool = False
    metrics: bool = False
    plots: tuple[PlotSpec, ...] = field(default_factory=tuple)
    note: str | None = None


# Deferred/minimal notes kept as named constants so they read once and stay honest.
_SOURCE_NOTE: Final[str] = (
    "Shown: source & background radiance at aperture (post-atmosphere). "
    "The pre-atmosphere emitted target/background spectrum is deferred (Gap 91)."
)
_PLATFORM_NOTE: Final[str] = (
    "Platform view is v1-minimal (owner-ratified: no dedicated MTF here). The smear and "
    "jitter MTF terms appear in the Optics and Performance MTF overlays."
)
_SPECTRAL_NOTE: Final[str] = (
    "A per-wavelength noise spectrum is deferred (Gap 92); noise is scalar per term, "
    "computed post-integration (Rule 8) — see the Detector view for the noise budget."
)
_READOUT_NOTE: Final[str] = (
    "Readout view is v1-minimal (owner-ratified: TBD). The full noise budget is on the "
    "Detector view (result.plot.noise_budget)."
)


# namespace -> center composition, row-by-row from the arch-doc §4.4.1 table. Keys are
# the real chain namespaces (matching ``RadiantSession.stage_names`` /
# ``Sensor.parameter_defs()`` — note ``spectral_integration``, not ``spectral``; CU-106).
STAGE_COMPOSITIONS: Final[dict[str, StageComposition]] = {
    # Derived angles/ranges readout (the arch-doc "angle summary"); 3D viewer is Phases 6–7.
    "geometry": StageComposition(title="Geometry", geometry_readout=True),
    # Source & background radiance at aperture — result.plot.spectral_source() (Gap 86).
    "source": StageComposition(
        title="Source",
        plots=(PlotSpec("Source & background radiance at aperture", "spectral_source"),),
        note=_SOURCE_NOTE,
    ),
    # τ_atm & L_path overlay + the at-aperture radiance now that atmosphere is applied.
    "atmosphere": StageComposition(
        title="Atmosphere",
        plots=(
            PlotSpec("τ_atm & L_path vs wavelength", "spectral_atmosphere"),
            PlotSpec("Source & background radiance at aperture", "spectral_source"),
        ),
    ),
    # MTF per-term table + overlay (relocated MTF tab) + the effective PSF.
    "optics": StageComposition(
        title="Optics",
        outputs=True,
        mtf_panel=True,
        plots=(PlotSpec("Effective PSF", "psf"),),
    ),
    # v1-minimal: a scalar outputs readout (jitter/smear/EE_box) + a themed note.
    "platform": StageComposition(title="Platform", outputs=True, note=_PLATFORM_NOTE),
    # In-band signal spectral radiance + the scalar electron budget + the Gap-92 note.
    "spectral_integration": StageComposition(
        title="Spectral Integration",
        outputs=True,
        plots=(PlotSpec("In-band signal spectral radiance", "spectral_inband"),),
        note=_SPECTRAL_NOTE,
    ),
    # Noise per-term table + bars + click-to-explain (relocated Noise Budget tab).
    "detector": StageComposition(title="Detector", outputs=True, noise_panel=True),
    # v1-minimal: a scalar outputs readout + a themed note pointing at the noise budget.
    "readout": StageComposition(title="Readout", outputs=True, note=_READOUT_NOTE),
    # All metrics (values + units) + system MTF and the MTF budget.
    "performance": StageComposition(
        title="Performance",
        metrics=True,
        plots=(
            PlotSpec("System MTF", "mtf"),
            PlotSpec("MTF budget", "mtf_budget"),
        ),
    ),
}

# The stage the center lands on after the first evaluation when the user has not yet
# clicked a stage: Performance — the summary view (metrics + system MTF), the on-spec
# successor to the old post-evaluate default figure (result.plot.mtf()).
DEFAULT_STAGE: Final[str] = "performance"


def composition_for(namespace: str | None) -> StageComposition | None:
    """The :class:`StageComposition` for *namespace* (``None`` / unknown → ``None``).

    ``None`` means "no stage selected" — the center shows its pre-evaluate placeholder.
    An unknown namespace (a stage grown without a §4.4.1 row) also returns ``None``
    rather than erroring, so navigation never crashes on a new stage.
    """
    if namespace is None:
        return None
    return STAGE_COMPOSITIONS.get(namespace)


__all__ = [
    "PlotSpec",
    "StageComposition",
    "STAGE_COMPOSITIONS",
    "DEFAULT_STAGE",
    "composition_for",
]
