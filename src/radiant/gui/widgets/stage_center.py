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
    QLabel,
    QScrollArea,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from radiant.api.errors import ApiValidationError
from radiant.api.inspect import ResultPlotNamespace
from radiant.gui.stage_views import (
    DEFAULT_STAGE,
    STAGE_COMPOSITIONS,
    PlotSpec,
    StageComposition,
    StageSubView,
    composition_for,
)
from radiant.gui.widgets.geometry_mode_form import GeometryModeForm
from radiant.gui.widgets.geometry_readout import GeometryReadout
from radiant.gui.widgets.matplotlib_canvas import MatplotlibCanvas
from radiant.gui.widgets.mtf_panel import MtfPanel
from radiant.gui.widgets.noise_budget_panel import NoiseBudgetPanel
from radiant.gui.widgets.outputs_readout import OutputsReadout
from radiant.gui.widgets.plot_placeholder import PlotPlaceholder

if TYPE_CHECKING:
    from radiant.api import ChainResult
    from radiant.api.sensor import Sensor

# Minimum figure height so a composite with two plots stays readable in a scroll area.
_PLOT_MIN_HEIGHT: int = 240


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
                self._build_sections(subview, tab_layout, tab)
                tab_layout.addStretch(1)
                self._tabs.addTab(tab, subview.title)
            self._body_layout.addWidget(self._tabs, 1)
        else:
            # Single flat pane (every v1 stage): sections stack in the body directly.
            self._build_sections(composition, self._body_layout, body)
            self._body_layout.addStretch(1)

    def _build_sections(
        self,
        spec: StageComposition | StageSubView,
        layout: QVBoxLayout,
        parent: QWidget,
    ) -> None:
        """Build *spec*'s sections into *layout* (shared by the flat pane and each tab).

        Only the sections *spec* asks for are built; created widgets are appended to the
        per-kind lists so :meth:`populate` fills them uniformly.
        """
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
            geometry_readout = GeometryReadout(parent)
            layout.addWidget(geometry_readout)
            self._geometry_readouts.append(geometry_readout)
        if spec.mtf_panel:
            mtf_panel = MtfPanel(parent)
            self._add_section(layout, "MTF budget", mtf_panel)
            self._mtf_panels.append(mtf_panel)
        if spec.noise_panel:
            noise_panel = NoiseBudgetPanel(parent)
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

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor* + shared display-unit store into any input form."""
        for form in self._geometry_forms:
            form.bind_sensor(sensor, display_units)

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
        stage_outputs = result.stage_outputs.get(self._namespace, {})
        for geometry_readout in self._geometry_readouts:
            geometry_readout.populate(stage_outputs)
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

    def refresh_forms(self) -> None:
        """Re-read every stage's input form from its bound sensor (values + active mode).

        Called after a clean evaluation and when navigating to a geometry conflict, so a
        parameter the user changed in the tree is reflected in the form. Safe only when
        the bound sensor resolves — both callers guarantee it (a clean run, or a geometry
        over-spec whose parameters still resolve individually).
        """
        form = self._panes["geometry"].geometry_form
        if form is not None:
            form.refresh()

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
