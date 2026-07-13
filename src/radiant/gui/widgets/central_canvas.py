"""The central visualization area: KPI row, banners, and the plot canvas (§4.4).

:class:`CentralCanvas` is the window's central widget. Top to bottom it stacks
(arch doc §4.4):

1. the :class:`~radiant.gui.widgets.kpi_badge_row.KpiBadgeRow` — the always-visible
   metric summary;
2. the :class:`~radiant.gui.widgets.saturation_banner.SaturationBanner` — a
   non-dismissible full-well-clip banner, **below the badge row and above the
   canvas** (owner amendment 2, placement recorded here);
3. a themed **stale notice** — shown when the last evaluation failed, so the
   still-displayed previous result is honestly marked stale (GUI plan §4, Phase 3
   task 4);
4. the plot area — a :class:`QStackedWidget` swapping the
   :class:`~radiant.gui.widgets.plot_placeholder.PlotPlaceholder` (pre-evaluate)
   for the :class:`~radiant.gui.widgets.matplotlib_canvas.MatplotlibCanvas`
   (post-evaluate).

It keeps the ``visualizationArea`` object name the shell layout contract uses. The
stale-notice label is themed via its ``#staleNotice`` object name; this file holds
no colour/font/size literal (GUI plan §4.9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from radiant.gui.widgets.kpi_badge_row import KpiBadgeRow
from radiant.gui.widgets.matplotlib_canvas import MatplotlibCanvas
from radiant.gui.widgets.plot_placeholder import PlotPlaceholder
from radiant.gui.widgets.saturation_banner import SaturationBanner

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
        self._stale_notice = QLabel(_STALE_NOTICE, self)
        self._stale_notice.setObjectName("staleNotice")
        self._stale_notice.setWordWrap(True)
        self._stale_notice.setVisible(False)

        # Plot area: placeholder (index 0) before the first evaluation, matplotlib
        # canvas (index 1) after — swapped on the first successful result.
        self._plot_stack = QStackedWidget(self)
        self._placeholder = PlotPlaceholder(self)
        self._matplotlib_canvas = MatplotlibCanvas(self)
        self._plot_stack.addWidget(self._placeholder)
        self._plot_stack.addWidget(self._matplotlib_canvas)

        layout.addWidget(self._kpi_row)
        layout.addWidget(self._saturation_banner)
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
    def stale_notice(self) -> QLabel:
        """The themed 'last evaluation failed' stale notice (hidden until it is)."""
        return self._stale_notice

    @property
    def matplotlib_canvas(self) -> MatplotlibCanvas:
        """The embedded matplotlib canvas (populated after the first evaluate)."""
        return self._matplotlib_canvas

    @property
    def plot_placeholder(self) -> PlotPlaceholder:
        """The empty-canvas placeholder (shown until the first result)."""
        return self._placeholder

    # -- evaluate loop (Phase 3) --------------------------------------------

    def show_result(self, result: ChainResult) -> None:
        """Display a fresh *result*: badges, saturation banner, and the plot.

        Clears any stale notice (the current result is live), fills the badges from
        the metric surface, updates the saturation banner from
        ``result.well_status()``, and renders the default figure into the canvas.
        """
        self._stale_notice.setVisible(False)
        self._kpi_row.update_from_result(result)
        self._saturation_banner.update_from_status(result.well_status())
        self._matplotlib_canvas.show_result(result)
        self._plot_stack.setCurrentWidget(self._matplotlib_canvas)

    def mark_stale(self) -> None:
        """Mark the displayed result stale after a failed evaluation (task 4).

        Leaves the previous badges and plot in place (never a blank or partial mix)
        but flags them: the badges get the ``→?`` stale marker and the themed stale
        notice appears.
        """
        self._kpi_row.set_stale(True)
        self._stale_notice.setVisible(True)
