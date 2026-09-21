"""CU-371: the MTF-budget and element-train tables show every row.

Both tables carried a fixed minimum height and no stretch, so they showed five or
six rows whatever the window height and scrolled inside themselves — the manual's
``flagship_mtf_budget`` figure could not show the ``mtf_pixel_aperture`` row the
prose quotes. A table's minimum height is now its content; the stage pane's scroll
area handles overflow. The MTF test failed on the pre-fix code (minimum 190 px for
nine rows).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem  # noqa: E402

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.widgets.mtf_panel import MtfPanel  # noqa: E402
from radiant.gui.widgets.table_sizing import content_height, fit_height_to_rows  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


class TestHelper:
    def test_minimum_height_covers_every_row(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        table = QTableWidget(12, 2)
        qtbot.addWidget(table)
        for row in range(12):
            table.setItem(row, 0, QTableWidgetItem(f"row {row}"))
        height = fit_height_to_rows(table)
        assert height == content_height(table)
        assert table.minimumHeight() >= table.horizontalHeader().sizeHint().height() + sum(
            table.rowHeight(r) for r in range(12)
        )

    def test_floor_keeps_an_empty_table_from_collapsing(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        table = QTableWidget(0, 2)
        qtbot.addWidget(table)
        assert fit_height_to_rows(table, floor=96) == 96


class TestMtfBudgetTable:
    def test_every_contributor_row_fits_without_an_inner_scrollbar(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = Sensor.load(_EXAMPLE).evaluate()
        panel = MtfPanel()
        qtbot.addWidget(panel)
        panel.show_result(result)
        table = panel.table_for("x")
        names = [table.item(r, 0).text() for r in range(table.rowCount())]
        assert "mtf_pixel_aperture" in names  # the row the manual's prose quotes
        assert table.rowCount() >= 6
        assert table.minimumHeight() >= content_height(table)
        table.resize(table.width(), table.minimumHeight())
        assert table.verticalScrollBar().maximum() == 0
