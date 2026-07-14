"""The Noise Budget panel: per-term table, bars, and click-to-explain (arch doc §4.4.1).

:class:`NoiseBudgetPanel` shows the per-term noise table (term name + its σ in e- RMS,
from the public ``result.noise_terms`` surface), the ``result.plot.noise_budget()`` bar
chart, and a per-term explanation panel that updates when a table row is clicked. It is
the relocation of the old Noise Budget detail tab into the **Detector** contextual-center
view (arch doc §4.7); the Readout view points at the same ``result.plot.noise_budget()``.
The noise-contributions **pie** chart named in §4.4.1 is a later per-stage task — the bars
(the shipped mark) stay here.

**Explain surface (Gap 87).** Arch doc §4.4.1 names ``result.explain(term)`` for the
per-term explanation, but no such public accessor exists on ``ChainResult``. Per ground
rule §4.1 the GUI does not reach into stage internals or invent physics text; it shows the
term's own stored :class:`~radiant.core.radiometry.NoiseTerm` metadata (physical basis,
origin frame, the budgets it contributes to) — the honest, public "describe" surface — and
the missing structured explain accessor is tracked as **Gap 87**.

Pre-result the panel shows a themed "evaluate first" state; :meth:`show_result` fills it on
every successful evaluation. Every dimensional value carries its unit through the shared
:func:`~radiant.gui.metric_format.format_metric_value` helper (e- RMS — R-UNITS). All
colour/typography comes from the QSS theme (GUI plan §4.9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
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
    from radiant.core.radiometry import NoiseTerm

_EMPTY: Final[str] = "Noise budget — evaluate to populate."
_NOISE_UNIT: Final[str] = "e- RMS"
_HEADERS: Final[tuple[str, ...]] = ("Term", "σ")
_EXPLAIN_HINT: Final[str] = "Select a noise term to see how it is generated."


def describe_noise_term(term: NoiseTerm) -> str:
    """Human description of a noise *term* from its stored metadata (Gap 87).

    The public API carries no structured per-term explain accessor (Gap 87); this renders
    the :class:`NoiseTerm`'s own fields — value, physical basis, origin frame, and the
    budgets it feeds — which is the honest public "describe" surface.
    """
    contributes = ", ".join(term.contributes_to)
    return (
        f"{term.name}\n"
        f"  value:          {format_metric_value(term.value_e, _NOISE_UNIT)}\n"
        f"  physical basis: {term.physical_basis}\n"
        f"  origin frame:   {term.origin_frame}\n"
        f"  contributes to: {contributes}"
    )


class NoiseBudgetPanel(QWidget):
    """Per-term noise table + bar chart + per-term describe panel (arch doc §4.4.1).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("noiseBudgetPanel")

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

        # Left column: table over the per-term describe panel.
        left = QVBoxLayout()
        left.setSpacing(8)
        self._table = QTableWidget(0, len(_HEADERS), self._content)
        self._table.setObjectName("noiseTable")
        self._table.setHorizontalHeaderLabels(list(_HEADERS))
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.itemSelectionChanged.connect(self._on_row_selected)

        self._explain = QPlainTextEdit(self._content)
        self._explain.setObjectName("noiseExplain")
        self._explain.setReadOnly(True)
        self._explain.setPlainText(_EXPLAIN_HINT)

        left.addWidget(self._table, 3)
        left.addWidget(self._explain, 1)

        self._canvas = MatplotlibCanvas(self._content)

        content_layout.addLayout(left, 1)
        content_layout.addWidget(self._canvas, 2)

        self._stack.addWidget(self._empty)
        self._stack.addWidget(self._content)
        outer.addWidget(self._stack)

        self._result: ChainResult | None = None
        self._terms: tuple[NoiseTerm, ...] = ()

    # -- accessors (tests) --------------------------------------------------

    @property
    def table(self) -> QTableWidget:
        """The per-term noise table."""
        return self._table

    @property
    def canvas(self) -> MatplotlibCanvas:
        """The embedded noise-budget bar-chart canvas."""
        return self._canvas

    @property
    def explain(self) -> QPlainTextEdit:
        """The per-term describe panel."""
        return self._explain

    def is_populated(self) -> bool:
        """True once a result has been shown (content page active)."""
        return self._stack.currentWidget() is self._content

    def term_names(self) -> list[str]:
        """The noise-term names currently in the table (column 0), for tests."""
        return [self._table.item(r, 0).text() for r in range(self._table.rowCount())]

    def select_term(self, row: int) -> None:
        """Select table *row* (drives the describe panel) — used by tests."""
        self._table.selectRow(row)

    # -- result delivery ----------------------------------------------------

    def show_result(self, result: ChainResult) -> None:
        """Fill the per-term table and the noise-budget bar chart from *result*."""
        self._result = result
        self._terms = tuple(result.noise_terms)
        self._fill_table()
        self._canvas.show_figure(_plot_noise_budget(result))
        self._explain.setPlainText(_EXPLAIN_HINT)
        self._stack.setCurrentWidget(self._content)

    def _fill_table(self) -> None:
        """One row per public noise term: name + σ in e- RMS (R-UNITS)."""
        self._table.setRowCount(len(self._terms))
        for row, term in enumerate(self._terms):
            self._table.setItem(row, 0, QTableWidgetItem(term.name))
            value_item = QTableWidgetItem(format_metric_value(term.value_e, _NOISE_UNIT))
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, 1, value_item)

    def _on_row_selected(self) -> None:
        """Show the selected term's stored describe metadata (Gap 87)."""
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        index = rows[0].row()
        if 0 <= index < len(self._terms):
            self._explain.setPlainText(describe_noise_term(self._terms[index]))


def _plot_noise_budget(result: ChainResult):  # type: ignore[no-untyped-def]
    """The ``result.plot.noise_budget()`` bar chart (one API call, GUI plan §4.1)."""
    from radiant.api.inspect import ResultPlotNamespace

    return ResultPlotNamespace(result).noise_budget()


__all__ = ["NoiseBudgetPanel", "describe_noise_term"]
