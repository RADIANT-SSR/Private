"""The MTF panel: per-term MTF@Nyquist table + overlay figure (arch doc §4.4.1).

:class:`MtfPanel` shows, side by side, the per-contributor MTF-at-Nyquist table and the
``result.plot.mtf()`` overlay of every MTF term. It is the relocation of the old MTF
detail tab into the **Optics** contextual-center view (arch doc §4.7); the Platform and
Performance views reach the same MTF terms through the Performance overlay. The table
terms are **discovered** from the result's own MTF surface —
``stage_outputs["performance"]["mtf_budget"]``'s ``per_term_at_nyquist`` (a
:class:`~radiant.performance.mtf_budget.MTFBudgetResult`) — so no term name is hardcoded;
the x/y-suffixed keys are grouped into their base contributor with an x- and a y-axis
column. MTF is dimensionless, so cells render as bare numbers through the shared
:func:`~radiant.gui.metric_format.format_metric_value` helper (a dimensionless unit shows
no suffix — R-UNITS still honoured, the value simply carries no dimension).

Pre-result the panel shows a themed "evaluate first" state; :meth:`show_result` fills it
on every successful evaluation. All colour/typography comes from the QSS theme (§4.9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.metric_format import format_metric_value
from radiant.gui.widgets.matplotlib_canvas import MatplotlibCanvas

if TYPE_CHECKING:
    from radiant.api import ChainResult

_EMPTY: Final[str] = "MTF budget — evaluate to populate."
_MTF_UNIT: Final[str] = "dimensionless"  # MTF is a pure ratio → bare number
_HEADERS: Final[tuple[str, ...]] = ("Contributor", "MTF @ Nyq (x)", "MTF @ Nyq (y)")
# Keep the embedded overlay tall enough that its title/axis labels stay readable when
# the window is short; the pane scrolls rather than collapsing the figure (matches the
# per-stage plot sections' floor in :mod:`radiant.gui.widgets.stage_center`).
_CANVAS_MIN_HEIGHT: Final[int] = 240


def _bases(per_term_at_nyquist: dict[str, float]) -> list[str]:
    """The base contributor names, discovered from x/y-suffixed MTF-term keys."""
    return sorted({n[:-2] for n in per_term_at_nyquist if n.endswith(("_x", "_y"))})


class MtfPanel(QWidget):
    """Per-term MTF@Nyquist table + ``result.plot.mtf()`` overlay (arch doc §4.4.1).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mtfPanel")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._stack = QStackedWidget(self)

        self._empty = QLabel(_EMPTY, self)
        self._empty.setObjectName("detailPlaceholderMsg")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)

        self._content = QWidget(self)
        content_layout = QHBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        self._table = QTableWidget(0, len(_HEADERS), self._content)
        self._table.setObjectName("mtfTable")
        self._table.setHorizontalHeaderLabels(list(_HEADERS))
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        # Every column sizes to its own contents (header + cells) so no header is clipped
        # to "trib…"/"@ Nyq…" when the table shares a narrow pane; if the summed width
        # exceeds the pane the table scrolls horizontally rather than truncating a header.
        header = self._table.horizontalHeader()
        for col in range(len(_HEADERS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        self._canvas = MatplotlibCanvas(self._content)
        self._canvas.setMinimumHeight(_CANVAS_MIN_HEIGHT)

        content_layout.addWidget(self._table, 3)
        content_layout.addWidget(self._canvas, 4)

        self._stack.addWidget(self._empty)
        self._stack.addWidget(self._content)
        outer.addWidget(self._stack)

        self._result: ChainResult | None = None

    # -- accessors (tests) --------------------------------------------------

    @property
    def table(self) -> QTableWidget:
        """The per-term MTF@Nyquist table."""
        return self._table

    @property
    def canvas(self) -> MatplotlibCanvas:
        """The embedded MTF-overlay canvas."""
        return self._canvas

    def is_populated(self) -> bool:
        """True once a result has been shown (content page active)."""
        return self._stack.currentWidget() is self._content

    def term_names(self) -> list[str]:
        """The contributor names currently in the table (column 0), for tests."""
        return [self._table.item(r, 0).text() for r in range(self._table.rowCount())]

    # -- result delivery ----------------------------------------------------

    def show_result(self, result: ChainResult) -> None:
        """Fill the per-term table and the MTF overlay from *result*."""
        self._result = result
        budget = result.stage_outputs.get("performance", {}).get("mtf_budget")
        per_term = getattr(budget, "per_term_at_nyquist", {}) if budget is not None else {}
        self._fill_table(per_term)
        self._canvas.show_figure(_plot_mtf(result))
        self._stack.setCurrentWidget(self._content)

    def _fill_table(self, per_term_at_nyquist: dict[str, float]) -> None:
        """Populate one row per discovered contributor (x + y MTF@Nyquist)."""
        bases = _bases(per_term_at_nyquist)
        self._table.setRowCount(len(bases))
        for row, base in enumerate(bases):
            self._table.setItem(row, 0, QTableWidgetItem(base))
            for col, axis in ((1, "_x"), (2, "_y")):
                value = per_term_at_nyquist.get(f"{base}{axis}")
                text = format_metric_value(value, _MTF_UNIT) if value is not None else "—"
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(row, col, item)


def _plot_mtf(result: ChainResult):  # type: ignore[no-untyped-def]
    """The ``result.plot.mtf()`` overlay figure (one API call, GUI plan §4.1)."""
    from radiant.api.inspect import ResultPlotNamespace

    return ResultPlotNamespace(result).mtf()


__all__ = ["MtfPanel"]
