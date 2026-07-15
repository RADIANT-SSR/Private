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
from radiant.gui.param_format import field_display_text
from radiant.gui.stage_views import (
    DEFAULT_STAGE,
    STAGE_COMPOSITIONS,
    PlotSpec,
    StageComposition,
    StageSubView,
    composition_for,
)
from radiant.gui.themes import Theme
from radiant.gui.viewer.viewer_widget import GeometryViewer
from radiant.gui.widgets.detector_illustration import DetectorIllustration
from radiant.gui.widgets.detector_inputs_form import DetectorInputsForm
from radiant.gui.widgets.geometry_angle_panel import (
    NOMINAL_SHAPE_DIMENSIONS,
    GeometryAnglePanel,
)
from radiant.gui.widgets.geometry_mode_form import GeometryModeForm
from radiant.gui.widgets.geometry_readout import GeometryReadout
from radiant.gui.widgets.matplotlib_canvas import MatplotlibCanvas
from radiant.gui.widgets.mtf_panel import MtfPanel
from radiant.gui.widgets.noise_budget_panel import NoiseBudgetPanel
from radiant.gui.widgets.optics_inputs_form import OpticsInputsForm
from radiant.gui.widgets.outputs_readout import OutputsReadout
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog
from radiant.gui.widgets.platform_inputs_form import PlatformInputsForm
from radiant.gui.widgets.plot_placeholder import PlotPlaceholder
from radiant.gui.widgets.readout_inputs_form import ReadoutInputsForm
from radiant.gui.widgets.source_inputs_form import SourceInputsForm
from radiant.gui.widgets.spectral_integration_inputs_form import SpectralIntegrationInputsForm
from radiant.gui.widgets.target_shape_panel import TargetShapePanel

if TYPE_CHECKING:
    from radiant.api import ChainResult
    from radiant.api.sensor import Sensor

# Minimum figure height so a composite with two plots stays readable in a scroll area.
_PLOT_MIN_HEIGHT: int = 240

# The shape-dimension parameters the geometry side panel edits (bounds/units from the
# schema; this list is the read/sync surface — the panel owns the shape→subset matrix).
_SHAPE_DIMENSION_PATHS: tuple[str, ...] = (
    "source.target.shape_radius_m",
    "source.target.shape_length_m",
    "source.target.shape_width_m",
    "source.target.shape_height_m",
    "source.target.shape_base_radius_m",
)


class _PlotSection(QWidget):
    """A titled plot region: a header over a guarded ``result.plot.*`` figure."""

    def __init__(self, spec: PlotSpec, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._spec = spec

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel(spec.title, self)
        title.setObjectName("stagePlotTitle")
        layout.addWidget(title)

        self._canvas = MatplotlibCanvas(self)
        self._canvas.setMinimumHeight(_PLOT_MIN_HEIGHT)
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

    def render(self, result: ChainResult) -> None:
        """Draw the section's ``result.plot.*`` figure, or its actionable message."""
        try:
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
        self._geometry_forms: list[GeometryModeForm] = []
        self._geometry_readouts: list[GeometryReadout] = []
        self._geometry_viewers: list[GeometryViewer] = []
        self._geometry_panels: list[GeometryAnglePanel] = []
        # Source-instrument sections (GUI plan Phase PS-1): the radiometric Inputs form and
        # the shared target-shape editor. The shape panels share the same edit/seed/sync path
        # as the Geometry Schematic tab's panels (both edit source.target.shape*).
        self._source_forms: list[SourceInputsForm] = []
        self._target_panels: list[TargetShapePanel] = []
        # The Optics-instrument Inputs form (GUI plan Phase PS-2): edit an optics param and
        # every diagnostic tab refreshes (edit-and-watch). Bound/refreshed like the source form.
        self._optics_forms: list[OpticsInputsForm] = []
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
        self._sensor: Sensor | None = None
        # The shared session display-unit store (bound in). The panel's field values are
        # formatted through it so a unit chosen on any surface reflects on all.
        self._display_units: dict[str, str] = {}
        self._last_result: ChainResult | None = None
        self._outputs_list: list[OutputsReadout] = []
        self._metrics_list: list[OutputsReadout] = []
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
                self._tabs.addTab(self._wrap_subview(subview, tab), subview.title)
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
        if spec.source_inputs or spec.target_shape:
            # The Source instrument's Inputs row: radiometric fields (left) beside the shared
            # shape/orientation editor (right), so the emission-spectrum headline below stays
            # near both — the Geometry-screen "edit-and-watch" layout (arch doc §4.4.1 Source).
            row_widget = QWidget(parent)
            row_widget.setObjectName("sourceInputsRow")
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(12)
            if spec.source_inputs:
                source_form = SourceInputsForm(row_widget)
                source_form.parameterEdited.connect(self.parameterEdited)
                row.addWidget(source_form, 1)
                self._source_forms.append(source_form)
            if spec.target_shape:
                # No triad toggle: the Source stage has no 3D scene to overlay a triad on.
                target_panel = TargetShapePanel(row_widget, show_triad_toggle=False)
                target_panel.shapeRequested.connect(self._on_shape_requested)
                target_panel.editRequested.connect(self._on_panel_edit_requested)
                row.addWidget(target_panel, 1)
                self._target_panels.append(target_panel)
            layout.addWidget(row_widget)
        if spec.optics_inputs:
            # The Optics instrument's editable inputs card (GUI plan Phase PS-2): one
            # sensor.set per edit, and each accepted edit re-emits parameterEdited so the host
            # re-evaluates and every Optics tab (MTF / PSF + Pupil / Throughput) refreshes.
            optics_form = OpticsInputsForm(parent)
            optics_form.parameterEdited.connect(self.parameterEdited)
            layout.addWidget(optics_form)
            self._optics_forms.append(optics_form)
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
        if spec.detector_illustration:
            illustration = DetectorIllustration(parent)
            self._add_section(layout, "Detector pixel", illustration)
            self._detector_illustrations.append(illustration)
        if spec.outputs:
            outputs = OutputsReadout(parent)
            outputs.pinOutputRequested.connect(self.pinOutputRequested)
            self._add_section(layout, "Outputs", outputs)
            self._outputs_list.append(outputs)
        if spec.metrics:
            metrics = OutputsReadout(parent)
            metrics.pinMetricRequested.connect(self.pinMetricRequested)
            self._add_section(layout, "Metrics", metrics)
            self._metrics_list.append(metrics)
        if spec.geometry_form:
            geometry_form = GeometryModeForm(parent)
            geometry_form.parameterEdited.connect(self.parameterEdited)
            layout.addWidget(geometry_form)
            self._geometry_forms.append(geometry_form)
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
        if spec.mtf_panel:
            mtf_panel = MtfPanel(parent)
            self._add_section(layout, "MTF budget", mtf_panel)
            self._mtf_panels.append(mtf_panel)
        if spec.noise_panel:
            # The Detector view suppresses the embedded bar (noise_panel_chart=False) so the
            # framework noise **pie** is the primary chart (drawn as a plot section) and the
            # panel contributes only the table + click-to-explain (GUI plan Phase PS-3).
            noise_panel = NoiseBudgetPanel(parent, show_chart=spec.noise_panel_chart)
            self._add_section(layout, "Noise budget", noise_panel)
            self._noise_panels.append(noise_panel)
        for plot_spec in spec.plots:
            section = _PlotSection(plot_spec, parent)
            self._plot_sections.append(section)
            layout.addWidget(section)
        if spec.note is not None:
            note = QLabel(spec.note, parent)
            note.setObjectName("stageNote")
            note.setWordWrap(True)
            layout.addWidget(note)
        return fills

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
    def geometry_form(self) -> GeometryModeForm | None:
        """The stage-0 input-mode forms, if this stage has them (Geometry)."""
        return self._geometry_forms[0] if self._geometry_forms else None

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
    def target_shape_panel(self) -> TargetShapePanel | None:
        """The Source stage's shared target-shape editor, if this stage has one (PS-1)."""
        return self._target_panels[0] if self._target_panels else None

    @property
    def optics_inputs_form(self) -> OpticsInputsForm | None:
        """The Optics editable-inputs form, if this stage has one (Optics, PS-2)."""
        return self._optics_forms[0] if self._optics_forms else None

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
        if sensor is not None and (self._geometry_panels or self._target_panels):
            self._configure_panels_from_schema(sensor)

    def set_theme(self, theme: Theme) -> None:
        """Re-theme this pane's custom-painted widgets (Phase-9 theme toggle).

        Only the ``QPainter`` widgets that read design tokens from a stored
        :class:`~radiant.gui.themes.tokens.Theme` (the geometry schematic viewer and the
        detector pixel illustration) need telling — every QSS-styled widget re-styles
        automatically when the app stylesheet is re-applied. The ``result.plot.*``
        matplotlib figures are drawn by the API with their own styling and are theme-neutral
        (tracked as CU-139); they are left as-is.
        """
        for viewer in self._geometry_viewers:
            viewer.set_theme(theme)
        for illustration in self._detector_illustrations:
            illustration.set_theme(theme)

    def refresh_geometry_forms(self) -> None:
        """Re-read every geometry input form from the bound sensor (Inputs + Schematic tabs).

        Both the Inputs-tab form and the Schematic-tab form read the one live sensor, so a
        value edited on either surface (or in the parameter tree) is reflected on both after
        the next clean evaluation, keeping the two tabs in sync.
        """
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
        shape_def = defs.get("source.target.shape")
        choices = tuple(shape_def.enum_values) if shape_def and shape_def.enum_values else ()
        if not choices:
            return
        for panel in self._geometry_panels:
            panel.set_shape_choices(choices)
        for target_panel in self._target_panels:
            target_panel.set_shape_choices(choices)

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
        self._sensor.set("source.target.shape", value)
        self._seed_nominal_dimensions(value)
        self._preview_last_result()
        self.parameterEdited.emit("source.target.shape")

    def _seed_nominal_dimensions(self, shape: str) -> None:
        """Seed *shape*'s required dims to nominal non-zero values where still unset (CU-125).

        Only a dimension currently at the ``0.0`` Rule-12 "not set" sentinel is seeded; a
        user-set non-zero value is never overwritten. Each seed is one ``sensor.set``. The
        schema keeps the ``0.0`` default (0.0 still means "shape not provided") — this is a
        GUI-side UX default so a freshly-picked shape evaluates cleanly.
        """
        if self._sensor is None:
            return
        for dotpath, nominal in NOMINAL_SHAPE_DIMENSIONS.get(shape, {}).items():
            if float(self._sensor.get(dotpath)) == 0.0:
                self._sensor.set(dotpath, nominal)

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
        dialog.exec()

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
    def metrics_readout(self) -> OutputsReadout | None:
        """The performance-metric readout, if this stage has one."""
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

    def populate(self, result: ChainResult) -> None:
        """Fill every section of this pane from *result* (one API call per figure).

        Iterates the per-kind lists so a tabbed composite (each tab contributing its own
        sections) is filled exactly like the single flat pane.
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
        self._refresh_detector_illustration()
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
            metrics.show_metrics(result)
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

        Covers both the Geometry Schematic tab's :class:`GeometryAnglePanel` and the Source
        instrument's :class:`TargetShapePanel` (both edit the one ``source.target.shape*``
        parameter set). The panels carry no derived-angles readout; this syncs only the
        shape-library controls. Each field's value is formatted in its chosen display unit
        through the shared formatter, so the panels' value buttons read identically to the
        Inputs form's fields (value + unit suffix, R-UNITS) — a panel never touches the sensor.
        """
        if self._sensor is None:
            return
        shape = str(self._sensor.get("source.target.shape"))
        rpy = {
            dotpath: field_display_text(self._sensor, dotpath, self._display_units)
            for dotpath in (
                "source.target.shape_yaw_rad",
                "source.target.shape_pitch_rad",
                "source.target.shape_roll_rad",
            )
        }
        dims = {
            dotpath: field_display_text(self._sensor, dotpath, self._display_units)
            for dotpath in _SHAPE_DIMENSION_PATHS
        }
        for panel in (*self._geometry_panels, *self._target_panels):
            panel.set_shape(shape)
            panel.set_orientation(rpy)
            panel.set_dimensions(dims)


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
            self._stack.addWidget(pane)
            self._panes[namespace] = pane

        layout.addWidget(self._stack)

        self._result: ChainResult | None = None
        self._selected: str | None = None

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
        """
        for pane in self._panes.values():
            pane.bind_sensor(sensor, display_units)

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

    def clear_geometry_highlight(self) -> None:
        """Clear any geometry mode-selector conflict tint (a clean run/edit)."""
        form = self._panes["geometry"].geometry_form
        if form is not None:
            form.clear_highlight()

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
        pane.populate(self._result)
        self._stack.setCurrentWidget(pane)


__all__ = ["StageCenter", "StagePane"]
