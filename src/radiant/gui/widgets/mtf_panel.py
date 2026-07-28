"""The MTF panel: system-MTF overlay above a per-axis budget table (arch doc §4.4.1).

:class:`MtfPanel` is the relocation of the old MTF detail tab into the **Optics**
contextual-center view (arch doc §4.7). Its layout follows the owner walkthrough:

* the ``result.plot.mtf()`` overlay **on top** — every contributor's roll-off with
  the detector Nyquist limit drawn as a red dashed line (item 12);
* the per-contributor budget **below** the figure rather than beside it (item 11:
  "maybe have the budget table below the MTF graph"), so the chart gets the full
  pane width and the numbers read underneath it;
* the budget split into **X and Y tabs**, each sampling every contributor at
  0.25, 0.5, 0.75 and 1.0 × Nyquist (item 10), instead of a single MTF@Nyquist
  column. One column showed only where each roll-off *ends*; four show its shape.

The separate MTF-at-Nyquist bar chart was removed in the same pass (item 10:
"MTF, don't need the bar chart") — it re-marked numbers the table already gives.

Terms are **discovered** from the result's own MTF surface — the
``mtf_fraction_table_x`` / ``_y`` stage outputs that ``PerformanceStage``
publishes from :mod:`radiant.performance.mtf_fraction_table` — so no term name is
hardcoded here and no MTF maths happens in the view (import-linter forbids
``gui`` → ``performance``; the sampling is done stage-side and read as data).
MTF is dimensionless, so cells render as bare numbers through the shared
:func:`~radiant.gui.metric_format.format_metric_value` helper.

Pre-result the panel shows a themed "evaluate first" state; :meth:`show_result`
fills it on every successful evaluation. All colour/typography comes from the QSS
theme (§4.9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.metric_format import format_metric_value
from radiant.gui.widgets.matplotlib_canvas import MatplotlibCanvas

if TYPE_CHECKING:
    from radiant.api import ChainResult

_EMPTY: Final[str] = "MTF budget — evaluate to populate."
_MTF_UNIT: Final[str] = "dimensionless"  # MTF is a pure ratio → bare number
_MISSING: Final[str] = "—"

#: The axis tabs, in order. Labels are the operator-facing cross/along-track names.
_AXIS_TABS: Final[tuple[tuple[str, str], ...]] = (
    ("x", "X (cross-track)"),
    ("y", "Y (along-track)"),
)

#: The system row's label — the product of every contributor above it.
_SYSTEM_ROW: Final[str] = "SYSTEM (product)"

# Keep the embedded overlay tall enough that its title/axis labels stay readable when
# the window is short; the pane scrolls rather than collapsing the figure (matches the
# per-stage plot sections' floor in :mod:`radiant.gui.widgets.stage_center`).
_CANVAS_MIN_HEIGHT: Final[int] = 260

# Enough height to show several contributors before the table itself scrolls.
_TABLE_MIN_HEIGHT: Final[int] = 190


class MtfPanel(QWidget):
    """``result.plot.mtf()`` overlay above per-axis MTF-vs-Nyquist-fraction tables.

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
        # Vertical: the figure leads, the numbers follow (owner walkthrough item 11).
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        self._canvas = MatplotlibCanvas(self._content)
        self._canvas.setMinimumHeight(_CANVAS_MIN_HEIGHT)
        content_layout.addWidget(self._canvas, 1)

        self._tabs = QTabWidget(self._content)
        self._tabs.setObjectName("mtfBudgetTabs")
        self._tables: dict[str, QTableWidget] = {}
        for axis, label in _AXIS_TABS:
            table = self._build_table(self._tabs)
            self._tables[axis] = table
            self._tabs.addTab(table, label)
        content_layout.addWidget(self._tabs)

        self._stack.addWidget(self._empty)
        self._stack.addWidget(self._content)
        outer.addWidget(self._stack)

        self._result: ChainResult | None = None

    @staticmethod
    def _build_table(parent: QWidget) -> QTableWidget:
        """One axis' budget table — columns filled in when the fractions are known."""
        table = QTableWidget(0, 0, parent)
        table.setObjectName("mtfTable")
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setMinimumHeight(_TABLE_MIN_HEIGHT)
        return table

    # -- accessors (tests) --------------------------------------------------

    @property
    def table(self) -> QTableWidget:
        """The currently visible axis' budget table (the X tab by default)."""
        return self._tables[_AXIS_TABS[self._tabs.currentIndex()][0]]

    def table_for(self, axis: str) -> QTableWidget:
        """The budget table for ``"x"`` or ``"y"``."""
        return self._tables[axis]

    def axis_tab_labels(self) -> list[str]:
        """The axis tab labels, in order."""
        return [self._tabs.tabText(i) for i in range(self._tabs.count())]

    @property
    def canvas(self) -> MatplotlibCanvas:
        """The embedded MTF-overlay canvas."""
        return self._canvas

    def is_populated(self) -> bool:
        """True once a result has been shown (content page active)."""
        return self._stack.currentWidget() is self._content

    def term_names(self, axis: str = "x") -> list[str]:
        """The contributor names in *axis*' table (column 0, system row excluded)."""
        table = self._tables[axis]
        names = [table.item(r, 0).text() for r in range(table.rowCount())]
        return [n for n in names if n != _SYSTEM_ROW]

    def column_headers(self, axis: str = "x") -> list[str]:
        """*axis* table's header labels, for tests."""
        table = self._tables[axis]
        return [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]

    # -- result delivery ----------------------------------------------------

    def show_result(self, result: ChainResult) -> None:
        """Fill the overlay and both per-axis budget tables from *result*."""
        self._result = result
        performance = result.stage_outputs.get("performance", {})
        for axis, _label in _AXIS_TABS:
            self._fill_table(self._tables[axis], performance.get(f"mtf_fraction_table_{axis}"))
        self._canvas.show_figure(_plot_mtf(result))
        self._stack.setCurrentWidget(self._content)

    def _fill_table(self, table: QTableWidget, fraction_table: Any) -> None:
        """Populate one axis' table from its :class:`MTFFractionTable`, or clear it.

        The stage publishes the table only when it ran the MTF product path with a
        focal length; absent, the axis' table empties rather than showing stale rows.
        """
        if fraction_table is None:
            table.setRowCount(0)
            table.setColumnCount(0)
            return

        fractions = tuple(fraction_table.fractions)
        headers = ["Contributor", *(f"{f:g} x Nyq" for f in fractions)]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        # Every column sizes to its own contents (header + cells) so no header is
        # clipped when the table shares a narrow pane; if the summed width exceeds
        # the pane the table scrolls rather than truncating a header.
        header = table.horizontalHeader()
        for col in range(len(headers)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        names = fraction_table.term_names()
        # Contributors, then the system product as the final summary row.
        table.setRowCount(len(names) + 1)
        for row, name in enumerate(names):
            self._fill_row(table, row, name, fraction_table.per_term[name])
        self._fill_row(table, len(names), _SYSTEM_ROW, fraction_table.system)

    @staticmethod
    def _fill_row(
        table: QTableWidget,
        row: int,
        label: str,
        values: tuple[float | None, ...],
    ) -> None:
        """One table row: a contributor label followed by its right-aligned values."""
        table.setItem(row, 0, QTableWidgetItem(label))
        for offset, value in enumerate(values):
            text = format_metric_value(value, _MTF_UNIT) if value is not None else _MISSING
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, offset + 1, item)


def _plot_mtf(result: ChainResult):  # type: ignore[no-untyped-def]
    """The ``result.plot.mtf()`` overlay figure (one API call, GUI plan §4.1)."""
    from radiant.api.inspect import ResultPlotNamespace

    return ResultPlotNamespace(result).mtf()


__all__ = ["MtfPanel"]
