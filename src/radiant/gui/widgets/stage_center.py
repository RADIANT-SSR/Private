"""The contextual per-stage center: one composite view per selected stage (§4.4).

:class:`StageCenter` is the star of the contextual layout (arch doc §4.4): when a stage is
selected in the signal-chain strip, the center shows **only that stage's composite** —
its outputs readout, its plot(s), and any relocated detail content (the MTF per-term
table, the noise-budget table + explain, the geometry angle readout). This replaces the
old single-canvas swap: there is no shared canvas that every stage writes into; each stage
owns its center content. The composite for each stage is described, Qt-free, in
:mod:`radiant.gui.stage_views`; :class:`StagePane` assembles it from existing widgets.

Every figure is one call on the public ``result.plot.*`` surface (one GUI action ↔ one API
call, GUI plan §4.1); no plotting logic lives in GUI code. A ``result.plot`` accessor that
raises :class:`~radiant.api.errors.ApiValidationError` (a frame absent for this regime)
surfaces its actionable message in place of the figure, never a blank (Rules 15/17).

Pre-evaluate (no result) the center shows the themed "evaluate first" placeholder; a stage
click before the first result is remembered and rendered once the result lands (the
Phase-4A navigation behaviour, preserved). The Outputs readouts carry a pin affordance that
bubbles up as :attr:`pinOutputRequested` / :attr:`pinMetricRequested` so any stage output or
metric can join the right-rail Pinned panel (arch doc §4.5, CU-115 Step-B clause).

All colour/typography comes from the QSS theme via object names (GUI plan §4.9); this file
holds no colour or font literal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from radiant.api.errors import ApiValidationError
from radiant.api.inspect import ResultPlotNamespace
from radiant.api.plot import plot_theme
from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.param_format import field_display_text
from radiant.gui.stage_views import (
    DEFAULT_STAGE,
    PANEL_BESIDE,
    STAGE_COMPOSITIONS,
    PlotSpec,
    StageComposition,
    StageSubView,
    composition_for,
)
from radiant.gui.themes import Theme
from radiant.gui.viewer.viewer_widget import GeometryViewer
from radiant.gui.widgets.atmosphere_inputs_form import AtmosphereInputsForm
from radiant.gui.widgets.detector_illustration import DetectorIllustration
from radiant.gui.widgets.detector_inputs_form import DetectorInputsForm
from radiant.gui.widgets.field_row import FieldRow
from radiant.gui.widgets.geometry_angle_panel import (
    NOMINAL_SHAPE_DIMENSIONS,
    GeometryAnglePanel,
)
from radiant.gui.widgets.geometry_mode_form import GeometryModeForm
from radiant.gui.widgets.geometry_readout import GeometryReadout
from radiant.gui.widgets.matplotlib_canvas import MatplotlibCanvas
from radiant.gui.widgets.metric_group_cards import MetricGroupCards
from radiant.gui.widgets.mtf_panel import MtfPanel
from radiant.gui.widgets.noise_budget_panel import NoiseBudgetPanel
from radiant.gui.widgets.optical_element_editor import OpticalElementEditor
from radiant.gui.widgets.optics_inputs_form import OpticsInputsForm
from radiant.gui.widgets.outputs_readout import OutputsReadout
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog
from radiant.gui.widgets.performance_metrics_form import PerformanceMetricsForm
from radiant.gui.widgets.platform_inputs_form import PlatformInputsForm
from radiant.gui.widgets.plot_placeholder import PlotPlaceholder
from radiant.gui.widgets.readout_inputs_form import ReadoutInputsForm
from radiant.gui.widgets.scene_class_panel import SceneClassPanel
from radiant.gui.widgets.site_elevation_panel import SiteElevationPanel
from radiant.gui.widgets.source_inputs_form import SourceInputsForm
from radiant.gui.widgets.spectral_integration_inputs_form import SpectralIntegrationInputsForm

if TYPE_CHECKING:
    from radiant.api import ChainResult
    from radiant.api.sensor import Sensor
    from radiant.gui.config_scope import ConfigurationScope
    from radiant.gui.metric_matrix import ConfigurationColumns

# Minimum figure height so a composite with two plots stays readable in a scroll area.
_PLOT_MIN_HEIGHT: int = 240

# Ceiling on a plot canvas' height as a multiple of its own width (CU-241 defect 1).
#
# A matplotlib figure *does* track its canvas widget exactly — the Qt backend sets
# ``figure.set_size_inches(w/dpi, h/dpi)`` on every resize, so a 258x480 px card holds a
# 2.58x4.80 in figure. What does not track it is the **axes**: every card in this family
# draws an ``imshow`` map, whose aspect is locked square, so the axes side length is
# min(usable width, usable height). Handed a card 2.4x taller than it is wide, the axes
# takes the width — minus the y label, the colorbar and its ticks — and leaves the rest of
# the height empty. Measured on the Optics "PSF + Pupil" tab at 700x800 px: the PSF axes
# came out 0.221 x 0.091 of the figure, i.e. **2 % of the card's area**, which is the
# reported "square-ish figure at ~20 % of the card with dead space above and below".
#
# Capping the canvas height at its own width removes the dead space at the source: the
# card stops asking for height an aspect-locked axes cannot use, and the pane's scroll
# area gives that height to the next section instead. Ratio 1.0 (square-ish, floored at
# ``_PLOT_MIN_HEIGHT``) is the smallest defensible choice for maps; a square figure minus
# label/colorbar overhead still yields a landscape *axes*, so nothing is over-corrected.
_PLOT_MAX_HEIGHT_RATIO: float = 1.0

# Floor on the width of a single plot section inside a multi-plot block. Below roughly
# this width the y label, the tick labels and the colorbar leave the aspect-locked map
# nothing (see the 2 %-of-card measurement above): the Optics three-map row gave each
# figure 197 px in a 700 px pane. Sections keep this floor even when it makes the block
# wider than the pane — the enclosing scroll area then scrolls horizontally, which is
# strictly better than three unreadable maps. Distinct from ``_PLOT_MIN_WIDTH_PX`` below,
# which floors the whole plot *column* against an embedded panel beside it.
_PLOT_MIN_SECTION_WIDTH_PX: int = 320

# Gap between plot sections inside a multi-column plot block (layout geometry, not a
# theme token — the QSS owns colour and type, this owns only spacing between figures).
_PLOT_BLOCK_SPACING_PX: int = 8

# Floor on the width of a plot column when an embedded panel sits beside it
# (PANEL_BESIDE). A matplotlib figure squeezed below roughly this width cannot lay
# out its title, colorbar and axis labels without overlapping or clipping them —
# constrained_layout has nowhere left to go. The Detector "Detector + PSF" tab hit
# exactly that: the pixel illustration took half the pane and both figures were
# crushed into a ~250 px column with a clipped title and an overstruck colorbar
# (CU-241, third instance). The splitter stays user-draggable; this only stops the
# *initial* division from starving the figures.
_PLOT_MIN_WIDTH_PX: int = 420

# The shape-dimension parameters the geometry side panel edits (bounds/units from the
# schema; this list is the read/sync surface — the panel owns the shape→subset matrix).
_SHAPE_DIMENSION_PATHS: tuple[str, ...] = (
    "geometry.target.shape_radius_m",
    "geometry.target.shape_length_m",
    "geometry.target.shape_width_m",
    "geometry.target.shape_height_m",
    "geometry.target.shape_base_radius_m",
)


class _PlotSection(QWidget):
    """A titled plot region: a header over a guarded ``result.plot.*`` figure."""

    def __init__(self, spec: PlotSpec, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._spec = spec
        self._dark = False
        self._result: ChainResult | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel(spec.title, self)
        title.setObjectName("stagePlotTitle")
        layout.addWidget(title)

        self._canvas = MatplotlibCanvas(self)
        self._canvas.setMinimumHeight(_PLOT_MIN_HEIGHT)
        self._canvas.setMinimumWidth(_PLOT_MIN_SECTION_WIDTH_PX)
        self._message = QLabel("", self)
        self._message.setObjectName("stagePlotMessage")
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)
        self._message.setVisible(False)
        layout.addWidget(self._canvas, 1)
        layout.addWidget(self._message)

    @property
    def canvas(self) -> MatplotlibCanvas:
        """The embedded figure canvas (populated on the next result)."""
        return self._canvas

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt override
        """Re-apply the width-driven height ceiling whenever the card resizes (CU-241).

        The figure follows its canvas widget automatically (the Qt backend resizes it),
        so the only thing this scaffold has to decide is **how much height a plot card
        should accept**. An aspect-locked map cannot use height beyond its own width, so
        the ceiling tracks the width on every resize rather than being fixed once at
        construction: a user widening the window or dragging the ``beside`` splitter gets
        a proportionally taller figure, and narrowing it reclaims the dead space instead
        of stranding it above and below the map.
        """
        super().resizeEvent(event)
        self._apply_height_ceiling()

    def _apply_height_ceiling(self) -> None:
        """Cap the canvas height at ``_PLOT_MAX_HEIGHT_RATIO`` x its own width."""
        width = self._canvas.width()
        ceiling = max(_PLOT_MIN_HEIGHT, int(round(width * _PLOT_MAX_HEIGHT_RATIO)))
        self._canvas.setMaximumHeight(ceiling)

    def render(self, result: ChainResult) -> None:
        """Draw the section's ``result.plot.*`` figure, or its actionable message."""
        self._result = result
        try:
            with plot_theme(dark=self._dark):
                figure = getattr(ResultPlotNamespace(result), self._spec.method)()
        except ApiValidationError as exc:
            # A frame absent for this regime — show the actionable text, never a blank.
            self._message.setText(str(exc))
            self._message.setVisible(True)
            self._canvas.setVisible(False)
            return
        self._message.setVisible(False)
        self._canvas.setVisible(True)
        self._canvas.show_figure(figure)

    def set_dark(self, dark: bool) -> None:
        """Adopt the dark/light plot theme; re-render the figure if one is shown (CU-139).

        The GUI matplotlib figures now follow the app theme through the public
        ``radiant.api.plot.plot_theme`` seam. Re-render only when a result is already
        drawn (via the normal close-and-re-embed path); an unpopulated section just
        remembers the flag for its next :meth:`render`.
        """
        if dark == self._dark:
            return
        self._dark = dark
        if self._result is not None:
            self.render(self._result)


class StagePane(QWidget):
    """One stage's contextual composite, assembled from a :class:`StageComposition`.

    With no declared sub-views (every v1 stage), the composite is a **single scroll
    pane**: its sections stack top-to-bottom exactly as before. When the composition
    declares **two or more** :class:`StageSubView` tabs (the deferred multi-tab hook, arch
    doc §4.4), the pane instead renders a ``QTabWidget`` with one scoped composite per
    tab; the single-pane accessors below then reflect the union across tabs (first-of-kind
    for the singular ones), and :meth:`populate` fills every tab. The seam is data-driven:
    a later phase turns a stage tabbed by populating ``subviews``, no widget rewrite.

    Parameters
    ----------
    namespace:
        The chain namespace this pane represents (``"optics"``, ``"detector"``, …).
    composition:
        The Qt-free spec of the sections this pane shows.
    parent:
        The owning widget, if any.

    Signals
    -------
    pinOutputRequested(str, str, str, str):
        Re-emitted from an Outputs row's pin — ``(stage, key, label, unit)``.
    pinMetricRequested(str, str):
        Re-emitted from a metric row's pin — ``(metric_key, label)``.
    """

    pinOutputRequested = Signal(str, str, str, str)
    pinMetricRequested = Signal(str, str)
    parameterEdited = Signal(str)
    # A compound edit: several dot-paths changed by one user action that must undo as a
    # single step (CU-141 — a shape pick plus the dimensions seeded alongside it). The
    # payload is the list of affected dot-paths, primary first.
    compoundParameterEdited = Signal(list)

    def __init__(
        self,
        namespace: str,
        composition: StageComposition,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("stagePane")
        self._namespace = namespace
        self._composition = composition

        scroll = QScrollArea(self)
        scroll.setObjectName("stagePaneScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        body = QWidget(scroll)
        body.setObjectName("stagePaneBody")
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(14, 12, 14, 14)
        self._body_layout.setSpacing(12)
        scroll.setWidget(body)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll)

        # Section widgets. Kept as lists so a tabbed composite (multiple tabs, each with
        # its own sections) and a flat composite (one of each at most) share one populate
        # path; the singular accessors return the first of a kind.
        # The session's configuration scope (Phase 4b): handed to every FieldRow so a
        # configured parameter shows its red "C" wherever it is edited.
        self._config_scope: ConfigurationScope | None = None
        # The Geometry Inputs tab's scene-class steering card (Geometry-Flexibility
        # Phase 4): derived-class chip + the optional geometry.scene_class assertion +
        # the metrics that class turns off by default. Bound/refreshed with the geometry
        # forms and populated from each result's geometry stage outputs.
        self._scene_class_panels: list[SceneClassPanel] = []
        self._geometry_forms: list[GeometryModeForm] = []
        # The one ``non_mode`` geometry scene fact (CU-301): site elevation is not a door
        # onto any canonical viewing quantity, so the manifest-driven mode forms cannot
        # render it and it gets its own card, on the scene-class card's precedent.
        self._site_elevation_panels: list[SiteElevationPanel] = []
        self._geometry_readouts: list[GeometryReadout] = []
        self._geometry_viewers: list[GeometryViewer] = []
        self._geometry_panels: list[GeometryAnglePanel] = []
        # Source-instrument sections (GUI plan Phase PS-1): the radiometric Inputs forms
        # (one per GT-0 tab). Target extent/shape/orientation is geometry content — its
        # editor mounts only on Geometry → Schematic (GT-0 / Windows finding 14).
        self._source_forms: list[SourceInputsForm] = []
        # The Optics-instrument Inputs form (GUI plan Phase PS-2): edit an optics param and
        # every diagnostic tab refreshes (edit-and-watch). Bound/refreshed like the source form.
        self._optics_forms: list[OpticsInputsForm] = []
        # The Optics element-train editor (GS-4): Apply commits the declarative document
        # (one set_optical_elements call) and relays through the parameterEdited pipeline.
        self._element_editors: list[OpticalElementEditor] = []
        # The Detector-instrument Inputs form + pixel illustration (GUI plan Phase PS-3): edit a
        # detector param and every tab refreshes — the dark rate shifts the noise pie, the pixel
        # pitch redraws the illustration + PSF grid. The illustration is drawn from the live
        # sensor's pixel geometry (populated each result, edit-and-watch).
        self._detector_forms: list[DetectorInputsForm] = []
        self._detector_illustrations: list[DetectorIllustration] = []
        # The Spectral-Integration-instrument Inputs form (GUI plan Phase PS-4): edit the band
        # or the integration time and every dependent view refreshes — editing the filter edges
        # re-clips the in-band spectrum, editing the integration time scales the electron budget.
        # Bound/refreshed like the source/optics/detector forms.
        self._spectral_forms: list[SpectralIntegrationInputsForm] = []
        # The Platform + Readout instrument Inputs forms (GUI plan Phase PS-5, v1-minimal): edit
        # a jitter/smear or read-noise/ADC/well param and the Outputs readout (+ the Readout noise
        # budget) refresh. Bound/refreshed like the source/optics/detector/spectral forms.
        self._platform_forms: list[PlatformInputsForm] = []
        self._readout_forms: list[ReadoutInputsForm] = []
        # The Atmosphere-instrument Inputs form (GUI Capability Expansion plan GS-2): the
        # model selector + the active backend's knobs. Edit the model (or a knob) and the
        # τ/L_path + before/after-aperture plots refresh (edit-and-watch).
        self._atmosphere_forms: list[AtmosphereInputsForm] = []
        self._sensor: Sensor | None = None
        # The shared session display-unit store (bound in). The panel's field values are
        # formatted through it so a unit chosen on any surface reflects on all.
        self._display_units: dict[str, str] = {}
        self._last_result: ChainResult | None = None
        self._outputs_list: list[OutputsReadout] = []
        # The Performance instrument's metric surface (owner redesign 2026-07-25):
        # the grouped metric cards.
        self._metrics_list: list[MetricGroupCards] = []
        # The Performance metric-group selection row (Gap 96): checkboxes for the five
        # performance.metrics.* group flags, ordered to match the card sections. A toggle
        # is one sensor.set + parameterEdited, so the host re-evaluates and every metric
        # surface re-renders with the reduced set.
        self._metric_selection_forms: list[PerformanceMetricsForm] = []
        self._mtf_panels: list[MtfPanel] = []
        self._noise_panels: list[NoiseBudgetPanel] = []
        self._plot_sections: list[_PlotSection] = []
        self._tabs: QTabWidget | None = None

        # Pane title (the stage heading), above either the flat sections or the tabs.
        self._title = QLabel(composition.title, body)
        self._title.setObjectName("stageCenterTitle")
        self._body_layout.addWidget(self._title)

        if len(composition.subviews) > 1:
            # Tabbed composite (deferred hook): one scoped composite per named sub-view.
            self._tabs = QTabWidget(body)
            self._tabs.setObjectName("stageSubViewTabs")
            for subview in composition.subviews:
                tab = QWidget(self._tabs)
                tab_layout = QVBoxLayout(tab)
                tab_layout.setContentsMargins(0, 8, 0, 0)
                tab_layout.setSpacing(12)
                fills = self._build_sections(subview, tab_layout, tab)
                if not fills:
                    tab_layout.addStretch(1)
                # "&" is a Qt mnemonic marker in tab titles ("Scene & regime" rendered as
                # "Scene _regime", visual QA 2026-07-17) — escape it for display.
                self._tabs.addTab(
                    self._wrap_subview(subview, tab), subview.title.replace("&", "&&")
                )
            self._body_layout.addWidget(self._tabs, 1)
        else:
            # Single flat pane (every v1 stage): sections stack in the body directly.
            fills = self._build_sections(composition, self._body_layout, body)
            if not fills:
                self._body_layout.addStretch(1)

    def _wrap_subview(self, spec: StageSubView, tab: QWidget) -> QWidget:
        """Give a tall sub-view its own scroll; let a canvas sub-view fill the tab viewport.

        A ``QTabWidget``'s stacked pages share one height (the tallest page's minimum). The
        Geometry "Inputs" tab (form + full-height derived-angles readout) is tall, so without
        its own scroll it inflated the shared stack and *ballooned* the sibling "Schematic"
        canvas taller than the viewport — the scene then rendered bottom-anchored with empty
        space above (owner report 2026-07-14). Wrapping every non-canvas sub-view in its own
        ``QScrollArea`` bounds its contributed height (one full-height scrollbar spans the
        whole form + table, as the owner asked), while the canvas sub-view is returned bare so
        it fills the tab viewport with no scrollbar.
        """
        if spec.geometry_viewer:
            return tab
        scroll = QScrollArea()
        scroll.setObjectName("stageSubViewScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(tab)
        return scroll

    def _build_sections(
        self,
        spec: StageComposition | StageSubView,
        layout: QVBoxLayout,
        parent: QWidget,
    ) -> bool:
        """Build *spec*'s sections into *layout* (shared by the flat pane and each tab).

        Only the sections *spec* asks for are built; created widgets are appended to the
        per-kind lists so :meth:`populate` fills them uniformly.

        Returns ``True`` when a section that *fills* the vertical slack was added (the
        geometry readout — which owns its own inner scrollbar — or the 3D-view split). The
        caller then omits its trailing ``addStretch`` so the filling section absorbs the
        remaining height and its scrollbar spans the whole pane, rather than sharing the
        slack with an empty stretch (owner report 2026-07-14: the derived-angles scrollbar
        was short because a trailing stretch ate the space the readout should have filled).
        """
        fills = False
        if spec.source_inputs:
            # The Source instrument's radiometric Inputs card (arch doc §4.4.1 Source).
            # No shape editor here: target extent/orientation is geometry content and is
            # edited on Geometry → Schematic only (GT-0 / Windows finding 14).
            source_form = SourceInputsForm(parent, groups=spec.source_groups or None)
            source_form.parameterEdited.connect(self.parameterEdited)
            layout.addWidget(source_form)
            self._source_forms.append(source_form)
        if spec.atmosphere_inputs:
            # The Atmosphere instrument's editable inputs card (GS-2): one sensor.set per
            # edit; each accepted edit re-emits parameterEdited so the host re-evaluates and
            # the τ_atm/L_path + before/after radiance plots refresh (edit-and-watch).
            atmosphere_form = AtmosphereInputsForm(parent)
            atmosphere_form.parameterEdited.connect(self.parameterEdited)
            # Choosing a bundled library family can write both the axes and the run-matrix
            # directory (CU-239), which must reverse as one undo step.
            atmosphere_form.compoundParameterEdited.connect(self.compoundParameterEdited)
            layout.addWidget(atmosphere_form)
            self._atmosphere_forms.append(atmosphere_form)
        if spec.optics_inputs:
            # The Optics instrument's editable inputs card (GUI plan Phase PS-2): one
            # sensor.set per edit, and each accepted edit re-emits parameterEdited so the host
            # re-evaluates and every Optics tab (MTF / PSF + Pupil / Throughput) refreshes.
            optics_form = OpticsInputsForm(parent)
            optics_form.parameterEdited.connect(self.parameterEdited)
            layout.addWidget(optics_form)
            self._optics_forms.append(optics_form)
        if spec.element_editor:
            # The Optics Elements tab (GS-4): the ADR-0009 element-document editor. A
            # successful Apply emits the pseudo-path through the standard edit pipeline
            # (stale dots + debounced re-evaluate); an invalid document never commits.
            element_editor = OpticalElementEditor(parent)
            element_editor.elementsApplied.connect(self.parameterEdited)
            layout.addWidget(element_editor)
            self._element_editors.append(element_editor)
        if spec.detector_inputs:
            # The Detector instrument's editable inputs card (GUI plan Phase PS-3): one
            # sensor.set per edit; each accepted edit re-emits parameterEdited so the host
            # re-evaluates and every Detector tab (Noise pie, illustration, PSF grid) refreshes.
            detector_form = DetectorInputsForm(parent)
            detector_form.parameterEdited.connect(self.parameterEdited)
            layout.addWidget(detector_form)
            self._detector_forms.append(detector_form)
        if spec.spectral_inputs:
            # The Spectral-Integration instrument's editable inputs card (GUI plan Phase PS-4):
            # one sensor.set per edit; each accepted edit re-emits parameterEdited so the host
            # re-evaluates and the in-band spectrum + the Outputs electron budget refresh.
            spectral_form = SpectralIntegrationInputsForm(parent)
            spectral_form.parameterEdited.connect(self.parameterEdited)
            layout.addWidget(spectral_form)
            self._spectral_forms.append(spectral_form)
        if spec.platform_inputs:
            # The Platform instrument's editable inputs card (GUI plan Phase PS-5, v1-minimal):
            # one sensor.set per edit; each accepted edit re-emits parameterEdited so the host
            # re-evaluates and the Outputs readout refreshes (edit-and-watch).
            platform_form = PlatformInputsForm(parent)
            platform_form.parameterEdited.connect(self.parameterEdited)
            layout.addWidget(platform_form)
            self._platform_forms.append(platform_form)
        if spec.readout_inputs:
            # The Readout instrument's editable inputs card (GUI plan Phase PS-5, v1-minimal):
            # one sensor.set per edit; each accepted edit re-emits parameterEdited so the host
            # re-evaluates and the Outputs readout + the noise budget refresh (edit-and-watch).
            readout_form = ReadoutInputsForm(parent)
            readout_form.parameterEdited.connect(self.parameterEdited)
            layout.addWidget(readout_form)
            self._readout_forms.append(readout_form)
        # The detector pixel illustration participates in ``panel_placement`` like
        # the MTF/noise panels, so it can sit *beside* the kernel that pixel
        # imposes on the PSF (owner walkthrough item 19) rather than above it.
        deferred_illustration: DetectorIllustration | None = None
        if spec.detector_illustration:
            deferred_illustration = DetectorIllustration(parent)
            self._detector_illustrations.append(deferred_illustration)
        if spec.outputs:
            outputs = OutputsReadout(parent)
            outputs.pinOutputRequested.connect(self.pinOutputRequested)
            self._add_section(layout, "Outputs", outputs)
            self._outputs_list.append(outputs)
        if spec.metric_selection:
            # Gap 96: the compact "Compute:" toggle row sits directly above the grouped
            # metric cards, checkbox order matching the card sections (owner 2026-07-25);
            # each toggle re-emits parameterEdited → re-evaluate. Self-labelling — no
            # section header.
            metric_form = PerformanceMetricsForm(parent)
            metric_form.parameterEdited.connect(self.parameterEdited)
            layout.addWidget(metric_form)
            self._metric_selection_forms.append(metric_form)
        if spec.metrics:
            # The grouped metric cards (human labels, values with units, hover pins). The
            # "All metrics" tab label provides the context — no section header.
            metrics = MetricGroupCards(parent)
            metrics.pinMetricRequested.connect(self.pinMetricRequested)
            layout.addWidget(metrics)
            self._metrics_list.append(metrics)
        if spec.scene_class_panel:
            # Above the mode forms by design: the scene class is the mission-type entry
            # point, and the operator reads (or asserts) it before typing angles. One
            # sensor.set per accepted assertion edit, relayed through the standard
            # parameterEdited pipeline so results go stale and a re-evaluate is scheduled.
            scene_class_panel = SceneClassPanel(parent)
            scene_class_panel.parameterEdited.connect(self.parameterEdited)
            layout.addWidget(scene_class_panel)
            self._scene_class_panels.append(scene_class_panel)
        if spec.geometry_form:
            geometry_form = GeometryModeForm(parent)
            geometry_form.parameterEdited.connect(self.parameterEdited)
            layout.addWidget(geometry_form)
            self._geometry_forms.append(geometry_form)
        if spec.site_elevation_panel:
            # Below the mode forms: the doors are typed first, then the standalone scene
            # fact. One sensor.set per accepted edit, relayed through the standard
            # parameterEdited pipeline so results go stale and a re-evaluate is scheduled.
            site_elevation_panel = SiteElevationPanel(parent)
            site_elevation_panel.parameterEdited.connect(self.parameterEdited)
            layout.addWidget(site_elevation_panel)
            self._site_elevation_panels.append(site_elevation_panel)
        if spec.geometry_readout:
            # No inner scroll here: the readout sizes to its full content and the pane's
            # outer scroll owns scrolling, so one full-height scrollbar spans the whole
            # form + derived table instead of clipping the table to a short inner sliver.
            geometry_readout = GeometryReadout(parent, scrollable=False)
            layout.addWidget(geometry_readout, 1)
            self._geometry_readouts.append(geometry_readout)
            fills = True
        if spec.geometry_viewer:
            # The Schematic tab is a split: the viewport (left, stretches) and the accordion
            # side panel of angle-annotation toggles + shared readout + shape/RPY editor
            # (right). The panel emits intent; this pane performs the one sensor.set (§4.1).
            split = QSplitter(Qt.Orientation.Horizontal, parent)
            split.setObjectName("geometryViewerSplit")
            geometry_viewer = GeometryViewer(split)
            geometry_panel = GeometryAnglePanel(split)
            # The angle-arc reveal toggles now live on the plot as a bottom-left overlay
            # (owner feedback 2026-07-14); the GeometryViewer wires that overlay directly to
            # its own set_angle_revealed, so this pane no longer routes angle reveals.
            geometry_panel.triadToggled.connect(self._on_triad_toggled)
            geometry_panel.shapeRequested.connect(self._on_shape_requested)
            geometry_panel.editRequested.connect(self._on_panel_edit_requested)
            # The panel embeds an editable GeometryModeForm (owner request 2026-07-14): geometry
            # is settable from the Schematic tab. It is registered as a geometry form so the
            # shared bind_sensor / refresh path binds and syncs it exactly like the Inputs-tab
            # form; its parameterEdited re-emits so an edit re-evaluates and re-renders the scene.
            schematic_form = geometry_panel.geometry_form
            schematic_form.parameterEdited.connect(self.parameterEdited)
            self._geometry_forms.append(schematic_form)
            split.addWidget(geometry_viewer)
            split.addWidget(geometry_panel)
            split.setStretchFactor(0, 3)
            split.setStretchFactor(1, 1)
            layout.addWidget(split, 1)
            self._geometry_viewers.append(geometry_viewer)
            self._geometry_panels.append(geometry_panel)
            fills = True
        # The embedded panel and the plot sections are placed together, because
        # ``panel_placement`` decides their relative arrangement (stage_views:
        # before / after / beside). Build the panel first, then hand both to the
        # placement helper — nothing below branches on the placement again.
        panel: QWidget | None = None
        panel_header = ""
        if deferred_illustration is not None:
            panel, panel_header = deferred_illustration, "Detector pixel"
        if spec.mtf_panel:
            mtf_panel = MtfPanel(parent)
            self._mtf_panels.append(mtf_panel)
            panel, panel_header = mtf_panel, "MTF budget"
        if spec.noise_panel:
            # The Detector view suppresses the embedded bar (noise_panel_chart=False) so the
            # framework noise **pie** is the primary chart (drawn as a plot section) and the
            # panel contributes only the table + click-to-explain (GUI plan Phase PS-3).
            noise_panel = NoiseBudgetPanel(parent, show_chart=spec.noise_panel_chart)
            self._noise_panels.append(noise_panel)
            panel, panel_header = noise_panel, "Noise budget"
        self._place_panel_and_plots(layout, parent, spec, panel, panel_header)
        if spec.note is not None:
            note = QLabel(spec.note, parent)
            note.setObjectName("stageNote")
            note.setWordWrap(True)
            layout.addWidget(note)
        return fills

    def _place_panel_and_plots(
        self,
        layout: QVBoxLayout,
        parent: QWidget,
        spec: StageComposition | StageSubView,
        panel: QWidget | None,
        panel_header: str,
    ) -> None:
        """Lay out the embedded *panel* and the spec's plot sections per its arrangement.

        Honours the two declarative arrangement fields (``stage_views``):

        * ``panel_placement`` — ``before`` (panel above the plots, the original v1
          order) or ``beside`` (a horizontal splitter, plots left and panel right).
        * ``plot_columns`` — how many plot sections share a row; they fill
          left-to-right and wrap.

        A spec with no panel behaves exactly as before, so the arrangement fields
        cost nothing for the stages that do not set them.
        """
        plots_host = self._build_plot_block(parent, spec)

        if panel is None:
            if plots_host is not None:
                layout.addWidget(plots_host)
            return

        if spec.panel_placement == PANEL_BESIDE and plots_host is not None:
            # Chart left, table right, user-draggable. Stretch favours the chart:
            # the table needs enough width to show its terms, not half the pane.
            split = QSplitter(Qt.Orientation.Horizontal, parent)
            split.setObjectName("stagePanelSplit")
            plots_host.setMinimumWidth(_PLOT_MIN_WIDTH_PX)
            split.addWidget(plots_host)
            split.addWidget(panel)
            split.setStretchFactor(0, 3)
            split.setStretchFactor(1, 2)
            # The figures are the point of the tab; the panel annotates them. Neither
            # may be collapsed to nothing by a stray drag, and the panel's own size
            # hint must not push the figures below the readable floor (CU-241).
            split.setCollapsible(0, False)
            split.setCollapsible(1, False)
            layout.addWidget(split)
            return

        # PANEL_BEFORE (and the beside-with-no-plots degenerate case).
        self._add_section(layout, panel_header, panel)
        if plots_host is not None:
            layout.addWidget(plots_host)

    def _build_plot_block(
        self,
        parent: QWidget,
        spec: StageComposition | StageSubView,
    ) -> QWidget | None:
        """Build the spec's plot sections into one container, or ``None`` if it has none.

        With ``plot_columns == 1`` the container is a plain vertical stack — the
        same visual result as adding each section straight to the pane. Above 1 the
        sections are packed into equal-width rows so related maps read side by side.
        """
        if not spec.plots:
            return None
        host = QWidget(parent)
        host.setObjectName("stagePlotBlock")
        columns = max(1, spec.plot_columns)
        outer = QVBoxLayout(host)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(_PLOT_BLOCK_SPACING_PX)

        row: QHBoxLayout | None = None
        for index, plot_spec in enumerate(spec.plots):
            section = _PlotSection(plot_spec, host)
            self._plot_sections.append(section)
            if columns == 1:
                outer.addWidget(section)
                continue
            if index % columns == 0:
                row_host = QWidget(host)
                row = QHBoxLayout(row_host)
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(_PLOT_BLOCK_SPACING_PX)
                outer.addWidget(row_host)
            assert row is not None  # set on every index % columns == 0 above
            # Equal stretch so a row of maps divides the width evenly rather than
            # sizing to whichever figure happens to render widest.
            row.addWidget(section, 1)
        return host

    def _add_section(self, layout: QVBoxLayout, header: str, widget: QWidget) -> None:
        """Add a titled section (a header label over *widget*) to *layout*."""
        label = QLabel(header, widget.parentWidget())
        label.setObjectName("stageSectionHeader")
        layout.addWidget(label)
        layout.addWidget(widget)

    # -- accessors (tests) --------------------------------------------------

    @property
    def namespace(self) -> str:
        """The chain namespace this pane represents."""
        return self._namespace

    @property
    def has_tabs(self) -> bool:
        """True when this stage renders its sub-views as a ``QTabWidget`` (the hook)."""
        return self._tabs is not None

    def tab_titles(self) -> list[str]:
        """The tab labels, in order (empty when the pane is a single flat composite)."""
        if self._tabs is None:
            return []
        return [self._tabs.tabText(i) for i in range(self._tabs.count())]

    @property
    def scene_class_panel(self) -> SceneClassPanel | None:
        """The scene-class steering card, if this stage has one (Geometry 'Inputs')."""
        return self._scene_class_panels[0] if self._scene_class_panels else None

    @property
    def geometry_form(self) -> GeometryModeForm | None:
        """The stage-0 input-mode forms, if this stage has them (Geometry)."""
        return self._geometry_forms[0] if self._geometry_forms else None

    @property
    def site_elevation_panel(self) -> SiteElevationPanel | None:
        """The site-elevation card, if this stage has one (Geometry 'Inputs', CU-301)."""
        return self._site_elevation_panels[0] if self._site_elevation_panels else None

    @property
    def geometry_readout(self) -> GeometryReadout | None:
        """The geometry angle readout, if this stage has one."""
        return self._geometry_readouts[0] if self._geometry_readouts else None

    @property
    def geometry_viewer(self) -> GeometryViewer | None:
        """The embedded geometry schematic viewer, if this stage has one (Geometry 'Schematic')."""
        return self._geometry_viewers[0] if self._geometry_viewers else None

    @property
    def geometry_panel(self) -> GeometryAnglePanel | None:
        """The 3D-viewer accordion side panel, if this stage has one (Part B)."""
        return self._geometry_panels[0] if self._geometry_panels else None

    @property
    def source_inputs_form(self) -> SourceInputsForm | None:
        """The Source radiometric Inputs form, if this stage has one (Source, PS-1)."""
        return self._source_forms[0] if self._source_forms else None

    @property
    def optics_inputs_form(self) -> OpticsInputsForm | None:
        """The Optics editable-inputs form, if this stage has one (Optics, PS-2)."""
        return self._optics_forms[0] if self._optics_forms else None

    @property
    def metric_selection_form(self) -> PerformanceMetricsForm | None:
        """The Performance metric-group selection card, if this stage has one (Gap 96)."""
        return self._metric_selection_forms[0] if self._metric_selection_forms else None

    @property
    def detector_inputs_form(self) -> DetectorInputsForm | None:
        """The Detector editable-inputs form, if this stage has one (Detector, PS-3)."""
        return self._detector_forms[0] if self._detector_forms else None

    @property
    def detector_illustration(self) -> DetectorIllustration | None:
        """The Detector pixel schematic, if this stage has one (Detector, PS-3)."""
        return self._detector_illustrations[0] if self._detector_illustrations else None

    @property
    def spectral_inputs_form(self) -> SpectralIntegrationInputsForm | None:
        """The Spectral-Integration editable-inputs form, if this stage has one (PS-4)."""
        return self._spectral_forms[0] if self._spectral_forms else None

    @property
    def platform_inputs_form(self) -> PlatformInputsForm | None:
        """The Platform editable-inputs form, if this stage has one (Platform, PS-5)."""
        return self._platform_forms[0] if self._platform_forms else None

    @property
    def readout_inputs_form(self) -> ReadoutInputsForm | None:
        """The Readout editable-inputs form, if this stage has one (Readout, PS-5)."""
        return self._readout_forms[0] if self._readout_forms else None

    @property
    def atmosphere_inputs_form(self) -> AtmosphereInputsForm | None:
        """The Atmosphere editable-inputs form, if this stage has one (GS-2)."""
        return self._atmosphere_forms[0] if self._atmosphere_forms else None

    @property
    def element_editor(self) -> OpticalElementEditor | None:
        """The Optics element-train editor, if this stage has one (GS-4)."""
        return self._element_editors[0] if self._element_editors else None

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor* + shared display-unit store into any input form.

        The sensor is also retained so the 3D geometry viewer can read the target-shape /
        optics / detector parameters the geometry stage does not emit (ADR-0007 §2), and
        the accordion side panel is configured from the schema (shape choices — never a
        hardcoded list, Gap 70). The shared *display_units* store is retained so the panel's
        dimension/RPY field values format in the same chosen units as every other surface.
        """
        self._sensor = sensor
        self._display_units = display_units
        # The last result belongs to the previously-bound sensor; drop it so a shape/RPY
        # preview (or any re-render) never resolves the new live sensor against a stale
        # result (blank-config crash, see StageCenter.bind_sensor).
        self._last_result = None
        for scene_class_panel in self._scene_class_panels:
            scene_class_panel.bind_sensor(sensor, display_units)
        for site_elevation_panel in self._site_elevation_panels:
            site_elevation_panel.bind_sensor(sensor, display_units)
        for form in self._geometry_forms:
            form.bind_sensor(sensor, display_units)
        for source_form in self._source_forms:
            source_form.bind_sensor(sensor, display_units)
        for optics_form in self._optics_forms:
            optics_form.bind_sensor(sensor, display_units)
        for detector_form in self._detector_forms:
            detector_form.bind_sensor(sensor, display_units)
        for spectral_form in self._spectral_forms:
            spectral_form.bind_sensor(sensor, display_units)
        for platform_form in self._platform_forms:
            platform_form.bind_sensor(sensor, display_units)
        for readout_form in self._readout_forms:
            readout_form.bind_sensor(sensor, display_units)
        for atmosphere_form in self._atmosphere_forms:
            atmosphere_form.bind_sensor(sensor, display_units)
        for element_editor in self._element_editors:
            element_editor.bind_sensor(sensor, display_units)
        for metric_form in self._metric_selection_forms:
            metric_form.bind_sensor(sensor, display_units)
        if sensor is not None and self._geometry_panels:
            self._configure_panels_from_schema(sensor)

    def bind_configuration_scope(self, scope: ConfigurationScope | None) -> None:
        """Give every input-form field the session's configuration scope (Phase 4b).

        Every per-stage form field is the one shared
        :class:`~radiant.gui.widgets.field_row.FieldRow`, so the red "C" badge and the
        scope context menu reach all nine stages by handing the scope to each row —
        found by widget-tree walk rather than by nine per-form fan-out methods that
        would silently miss any field a future form adds. The rows are built with their
        panes, so a walk at bind time sees all of them; each row then re-reads itself
        from the scope's ``changed`` signal.

        The Optics **Elements** tab takes the same scope by name (Gap 103 v1.1). It is
        not a ``FieldRow``, and what it needs from the scope is the study document
        itself — which configuration is active and what that configuration overrides —
        so it can render that configuration's effective element train and route its
        Apply to the shared document or to the configuration's overrides.
        """
        self._config_scope = scope
        for row in self.findChildren(FieldRow):
            row.set_configuration_scope(scope)
        for element_editor in self._element_editors:
            element_editor.set_configuration_scope(scope)

    def set_theme(self, theme: Theme) -> None:
        """Re-theme this pane's custom-painted widgets + matplotlib figures (theme toggle).

        The ``QPainter`` widgets that read design tokens from a stored
        :class:`~radiant.gui.themes.tokens.Theme` (the geometry schematic viewer and the
        detector pixel illustration) are told directly. The ``result.plot.*`` matplotlib
        figures now follow the app theme too (CU-139): each plot section adopts the dark
        or light chrome via the public ``radiant.api.plot.plot_theme`` seam and re-renders
        if already drawn. Every QSS-styled widget re-styles automatically when the app
        stylesheet is re-applied.
        """
        for viewer in self._geometry_viewers:
            viewer.set_theme(theme)
        for illustration in self._detector_illustrations:
            illustration.set_theme(theme)
        dark = theme.name == "dark"
        for section in self._plot_sections:
            section.set_dark(dark)
        for element_editor in self._element_editors:
            element_editor.set_dark(dark)

    def refresh_geometry_forms(self) -> None:
        """Re-read every geometry input form from the bound sensor (Inputs + Schematic tabs).

        Both the Inputs-tab form and the Schematic-tab form read the one live sensor, so a
        value edited on either surface (or in the parameter tree) is reflected on both after
        the next clean evaluation, keeping the two tabs in sync. The scene-class card's
        assertion field and the site-elevation card re-read on the same beat — a value set
        in the parameter tree shows on the Geometry screen immediately, exactly like a mode
        field (CU-121, CU-301).
        """
        for scene_class_panel in self._scene_class_panels:
            scene_class_panel.refresh()
        for site_elevation_panel in self._site_elevation_panels:
            site_elevation_panel.refresh()
        for form in self._geometry_forms:
            form.refresh()

    def _configure_panels_from_schema(self, sensor: Sensor) -> None:
        """Populate each side panel's shape choices from the live schema (Gap 70).

        Dimension/RPY bounds are no longer pushed to the panel: those fields now open the
        shared :class:`ParameterEditorDialog`, which enforces the schema bounds (and units)
        itself on a throwaway clone before the one ``sensor.set`` — the same reject path as
        every other schema field, so the panel needs no bounds of its own.
        """
        defs = sensor.parameter_defs()
        shape_def = defs.get("geometry.target.shape")
        choices = tuple(shape_def.enum_values) if shape_def and shape_def.enum_values else ()
        if not choices:
            return
        for panel in self._geometry_panels:
            panel.set_shape_choices(choices)

    # -- Part-B 3D-viewer interaction slots ---------------------------------

    def _on_triad_toggled(self, visible: bool) -> None:
        """Show/hide the RPY triad in every embedded viewer (view-only)."""
        for viewer in self._geometry_viewers:
            viewer.set_triad_visible(visible)

    def _on_shape_requested(self, value: str) -> None:
        """Set the target shape (one ``sensor.set``), seed nominal dims, preview, re-evaluate.

        The viewer previews the new shape immediately from the updated params against the
        last result (the glyph does not need a fresh evaluation), then the shared
        ``parameterEdited`` path schedules the full re-run for the physics. Any required
        dimension still at the ``0.0`` "not set" sentinel is seeded to its nominal value first
        (CU-125) so the scheduled re-evaluate succeeds instead of tripping the shape factory.
        """
        if self._sensor is None:
            return
        self._sensor.set("geometry.target.shape", value)
        seeded = self._seed_nominal_dimensions(value)
        self._preview_last_result()
        # Emit the shape edit and any dimensions seeded alongside it as ONE compound edit
        # so the host records them under a single undo macro — undoing the shape pick then
        # reverses the seeded dims too, in one step (CU-141), instead of leaving them behind.
        self.compoundParameterEdited.emit(["geometry.target.shape", *seeded])

    def _seed_nominal_dimensions(self, shape: str) -> list[str]:
        """Seed *shape*'s required dims to nominal non-zero values where still unset (CU-125).

        Only a dimension currently at the ``0.0`` Rule-12 "not set" sentinel is seeded; a
        user-set non-zero value is never overwritten. Each seed is one ``sensor.set``. The
        schema keeps the ``0.0`` default (0.0 still means "shape not provided") — this is a
        GUI-side UX default so a freshly-picked shape evaluates cleanly.

        Returns the list of dot-paths actually seeded, so the caller can bundle them with the
        shape edit into a single undo macro (CU-141).
        """
        if self._sensor is None:
            return []
        seeded: list[str] = []
        for dotpath, nominal in NOMINAL_SHAPE_DIMENSIONS.get(shape, {}).items():
            if float(self._sensor.get(dotpath)) == 0.0:
                self._sensor.set(dotpath, nominal)
                seeded.append(dotpath)
        return seeded

    def _on_panel_edit_requested(self, dotpath: str) -> None:
        """Open the shared Parameter Editor on a target dimension/RPY field (§4.3).

        The user clicked a dimension or RPY value field on the Schematic side panel; open the
        same :class:`ParameterEditorDialog` the Inputs-tab form and parameter tree use — one
        ``sensor.set`` on commit, validated on a throwaway clone first (a rejected value never
        touches the live sensor; the actionable what/why/action shows inline). This keeps the
        panel a pure view + control surface (R-API §4.1): the panel emits the intent, the pane
        performs the one API call via the dialog.
        """
        if self._sensor is None:
            return
        dialog = ParameterEditorDialog(
            self._sensor,
            dotpath,
            self._after_panel_commit,
            self,
            display_unit=self._display_units.get(dotpath),
        )
        exec_dialog(dialog)

    def _after_panel_commit(self, dotpath: str, unit: str | None) -> None:
        """After an accepted dimension/RPY edit: adopt the unit, preview, re-evaluate.

        Records the chosen display unit (shared with every surface), re-syncs the panel's
        field text off the now-mutated sensor, previews the tilt/wireframe from the updated
        params, then re-emits ``parameterEdited`` so the full physics re-run is scheduled.
        """
        if unit is not None:
            self._display_units[dotpath] = unit
        self._sync_panels()
        self._preview_last_result()
        self.parameterEdited.emit(dotpath)

    def _preview_last_result(self) -> None:
        """Re-render the viewers from the last result + current params (shape/RPY preview)."""
        if self._last_result is None or self._sensor is None:
            return
        for viewer in self._geometry_viewers:
            viewer.show_result(self._last_result, self._sensor)

    @property
    def outputs_readout(self) -> OutputsReadout | None:
        """The scalar stage-output readout, if this stage has one."""
        return self._outputs_list[0] if self._outputs_list else None

    @property
    def metric_cards(self) -> MetricGroupCards | None:
        """The grouped performance-metric cards, if this stage has them (Performance)."""
        return self._metrics_list[0] if self._metrics_list else None

    @property
    def mtf_panel(self) -> MtfPanel | None:
        """The MTF per-term table + overlay, if this stage embeds it."""
        return self._mtf_panels[0] if self._mtf_panels else None

    @property
    def noise_panel(self) -> NoiseBudgetPanel | None:
        """The noise-budget table + bars + explain, if this stage embeds it."""
        return self._noise_panels[0] if self._noise_panels else None

    @property
    def plot_canvases(self) -> list[MatplotlibCanvas]:
        """The figure canvases of this pane's plot sections, in order."""
        return [section.canvas for section in self._plot_sections]

    # -- result delivery ----------------------------------------------------

    def populate(self, result: ChainResult, columns: ConfigurationColumns | None = None) -> None:
        """Fill every section of this pane from *result* (one API call per figure).

        Iterates the per-kind lists so a tabbed composite (each tab contributing its own
        sections) is filled exactly like the single flat pane.

        *columns* is the study's per-configuration Performance model (Phase 4d): when it
        is present the metric cards render one column per configuration from the retained
        evaluate-all pass, and when it is ``None`` — every single-configuration session —
        they render exactly the rows they rendered before Phase 4d. Every **other**
        section stays single-configuration by design: the stage views show the displayed
        configuration (§4.2b), and only the Performance surface goes side by side.
        """
        self._last_result = result
        stage_outputs = result.stage_outputs.get(self._namespace, {})
        for source_form in self._source_forms:
            source_form.refresh()
        for optics_form in self._optics_forms:
            optics_form.refresh()
        for detector_form in self._detector_forms:
            detector_form.refresh()
        for spectral_form in self._spectral_forms:
            spectral_form.refresh()
        for platform_form in self._platform_forms:
            platform_form.refresh()
        for readout_form in self._readout_forms:
            readout_form.refresh()
        for atmosphere_form in self._atmosphere_forms:
            atmosphere_form.refresh()
        self._refresh_detector_illustration()
        # The derived scene class + its relevance preview come from the same
        # ``stage_outputs["geometry"]`` mapping the angle readout renders — read
        # verbatim, never re-derived GUI-side (arch doc §6.3).
        for scene_class_panel in self._scene_class_panels:
            scene_class_panel.populate(stage_outputs)
        for geometry_readout in self._geometry_readouts:
            geometry_readout.populate(stage_outputs)
        # The 3D viewer needs the full result + the live sensor (for shape/optics params);
        # it renders only when a sensor is bound (always true post-evaluate).
        if self._sensor is not None:
            for geometry_viewer in self._geometry_viewers:
                geometry_viewer.show_result(result, self._sensor)
            self._sync_panels()
        for outputs in self._outputs_list:
            outputs.show_stage_outputs(self._namespace, stage_outputs)
        for metrics in self._metrics_list:
            if columns is None:
                metrics.show_metrics(result)
            else:
                metrics.show_matrix(columns.matrix, columns.accents)
        for mtf_panel in self._mtf_panels:
            mtf_panel.show_result(result)
        for noise_panel in self._noise_panels:
            noise_panel.show_result(result)
        for section in self._plot_sections:
            section.render(result)

    def _refresh_detector_illustration(self) -> None:
        """Redraw the pixel schematic from the live sensor's pixel geometry (edit-and-watch).

        Reads the pitch in input units (µm) and the fill factor via the public
        ``Sensor.get_input`` surface (no unit maths here, Rule 2 — display only), so editing
        the pitch or fill factor on the Inputs tab redraws the pixel next evaluation.
        """
        if self._sensor is None or not self._detector_illustrations:
            return

        def _num(dotpath: str, fallback: float) -> float:
            value = self._sensor.get_input(dotpath) if self._sensor is not None else None
            return fallback if value is None else float(value)

        pitch_x = _num("detector.pixel_pitch_x_um", 0.0)
        pitch_y = _num("detector.pixel_pitch_y_um", 0.0)
        fill = _num("detector.fill_factor", 1.0)
        for illustration in self._detector_illustrations:
            illustration.set_pixel_geometry(pitch_x, pitch_y, fill)

    def _sync_panels(self) -> None:
        """Refresh each shape panel's shape/RPY/dimensions from the live sensor.

        Covers the Geometry Schematic tab's :class:`GeometryAnglePanel` (the one mount of
        the shared target-shape editor — GT-0 / Windows finding 14 removed the Source
        duplicate; both surfaces previously edited the one ``geometry.target.shape*``
        parameter set). The panels carry no derived-angles readout; this syncs only the
        shape-library controls. Each field's value is formatted in its chosen display unit
        through the shared formatter, so the panels' value buttons read identically to the
        Inputs form's fields (value + unit suffix, R-UNITS) — a panel never touches the sensor.
        """
        if self._sensor is None:
            return
        shape = str(self._sensor.get("geometry.target.shape"))
        rpy = {
            dotpath: field_display_text(self._sensor, dotpath, self._display_units)
            for dotpath in (
                "geometry.target.shape_yaw_rad",
                "geometry.target.shape_pitch_rad",
                "geometry.target.shape_roll_rad",
            )
        }
        dims = {
            dotpath: field_display_text(self._sensor, dotpath, self._display_units)
            for dotpath in _SHAPE_DIMENSION_PATHS
        }
        # The scalar projected-area field (shown by the panel only when shape="none").
        area_text = field_display_text(
            self._sensor, "geometry.target.projected_area_m2", self._display_units
        )
        for panel in self._geometry_panels:
            panel.set_shape(shape)
            panel.set_orientation(rpy)
            panel.set_dimensions(dims)
            panel.set_projected_area(area_text)


class StageCenter(QWidget):
    """The per-stage contextual center: a placeholder + one :class:`StagePane` per stage.

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    pinOutputRequested(str, str, str, str):
        Bubbled up from a pane's Outputs row pin — ``(stage, key, label, unit)``.
    pinMetricRequested(str, str):
        Bubbled up from a pane's metric row pin — ``(metric_key, label)``.
    """

    pinOutputRequested = Signal(str, str, str, str)
    pinMetricRequested = Signal(str, str)
    parameterEdited = Signal(str)
    # A compound edit: several dot-paths changed by one user action that must undo as a
    # single step (CU-141 — a shape pick plus the dimensions seeded alongside it). The
    # payload is the list of affected dot-paths, primary first.
    compoundParameterEdited = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stageCenter")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget(self)
        self._placeholder = PlotPlaceholder(self)
        self._stack.addWidget(self._placeholder)

        # One pane per chain stage, keyed by namespace. Built once; populated on result.
        self._panes: dict[str, StagePane] = {}
        for namespace, composition in STAGE_COMPOSITIONS.items():
            pane = StagePane(namespace, composition, self)
            pane.pinOutputRequested.connect(self.pinOutputRequested)
            pane.pinMetricRequested.connect(self.pinMetricRequested)
            pane.parameterEdited.connect(self.parameterEdited)
            pane.compoundParameterEdited.connect(self.compoundParameterEdited)
            self._stack.addWidget(pane)
            self._panes[namespace] = pane

        layout.addWidget(self._stack)

        self._result: ChainResult | None = None
        self._selected: str | None = None
        # The study's per-configuration Performance model (Phase 4d). ``None`` for every
        # single-configuration session, which is what keeps that path unchanged.
        self._columns: ConfigurationColumns | None = None

    # -- accessors ----------------------------------------------------------

    @property
    def selected_stage(self) -> str | None:
        """The stage whose composite is shown (``None`` → pre-evaluate placeholder)."""
        return self._selected

    @property
    def plot_placeholder(self) -> PlotPlaceholder:
        """The pre-evaluate placeholder pane."""
        return self._placeholder

    def pane(self, namespace: str) -> StagePane:
        """The :class:`StagePane` for *namespace* (KeyError if unknown — programmer error)."""
        return self._panes[namespace]

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor* + shared display-unit store into every stage's forms.

        Only stages carrying an input form (Geometry, GUI plan Phase 5) do anything; the
        rest ignore it. Called by the window on sensor load and after a config swap.

        A result belongs to the sensor that produced it, so a sensor swap invalidates the
        stored result: it is dropped and the center falls back to the placeholder until the
        next evaluation. Without this, navigating to a stage after File → New (or opening an
        incomplete config) re-populated a stale result against the *new* live sensor — the
        geometry viewer then resolved that (possibly unresolvable) sensor and the whole
        window became unusable behind a modal error (crash: circular f/# dependency on a
        blank config).
        """
        self._result = None
        self._stack.setCurrentWidget(self._placeholder)
        for pane in self._panes.values():
            pane.bind_sensor(sensor, display_units)

    def bind_configuration_scope(self, scope: ConfigurationScope | None) -> None:
        """Hand the session's configuration scope to every stage pane's form fields (4b)."""
        for pane in self._panes.values():
            pane.bind_configuration_scope(scope)

    def set_configuration_columns(self, columns: ConfigurationColumns | None) -> None:
        """Set (or clear) the study's per-configuration Performance columns (Phase 4d).

        Pushed by the window from its retained ``last_run`` before each render — the
        columns are a *view* over a pass that already completed, so setting them never
        evaluates anything. ``None`` restores the single-configuration readout, which is
        what a one-configuration session always gets.

        Held here rather than passed through :meth:`show_result` so a stage switch, a
        theme re-render, and a selector switch all re-render the same columns without the
        caller having to re-supply them.
        """
        self._columns = columns

    @property
    def configuration_columns(self) -> ConfigurationColumns | None:
        """The study columns currently in force (``None`` for a single configuration)."""
        return self._columns

    def set_theme(self, theme: Theme) -> None:
        """Re-theme every stage pane's custom-painted widgets (Phase-9 theme toggle)."""
        for pane in self._panes.values():
            pane.set_theme(theme)

    def refresh_forms(self) -> None:
        """Re-read every geometry input form from its bound sensor (values + active mode).

        Called after a clean evaluation and when navigating to a geometry conflict, so a
        parameter the user changed in the tree (or in either geometry tab's form) is
        reflected in both the Inputs-tab and Schematic-tab forms. Safe only when the bound
        sensor resolves — every caller guarantees it (a clean run, or a geometry over-spec
        whose parameters still resolve individually).
        """
        self._panes["geometry"].refresh_geometry_forms()

    def highlight_geometry_error(self, what: str, context: dict[str, object] | None) -> set[str]:
        """Highlight the geometry mode selector(s) an over/under-spec error names (task 3).

        Returns the implicated family keys (empty when the geometry pane has no form or
        the error does not localise). Selecting the Geometry stage then shows the tint.
        """
        form = self._panes["geometry"].geometry_form
        if form is None:
            return set()
        return form.highlight_error(what, context)

    def highlight_scene_class_error(self, what: str, context: dict[str, object] | None) -> bool:
        """Tint the scene-class card when the error names its assertion (Phase 4).

        Returns whether the error was the assertion's, so the window can decide to
        navigate to the Geometry screen. Cleared by :meth:`clear_geometry_highlight`
        along with the mode-selector tint — one lifecycle for both geometry locators.
        """
        panel = self._panes["geometry"].scene_class_panel
        if panel is None:
            return False
        return panel.highlight_error(what, context)

    def clear_geometry_highlight(self) -> None:
        """Clear any geometry conflict tint — mode selectors and scene-class card."""
        form = self._panes["geometry"].geometry_form
        if form is not None:
            form.clear_highlight()
        panel = self._panes["geometry"].scene_class_panel
        if panel is not None:
            panel.clear_highlight()

    def active_pane(self) -> QWidget:
        """The stack pane currently shown (placeholder or a :class:`StagePane`)."""
        return self._stack.currentWidget()

    def is_placeholder(self) -> bool:
        """True while the pre-evaluate placeholder is shown."""
        return self._stack.currentWidget() is self._placeholder

    # -- navigation + result delivery ---------------------------------------

    def select_stage(self, namespace: str | None) -> None:
        """Select *namespace*'s composite (arch doc §4.4). Navigation only.

        Pre-evaluate the placeholder stays and the selection is remembered; it renders on
        the next result. An unknown namespace (no §4.4.1 row) keeps the placeholder.
        """
        self._selected = namespace
        self._render_selection()

    def show_result(self, result: ChainResult) -> None:
        """Store *result* and render the selected stage's composite.

        With no stage selected yet, the center lands on the default stage
        (:data:`~radiant.gui.stage_views.DEFAULT_STAGE`) so the first evaluation shows a
        populated composite rather than the placeholder.
        """
        self._result = result
        if self._selected is None:
            self._selected = DEFAULT_STAGE
        self._render_selection()

    def _render_selection(self) -> None:
        """Swap to the selected stage's populated pane (or the placeholder)."""
        composition = composition_for(self._selected)
        if self._result is None or composition is None:
            self._stack.setCurrentWidget(self._placeholder)
            return
        pane = self._panes[self._selected]
        pane.populate(self._result, self._columns)
        self._stack.setCurrentWidget(pane)


__all__ = ["StageCenter", "StagePane"]
