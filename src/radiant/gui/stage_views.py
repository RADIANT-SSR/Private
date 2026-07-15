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
and the ``stage_outputs`` scalar readouts. The Source stage instrument (GUI plan Phase
PS-1) consumes the FP-1
``spectral_source_emission`` accessor (Gap 91 closed) and adds editable radiometric inputs
plus the shared target-shape editor. Bespoke per-stage content that still needs a new
framework capability — the Optics pupil/coating maps (Gaps 89/90) and the per-λ noise
decomposition (Gap 92) — is **not** built here; those are separate later per-stage tasks.
Platform and Readout are v1-minimal (owner-ratified): an outputs readout plus a themed
note, no invented content.

A stage may optionally declare named :class:`StageSubView` tabs (the deferred multi-tab
hook, arch doc §4.4): when a stage's content grows past what one pane holds comfortably, a
later phase populates ``StageComposition.subviews`` with two or more sub-views and the
pane renders them as a ``QTabWidget``. v1 declares none — every stage is a single pane.

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
class StageSubView:
    """One named tab of a stage's center composite — the deferred multi-tab hook.

    A stage that would overload a single scroll pane (many plots / large tables across
    distinct concerns) may declare **two or more** named sub-views; the
    :class:`~radiant.gui.widgets.stage_center.StagePane` then renders each in a tab of a
    ``QTabWidget`` instead of stacking everything in one pane (arch doc §4.4). Each
    sub-view carries the **same content fields** as :class:`StageComposition` (minus the
    stage title and nested sub-views) — so a tab is just a scoped composite.

    v1 declares **no** sub-views: every shipped stage renders as a single pane
    (``StageComposition.subviews`` empty). This class is the provisioned seam a later
    detailed phase fills when a stage's content genuinely needs tab separation; adding it
    now keeps that a data change (populate ``subviews``), not a widget rewrite.

    Attributes
    ----------
    title:
        The tab label.
    geometry_form, geometry_readout, geometry_viewer, mtf_panel, noise_panel, outputs, \
    metrics, plots, note:
        The same section fields as :class:`StageComposition`, scoped to this tab.
        ``geometry_viewer`` embeds the geometry schematic viewer (ADR-0007, Geometry "Schematic").
    """

    title: str
    geometry_form: bool = False
    geometry_readout: bool = False
    geometry_viewer: bool = False
    source_inputs: bool = False
    target_shape: bool = False
    mtf_panel: bool = False
    noise_panel: bool = False
    outputs: bool = False
    metrics: bool = False
    plots: tuple[PlotSpec, ...] = field(default_factory=tuple)
    note: str | None = None


@dataclass(frozen=True, slots=True)
class StageComposition:
    """What one stage's contextual-center composite contains (arch doc §4.4).

    All fields are additive sections rendered top-to-bottom in this order: outputs
    readout, embedded relocated widget (geometry readout / MTF panel / noise panel),
    plot section(s), performance-metric readout, themed note. A stage sets only the
    sections it owns; the rest stay empty.

    A stage may **optionally** declare named :attr:`subviews`; when two or more are
    present, :class:`~radiant.gui.widgets.stage_center.StagePane` renders them as tabs
    (a ``QTabWidget``) instead of the single flat pane (the deferred multi-tab hook, arch
    doc §4.4). With zero or one sub-view the stage renders as today — a single composite
    pane from the section fields below. **Every v1 stage leaves** ``subviews`` **empty.**

    Attributes
    ----------
    title:
        The stage heading shown at the top of the center.
    geometry_form:
        Show the stage-0 input-mode forms — the mode selectors + schema-driven fields
        (Geometry only; the arch-doc §4.4 "Inputs" section, GUI plan Phase 5).
    geometry_readout:
        Show the geometry angle/range readout (Geometry only).
    geometry_viewer:
        Embed the geometry schematic viewer — the 2D orthographic line-schematic bound to
        the geometry outputs (Geometry "Schematic" tab, ADR-0007 / GUI plan Phase 7).
    source_inputs:
        Show the Source stage's radiometric Inputs card — target/background/contrast-reference
        (ε, T) as schema-driven :class:`FieldRow`s (Source only, GUI plan Phase PS-1).
    target_shape:
        Show the shared target shape/size/orientation editor (shape combo + dimension fields
        + RPY) — the same widget the Geometry Schematic tab mounts, editing the one
        ``source.target.shape*`` parameter set (Source only, GUI plan Phase PS-1).
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
    subviews:
        Optional named tabs (the deferred multi-tab hook). Empty in v1 → single pane;
        two or more → the pane renders a ``QTabWidget``. The section fields above then
        describe the pane's title only; each tab's content comes from its
        :class:`StageSubView`.
    """

    title: str
    geometry_form: bool = False
    geometry_readout: bool = False
    geometry_viewer: bool = False
    source_inputs: bool = False
    target_shape: bool = False
    mtf_panel: bool = False
    noise_panel: bool = False
    outputs: bool = False
    metrics: bool = False
    plots: tuple[PlotSpec, ...] = field(default_factory=tuple)
    note: str | None = None
    subviews: tuple[StageSubView, ...] = field(default_factory=tuple)


# Deferred/minimal notes kept as named constants so they read once and stay honest.
_SOURCE_NOTE: Final[str] = (
    "Shown: pre-atmosphere target/background emission (primary) + at-aperture radiance "
    "(post-atmosphere). All source inputs are shown ungated; per-scenario-type input "
    "relevance is deferred (Gap 85)."
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
    # Stage-0 is a two-tab composite (GUI plan Phase 7 "Inputs | Schematic" split): an
    # "Inputs" tab with the input-mode forms (§4.4 Inputs, Phase 5) + the derived
    # angles/ranges readout, and a "Schematic" tab with the embedded 2D geometry
    # schematic viewer (ADR-0007, superseded 2026-07-14 — 2D orthographic Qt schematic).
    # The tabbed sub-view hook renders them as a QTabWidget.
    "geometry": StageComposition(
        title="Geometry",
        subviews=(
            StageSubView(title="Inputs", geometry_form=True, geometry_readout=True),
            StageSubView(title="Schematic", geometry_viewer=True),
        ),
    ),
    # The Source stage instrument (GUI plan Phase PS-1, arch doc §4.4.1 Source rows):
    # editable radiometric inputs + shared shape/orientation editor + the tentative-regime
    # outputs readout + the pre-atmosphere emission spectra (target + background, FP-1) with
    # the at-aperture radiance kept as a secondary plot.
    "source": StageComposition(
        title="Source",
        source_inputs=True,
        target_shape=True,
        outputs=True,
        plots=(
            PlotSpec(
                "Target & background emission (before atmosphere)",
                "spectral_source_emission",
            ),
            PlotSpec("Source & background radiance at aperture", "spectral_source"),
        ),
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
    "StageSubView",
    "StageComposition",
    "STAGE_COMPOSITIONS",
    "DEFAULT_STAGE",
    "composition_for",
]
