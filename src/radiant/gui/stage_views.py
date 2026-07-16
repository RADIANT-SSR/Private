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
hook, arch doc §4.4): when a stage's content grows past what one pane holds comfortably,
``StageComposition.subviews`` carries two or more sub-views and the pane renders them as a
``QTabWidget``. The **Geometry** (Inputs | Schematic), **Optics** (Inputs | MTF | PSF &
Pupil | Throughput, GUI plan Phase PS-2), and **Detector** (Inputs | Noise | Detector + PSF,
GUI plan Phase PS-3) stages use the hook; the rest are single panes.

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

    The **Geometry**, **Optics** (GUI plan Phase PS-2), and **Detector** (GUI plan Phase PS-3)
    stages declare sub-views; a stage whose content fits one pane declares none
    (``StageComposition.subviews`` empty). Turning a stage tabbed is a data change (populate
    ``subviews``), not a widget rewrite.

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
    atmosphere_inputs: bool = False
    target_shape: bool = False
    optics_inputs: bool = False
    element_editor: bool = False
    detector_inputs: bool = False
    detector_illustration: bool = False
    spectral_inputs: bool = False
    platform_inputs: bool = False
    readout_inputs: bool = False
    mtf_panel: bool = False
    noise_panel: bool = False
    noise_panel_chart: bool = True
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
    doc §4.4). With zero or one sub-view the stage renders as a single composite pane from
    the section fields below. The **Geometry**, **Optics** (GUI plan Phase PS-2), and
    **Detector** (GUI plan Phase PS-3) stages declare sub-views; the rest leave ``subviews`` empty.

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
    atmosphere_inputs:
        Show the Atmosphere stage's editable Inputs card — the ``atmosphere.model`` selector
        with the active backend's parameters (simple / MODTRAN tape7 / tabulated files /
        interpolated run-matrix / exo note) + turbulence r₀ as schema-driven
        :class:`FieldRow`s (Atmosphere only, GUI Capability Expansion plan GS-2).
    target_shape:
        Show the shared target shape/size/orientation editor (shape combo + dimension fields
        + RPY) — the same widget the Geometry Schematic tab mounts, editing the one
        ``geometry.target.shape*`` parameter set (Source only, GUI plan Phase PS-1).
    optics_inputs:
        Show the Optics stage's editable inputs card — aperture / focal length / f-number /
        obscuration / spiders / scalar throughput / WFE / optics temperature as schema-driven
        :class:`FieldRow`s (Optics only, GUI plan Phase PS-2).
    element_editor:
        Show the optical element-train table editor — the ADR-0009 D2 declarative-document
        editor committing through one ``Sensor.set_optical_elements`` call, ε derived
        read-only per Rule 5 (Optics "Elements" tab, GUI Capability Expansion plan GS-4).
    detector_inputs:
        Show the Detector stage's editable inputs card — quantum efficiency / dark rate /
        pixel pitch x,y / fill factor / detector temperature as schema-driven
        :class:`FieldRow`s (Detector only, GUI plan Phase PS-3).
    platform_inputs:
        Show the Platform stage's editable inputs card — jitter RMS (isotropic + cross/along-
        track) and the smear knobs (ground velocity + focal-plane smear length) as schema-driven
        :class:`FieldRow`s (Platform only, GUI plan Phase PS-5, v1-minimal).
    readout_inputs:
        Show the Readout stage's editable inputs card — read noise / conversion gain / ADC bit
        depth / full-well capacity as schema-driven :class:`FieldRow`s (Readout only, GUI plan
        Phase PS-5, v1-minimal).
    detector_illustration:
        Show the Detector pixel schematic — a Qt-drawn, not-to-scale pixel labelled with its
        pitch (µm) and fill factor (Detector only, GUI plan Phase PS-3).
    spectral_inputs:
        Show the Spectral-Integration stage's editable inputs card — the filter bandpass edges
        (``filter_min_um`` / ``filter_max_um``) under a *Filter bandpass* heading and the
        acquisition ``integration_time_s`` under an *Acquisition* heading, as schema-driven
        :class:`FieldRow`s (Spectral Integration only, GUI plan Phase PS-4). The integration-time
        grouping is a presentation choice only (arch doc §4.4.1 GUI-grouping note); the schema is
        unchanged.
    mtf_panel:
        Embed the MTF per-term table + overlay (relocated from the MTF detail tab).
    noise_panel:
        Embed the noise per-term table + bars + click-to-explain (relocated from the
        Noise Budget detail tab).
    noise_panel_chart:
        Whether the embedded noise panel shows its bar chart (default ``True``). The Detector
        view sets it ``False`` so the noise **pie** (``result.plot.noise_pie``) is the primary
        chart and the panel contributes only the table + click-to-explain (GUI plan Phase PS-3).
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
    atmosphere_inputs: bool = False
    target_shape: bool = False
    optics_inputs: bool = False
    element_editor: bool = False
    detector_inputs: bool = False
    detector_illustration: bool = False
    spectral_inputs: bool = False
    platform_inputs: bool = False
    readout_inputs: bool = False
    mtf_panel: bool = False
    noise_panel: bool = False
    noise_panel_chart: bool = True
    outputs: bool = False
    metrics: bool = False
    plots: tuple[PlotSpec, ...] = field(default_factory=tuple)
    note: str | None = None
    subviews: tuple[StageSubView, ...] = field(default_factory=tuple)


# Deferred/minimal notes kept as named constants so they read once and stay honest.
_SOURCE_NOTE: Final[str] = (
    "Shown: pre-atmosphere target/background emission (primary) + at-aperture radiance "
    "(post-atmosphere). Pathways (mutually exclusive by engine design): thermal ε+T "
    "(Kirchhoff ρ=1−ε adds a daytime reflected-solar term — mixed emit+reflect); pure "
    "reflectance ρ alone (VIS/solar); declared scene type cross-checks the derived regime "
    "(warning on mismatch). All inputs shown ungated; per-scenario-type relevance is the "
    "Gap 85 fast-follow."
)
_PLATFORM_NOTE: Final[str] = (
    "Platform view is v1-minimal (owner-ratified: no dedicated MTF here — more detail is a "
    "post-v1 task). The smear and jitter MTF terms appear in the Optics and Performance MTF "
    "overlays. Platform/sensor attitude has no stage owner yet (ADR-0006 §4 / CU-122); the "
    "target RPY triad ships from source.target.*."
)
_SPECTRAL_NOTE: Final[str] = (
    "A per-wavelength noise spectrum is deferred (Gap 92); noise is scalar per term, "
    "computed post-integration (Rule 8) — see the Detector view for the noise budget."
)
_READOUT_NOTE: Final[str] = (
    "Readout view is v1-minimal (owner-ratified — more detail is a post-v1 task). The noise "
    "budget shown here (read noise + quantization live in this stage) is the same "
    "result.plot.noise_budget as the Detector view."
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
    # The Atmosphere stage instrument (GUI Capability Expansion plan GS-2, audit A-1…A-5):
    # the editable model-selector Inputs card (model enum + the active backend's knobs +
    # turbulence r₀ — the audit's "no atmosphere form at all" P0), the scalar outputs
    # readout, and the propagation story told as before/after: what the source emits
    # (pre-atmosphere), what the atmosphere does (τ & L_path — transmission loss vs the
    # path's own radiance, separately visible), and what reaches the aperture.
    "atmosphere": StageComposition(
        title="Atmosphere",
        atmosphere_inputs=True,
        outputs=True,
        plots=(
            PlotSpec("τ_atm & L_path vs wavelength", "spectral_atmosphere"),
            PlotSpec(
                "Before atmosphere — target & background emission",
                "spectral_source_emission",
            ),
            PlotSpec("After atmosphere — radiance at aperture", "spectral_source"),
        ),
    ),
    # The Optics stage instrument (GUI plan Phase PS-2, arch doc §4.4.1 Optics rows): the
    # first production use of the tabbed sub-view hook. Four tabs — editable optics Inputs +
    # the FINAL-regime outputs readout (Rule 10); the MTF per-term table + overlay (relocated
    # MTF tab) plus the MTF-at-Nyquist budget; the effective PSF beside the FP-2 complex-pupil
    # maps (apodization + wavefront-error, WAVES); and the FP-3 system throughput τ_opt(λ) with
    # the per-element coating R/T/ε spectra. Editing an input re-evaluates and every tab
    # refreshes (edit-and-watch: WFE → the pupil-phase map, aperture → MTF/PSF, τ_opt →
    # throughput).
    "optics": StageComposition(
        title="Optics",
        subviews=(
            StageSubView(title="Inputs", optics_inputs=True, outputs=True),
            # The Elements tab (GUI Capability Expansion plan GS-4, audit O-1): the
            # ADR-0009 D2 element-train editor — per-element R/T/temperature/geometry,
            # ε derived read-only (Rule 5), Apply = one Sensor.set_optical_elements call.
            StageSubView(title="Elements", element_editor=True),
            StageSubView(
                title="MTF",
                mtf_panel=True,
                plots=(PlotSpec("MTF-at-Nyquist budget", "mtf_budget"),),
            ),
            StageSubView(
                title="PSF + Pupil",
                plots=(
                    PlotSpec("Effective PSF", "psf"),
                    PlotSpec("Pupil apodization (amplitude / transmission)", "pupil_amplitude"),
                    PlotSpec("Pupil wavefront error (waves)", "pupil_phase"),
                ),
            ),
            StageSubView(
                title="Throughput",
                plots=(
                    PlotSpec("System optical throughput τ_opt(λ)", "optical_throughput"),
                    PlotSpec("Coating spectra — R / T / ε per element", "coating_spectra"),
                ),
            ),
        ),
    ),
    # The Platform stage instrument (GUI plan Phase PS-5, arch doc §4.4.1 Platform row):
    # v1-minimal (owner-ratified — no dedicated MTF). Editable jitter/smear inputs beside the
    # scalar outputs readout (jitter_sigma_x/y_m, smear_width_m, EE_box) + a themed v1-minimal
    # note (attitude ownership deferred, CU-122). Single flat pane.
    "platform": StageComposition(
        title="Platform",
        platform_inputs=True,
        outputs=True,
        note=_PLATFORM_NOTE,
    ),
    # The Spectral-Integration stage instrument (GUI plan Phase PS-4, arch doc §4.4.1
    # Spectral-Integration rows): the editable band + acquisition inputs (filter edges +
    # integration time, one sensor.set per edit — edit the band and the in-band spectrum
    # re-clips) beside the scalar electron budget, the in-band signal spectral radiance as the
    # primary plot, and the Gap-92 note (per-λ noise is scalar per term, computed once post-
    # integration per Rule 8 — the per-wavelength noise spectrum is deferred). Single flat pane.
    "spectral_integration": StageComposition(
        title="Spectral Integration",
        spectral_inputs=True,
        outputs=True,
        plots=(PlotSpec("In-band signal spectral radiance", "spectral_inband"),),
        note=_SPECTRAL_NOTE,
    ),
    # The Detector stage instrument (GUI plan Phase PS-3, arch doc §4.4.1 Detector rows): a
    # tabbed composite (the §4.4 sub-view hook, as Optics). Three tabs — editable detector
    # Inputs (QE / dark rate / pixel pitch x,y / fill factor / temperature) beside the scalar
    # outputs (signal_e, dark_e, …); the Noise budget as the ratified framework **pie**
    # (result.plot.noise_pie — slices ∝ variance, the primary chart) above the per-term table +
    # click-to-explain (the bar is suppressed, noise_panel_chart=False); and the Detector +
    # PSF tab — the Qt-drawn pixel illustration beside result.plot.psf_pixel_grid (the PSF with
    # the detector pixel grid overlaid). Editing a detector input re-evaluates and every tab
    # refreshes: the dark rate shifts the pie, the pixel pitch redraws the illustration + grid.
    "detector": StageComposition(
        title="Detector",
        subviews=(
            StageSubView(title="Inputs", detector_inputs=True, outputs=True),
            StageSubView(
                title="Noise",
                noise_panel=True,
                noise_panel_chart=False,
                plots=(PlotSpec("Noise budget — share of variance", "noise_pie"),),
            ),
            StageSubView(
                title="Detector + PSF",
                detector_illustration=True,
                plots=(PlotSpec("PSF with detector pixel grid", "psf_pixel_grid"),),
            ),
        ),
    ),
    # The Readout stage instrument (GUI plan Phase PS-5, arch doc §4.4.1 Readout row):
    # v1-minimal (owner-ratified). Editable read-noise/ADC/well inputs beside the scalar outputs
    # readout (signal_dn_final, sigma_total_e, total_well_e, well_fill_fraction, …) + the scalar
    # noise budget (read noise + quantization live in this stage — §4.7 relocates the Noise
    # Budget detail tab to the Detector/Readout views) + a themed v1-minimal note. Single flat pane.
    "readout": StageComposition(
        title="Readout",
        readout_inputs=True,
        outputs=True,
        plots=(PlotSpec("Noise budget", "noise_budget"),),
        note=_READOUT_NOTE,
    ),
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
