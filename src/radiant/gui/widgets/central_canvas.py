"""The central visualization area: KPI badge row above the plot canvas (§4.4).

:class:`CentralCanvas` is the window's central widget. It stacks the
:class:`~radiant.gui.widgets.kpi_badge_row.KpiBadgeRow` (the always-visible metric
summary) above the :class:`~radiant.gui.widgets.plot_placeholder.PlotPlaceholder`
(the empty canvas). It keeps the ``visualizationArea`` object name the shell layout
contract uses, so the region the theme and later phases anchor to is unchanged.

Phase 3 replaces the placeholder with the embedded matplotlib canvas and fills the
badges; Phase 1 is the static skeleton they inhabit.
"""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from radiant.gui.widgets.kpi_badge_row import KpiBadgeRow
from radiant.gui.widgets.plot_placeholder import PlotPlaceholder


class CentralCanvas(QWidget):
    """KPI row + plot placeholder, the window's central widget (Phase 1 shell).

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
        self._plot = PlotPlaceholder(self)

        layout.addWidget(self._kpi_row)
        layout.addWidget(self._plot, 1)

    @property
    def kpi_row(self) -> KpiBadgeRow:
        """The KPI badge row (Phase 3 fills its values)."""
        return self._kpi_row

    @property
    def plot_placeholder(self) -> PlotPlaceholder:
        """The empty-canvas placeholder (Phase 3 swaps in the matplotlib canvas)."""
        return self._plot
