"""The central visualization area: KPI row, banners, and the plot canvas (§4.4).

:class:`CentralCanvas` is the window's central widget. Top to bottom it stacks
(arch doc §4.4):

1. the :class:`~radiant.gui.widgets.kpi_badge_row.KpiBadgeRow` — the always-visible
   metric summary;
2. the :class:`~radiant.gui.widgets.saturation_banner.SaturationBanner` — a
   non-dismissible full-well-clip banner, **below the badge row and above the
   canvas** (owner amendment 2, placement recorded here);
3. the :class:`~radiant.gui.widgets.warning_strip.WarningStrip` — a themed, clickable
   **warn-token** strip carrying the chain ``UserWarning``s of the last evaluation
   (distinct from the red saturation banner), also between badge row and canvas
   (owner feedback 2026-07-13);
4. a themed **stale notice** — shown when the last evaluation failed, so the
   still-displayed previous result is honestly marked stale (GUI plan §4, Phase 3
   task 4);
5. the plot area — a :class:`QStackedWidget` that swaps between the
   :class:`~radiant.gui.widgets.plot_placeholder.PlotPlaceholder` (pre-evaluate),
   the :class:`~radiant.gui.widgets.matplotlib_canvas.MatplotlibCanvas` (a
   ``result.plot.*`` figure), and the
   :class:`~radiant.gui.widgets.geometry_readout.GeometryReadout` (the Geometry
   stage's angle summary). The active pane follows the selected stage (GUI plan
   Phase 4, arch doc §4.4 table via :mod:`radiant.gui.stage_views`). Every §4.4
   row now names a real ``result.plot`` accessor (the spectral-radiance figures
   for Source / Atmosphere / Spectral Integration landed with Gap 86), so the
   former "not yet available" gap pane is gone.

It keeps the ``visualizationArea`` object name the shell layout contract uses. The
stale-notice label is themed via its ``#staleNotice`` object name; this file holds
no colour/font/size literal (GUI plan §4.9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from radiant.api.inspect import ResultPlotNamespace
from radiant.gui.stage_views import KIND_GEOMETRY, view_for
from radiant.gui.widgets.geometry_readout import GeometryReadout
from radiant.gui.widgets.kpi_badge_row import KpiBadgeRow
from radiant.gui.widgets.matplotlib_canvas import MatplotlibCanvas
from radiant.gui.widgets.plot_placeholder import PlotPlaceholder
from radiant.gui.widgets.saturation_banner import SaturationBanner
from radiant.gui.widgets.warning_strip import WarningStrip

if TYPE_CHECKING:
    from radiant.api import ChainResult

_STALE_NOTICE: str = "Stale — last evaluation failed; showing the previous result."


class CentralCanvas(QWidget):
    """KPI row + saturation banner + stale notice + swappable plot (live in Phase 3).

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

        self._kpi_row = KpiBadgeRow(self)
        self._saturation_banner = SaturationBanner(self)
        self._warning_strip = WarningStrip(self)
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

        layout.addWidget(self._kpi_row)
        layout.addWidget(self._saturation_banner)
        layout.addWidget(self._warning_strip)
        layout.addWidget(self._stale_notice)
        layout.addWidget(self._plot_stack, 1)

    # -- accessors ----------------------------------------------------------

    @property
    def kpi_row(self) -> KpiBadgeRow:
        """The KPI badge row."""
        return self._kpi_row

    @property
    def saturation_banner(self) -> SaturationBanner:
        """The full-well saturation banner (visible only when clipped)."""
        return self._saturation_banner

    @property
    def warning_strip(self) -> WarningStrip:
        """The clickable chain-warning strip (visible only when warnings were raised)."""
        return self._warning_strip

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
        """Display a fresh *result*: badges, saturation banner, and the plot pane.

        Clears any stale notice (the current result is live), fills the badges from
        the metric surface, and updates the saturation banner from
        ``result.well_status()``. The plot area then re-renders for the currently
        selected stage (or the post-evaluate default when none is selected). The chain
        warnings are delivered separately via :meth:`update_warnings` (they are
        captured by the worker, not read off the result).
        """
        self._result = result
        self._stale_notice.setVisible(False)
        self._kpi_row.update_from_result(result)
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

    def update_warnings(self, messages: list[str]) -> None:
        """Show the chain warnings of the last evaluation in the strip (clear if none).

        The messages come from the worker's ``warnings.catch_warnings`` capture (arch
        doc §4.4, owner feedback 2026-07-13); a warning-free run clears the strip.
        """
        self._warning_strip.update_from_warnings(messages)

    def mark_stale(self) -> None:
        """Mark the displayed result stale after a failed evaluation (task 4).

        Leaves the previous badges and plot in place (never a blank or partial mix)
        but flags them: the badges get the ``→?`` stale marker and the themed stale
        notice appears.
        """
        self._kpi_row.set_stale(True)
        self._stale_notice.setVisible(True)
