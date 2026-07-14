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
    composition_for,
)
from radiant.gui.widgets.geometry_readout import GeometryReadout
from radiant.gui.widgets.matplotlib_canvas import MatplotlibCanvas
from radiant.gui.widgets.mtf_panel import MtfPanel
from radiant.gui.widgets.noise_budget_panel import NoiseBudgetPanel
from radiant.gui.widgets.outputs_readout import OutputsReadout
from radiant.gui.widgets.plot_placeholder import PlotPlaceholder

if TYPE_CHECKING:
    from radiant.api import ChainResult

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

        # Section widgets (only those the composition asks for are built).
        self._title = QLabel(composition.title, body)
        self._title.setObjectName("stageCenterTitle")
        self._body_layout.addWidget(self._title)

        self._geometry_readout: GeometryReadout | None = None
        self._outputs: OutputsReadout | None = None
        self._metrics: OutputsReadout | None = None
        self._mtf_panel: MtfPanel | None = None
        self._noise_panel: NoiseBudgetPanel | None = None
        self._plot_sections: list[_PlotSection] = []

        if composition.outputs:
            self._outputs = OutputsReadout(body)
            self._outputs.pinOutputRequested.connect(self.pinOutputRequested)
            self._add_section("Outputs", self._outputs)
        if composition.metrics:
            self._metrics = OutputsReadout(body)
            self._metrics.pinMetricRequested.connect(self.pinMetricRequested)
            self._add_section("Metrics", self._metrics)
        if composition.geometry_readout:
            self._geometry_readout = GeometryReadout(body)
            self._body_layout.addWidget(self._geometry_readout)
        if composition.mtf_panel:
            self._mtf_panel = MtfPanel(body)
            self._add_section("MTF budget", self._mtf_panel)
        if composition.noise_panel:
            self._noise_panel = NoiseBudgetPanel(body)
            self._add_section("Noise budget", self._noise_panel)
        for spec in composition.plots:
            section = _PlotSection(spec, body)
            self._plot_sections.append(section)
            self._body_layout.addWidget(section)
        if composition.note is not None:
            note = QLabel(composition.note, body)
            note.setObjectName("stageNote")
            note.setWordWrap(True)
            self._body_layout.addWidget(note)

        self._body_layout.addStretch(1)

    def _add_section(self, header: str, widget: QWidget) -> None:
        """Add a titled section (a header label over *widget*)."""
        label = QLabel(header, widget.parentWidget())
        label.setObjectName("stageSectionHeader")
        self._body_layout.addWidget(label)
        self._body_layout.addWidget(widget)

    # -- accessors (tests) --------------------------------------------------

    @property
    def namespace(self) -> str:
        """The chain namespace this pane represents."""
        return self._namespace

    @property
    def geometry_readout(self) -> GeometryReadout | None:
        """The geometry angle readout, if this stage has one."""
        return self._geometry_readout

    @property
    def outputs_readout(self) -> OutputsReadout | None:
        """The scalar stage-output readout, if this stage has one."""
        return self._outputs

    @property
    def metrics_readout(self) -> OutputsReadout | None:
        """The performance-metric readout, if this stage has one."""
        return self._metrics

    @property
    def mtf_panel(self) -> MtfPanel | None:
        """The MTF per-term table + overlay, if this stage embeds it."""
        return self._mtf_panel

    @property
    def noise_panel(self) -> NoiseBudgetPanel | None:
        """The noise-budget table + bars + explain, if this stage embeds it."""
        return self._noise_panel

    @property
    def plot_canvases(self) -> list[MatplotlibCanvas]:
        """The figure canvases of this pane's plot sections, in order."""
        return [section.canvas for section in self._plot_sections]

    # -- result delivery ----------------------------------------------------

    def populate(self, result: ChainResult) -> None:
        """Fill every section of this pane from *result* (one API call per figure)."""
        if self._geometry_readout is not None:
            self._geometry_readout.populate(result.stage_outputs.get(self._namespace, {}))
        if self._outputs is not None:
            self._outputs.show_stage_outputs(
                self._namespace, result.stage_outputs.get(self._namespace, {})
            )
        if self._metrics is not None:
            self._metrics.show_metrics(result)
        if self._mtf_panel is not None:
            self._mtf_panel.show_result(result)
        if self._noise_panel is not None:
            self._noise_panel.show_result(result)
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
