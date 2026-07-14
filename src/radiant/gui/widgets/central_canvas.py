"""The central visualization area: run bar, saturation banner, and the plot canvas (§4.4).

:class:`CentralCanvas` is the window's central widget. In the contextual layout (arch doc
§4.4, owner-ratified 2026-07-13) the **global metric-badge row is gone** — the performance
metrics now live in the right-rail *Pinned* panel (§4.5) — and the **chain-warning strip is
gone** — warnings now live in the right-rail *Messages* panel (§4.5). What remains here,
top to bottom:

1. a thin **run bar** carrying the accent
   :class:`~radiant.gui.widgets.run_button.RunButton` (Evaluate / F5). The button moved
   here when the badge row that used to host it was retired;
2. the :class:`~radiant.gui.widgets.saturation_banner.SaturationBanner` — the persistent,
   non-dismissible full-well-clip banner. It is **retained in the center** (arch doc §4.4:
   the saturation banner renders at the top of the center column) — it is high-signal and
   deliberately kept out of the generic Messages list (Step-A placement decision);
3. a themed **stale notice** — shown when the last evaluation failed, so the still-displayed
   previous result is honestly marked stale;
4. the plot area — a :class:`QStackedWidget` that swaps between the
   :class:`~radiant.gui.widgets.plot_placeholder.PlotPlaceholder`, the
   :class:`~radiant.gui.widgets.matplotlib_canvas.MatplotlibCanvas`, and the
   :class:`~radiant.gui.widgets.geometry_readout.GeometryReadout`, following the selected
   stage (arch doc §4.4 via :mod:`radiant.gui.stage_views`).

It keeps the ``visualizationArea`` object name the shell layout contract uses. This file
holds no colour/font/size literal (GUI plan §4.9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QHBoxLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget

from radiant.api.inspect import ResultPlotNamespace
from radiant.gui.stage_views import KIND_GEOMETRY, view_for
from radiant.gui.widgets.geometry_readout import GeometryReadout
from radiant.gui.widgets.matplotlib_canvas import MatplotlibCanvas
from radiant.gui.widgets.plot_placeholder import PlotPlaceholder
from radiant.gui.widgets.run_button import RunButton
from radiant.gui.widgets.saturation_banner import SaturationBanner

if TYPE_CHECKING:
    from radiant.api import ChainResult

_STALE_NOTICE: str = "Stale — last evaluation failed; showing the previous result."


class CentralCanvas(QWidget):
    """Run bar + saturation banner + stale notice + swappable plot (live in Phase 3).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Preserve the shell's named region so the theme / layout contract holds.
        self.setObjectName("visualizationArea")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Thin run bar: the accent Evaluate button, right-aligned. It lived in the
        # retired KPI badge row; the F5 / Run menu actions still drive the same slot.
        run_bar = QWidget(self)
        run_bar.setObjectName("runBar")
        run_bar_layout = QHBoxLayout(run_bar)
        run_bar_layout.setContentsMargins(14, 8, 14, 8)
        run_bar_layout.setSpacing(0)
        run_bar_layout.addStretch(1)
        self._run_button = RunButton(run_bar)
        run_bar_layout.addWidget(self._run_button)

        self._saturation_banner = SaturationBanner(self)
        self._stale_notice = QLabel(_STALE_NOTICE, self)
        self._stale_notice.setObjectName("staleNotice")
        self._stale_notice.setWordWrap(True)
        self._stale_notice.setVisible(False)

        # Plot area: the placeholder shows pre-evaluate; after a result the active
        # pane follows the selected stage (a matplotlib figure or the geometry
        # readout — GUI plan Phase 4). The last result and selected stage are
        # remembered so re-evaluations and stage clicks re-render the right pane.
        self._plot_stack = QStackedWidget(self)
        self._placeholder = PlotPlaceholder(self)
        self._matplotlib_canvas = MatplotlibCanvas(self)
        self._geometry_readout = GeometryReadout(self)
        self._plot_stack.addWidget(self._placeholder)
        self._plot_stack.addWidget(self._matplotlib_canvas)
        self._plot_stack.addWidget(self._geometry_readout)

        self._result: ChainResult | None = None
        self._selected_stage: str | None = None

        layout.addWidget(run_bar)
        layout.addWidget(self._saturation_banner)
        layout.addWidget(self._stale_notice)
        layout.addWidget(self._plot_stack, 1)

    # -- accessors ----------------------------------------------------------

    @property
    def run_button(self) -> RunButton:
        """The accent Run/Evaluate button (relocated here from the retired badge row)."""
        return self._run_button

    @property
    def saturation_banner(self) -> SaturationBanner:
        """The full-well saturation banner (visible only when clipped)."""
        return self._saturation_banner

    @property
    def stale_notice(self) -> QLabel:
        """The themed 'last evaluation failed' stale notice (hidden until it is)."""
        return self._stale_notice

    @property
    def matplotlib_canvas(self) -> MatplotlibCanvas:
        """The embedded matplotlib canvas (populated after the first evaluate)."""
        return self._matplotlib_canvas

    @property
    def geometry_readout(self) -> GeometryReadout:
        """The Geometry stage's angle-summary readout pane."""
        return self._geometry_readout

    @property
    def plot_placeholder(self) -> PlotPlaceholder:
        """The empty-canvas placeholder (shown until the first result)."""
        return self._placeholder

    @property
    def active_pane(self) -> QWidget:
        """The plot-area pane currently shown (for tests: which visualization is live)."""
        return self._plot_stack.currentWidget()

    @property
    def selected_stage(self) -> str | None:
        """The stage whose default visualization is shown (``None`` → post-evaluate default)."""
        return self._selected_stage

    # -- evaluate loop (Phase 3) --------------------------------------------

    def show_result(self, result: ChainResult) -> None:
        """Display a fresh *result*: saturation banner and the plot pane.

        Clears any stale notice (the current result is live) and updates the saturation
        banner from ``result.well_status()``. The plot area then re-renders for the
        currently selected stage (or the post-evaluate default when none is selected).
        The performance metrics are delivered to the right-rail Pinned panel, and the
        chain warnings to the right-rail Messages panel, by the main window — not here.
        """
        self._result = result
        self._stale_notice.setVisible(False)
        self._saturation_banner.update_from_status(result.well_status())
        self._render_selection()

    def select_stage(self, namespace: str | None) -> None:
        """Select *namespace*'s default visualization (GUI plan Phase 4, arch §4.4).

        Navigation only — no API call beyond the one ``result.plot.*`` figure the
        stage's view names. With no result yet the placeholder stays; the selection is
        remembered and rendered on the next result.
        """
        self._selected_stage = namespace
        self._render_selection()

    def _render_selection(self) -> None:
        """Swap the plot area to the selected stage's view of the current result.

        Pre-evaluate (no result) shows the placeholder. Otherwise the stage's
        :class:`~radiant.gui.stage_views.StageView` decides: the geometry readout or
        a ``result.plot.*`` figure. Figure production is one API call on the public
        ``result.plot`` surface (GUI plan §4.1) — no plotting in GUI code.
        """
        if self._result is None:
            self._plot_stack.setCurrentWidget(self._placeholder)
            return
        view = view_for(self._selected_stage)
        if view.kind == KIND_GEOMETRY:
            self._geometry_readout.populate(self._result.stage_outputs.get("geometry", {}))
            self._plot_stack.setCurrentWidget(self._geometry_readout)
        else:  # KIND_PLOT
            assert view.plot_method is not None
            figure = getattr(ResultPlotNamespace(self._result), view.plot_method)()
            self._matplotlib_canvas.show_figure(figure)
            self._plot_stack.setCurrentWidget(self._matplotlib_canvas)

    def mark_stale(self) -> None:
        """Mark the displayed result stale after a failed evaluation (task 4).

        Leaves the previous plot in place (never a blank or partial mix) but shows the
        themed stale notice. The right-rail Pinned cards' ``→?`` stale marker is set by
        the main window (they own the metric values now).
        """
        self._stale_notice.setVisible(True)
