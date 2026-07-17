"""Tests for the Compare Configurations dialog (Tier-2 GT-3 over Gap 79)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.widgets.comparison_dialog import ComparisonDialog  # noqa: E402

_REPO = Path(__file__).resolve()
while not (_REPO / "pyproject.toml").exists():
    _REPO = _REPO.parent
_EXAMPLE = _REPO / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 120000


class TestComparisonDialog:
    def test_needs_a_second_config(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = ComparisonDialog(Sensor.from_yaml(_EXAMPLE))
        qtbot.addWidget(dialog)
        dialog.start_comparison()
        assert "Add at least one config" in dialog.status_text

    def test_compares_current_against_variant_file(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        variant = sensor.clone().set("optics.aperture_diameter_m", 0.5)
        variant_path = tmp_path / "bigger_aperture.yaml"
        variant.save(variant_path)

        dialog = ComparisonDialog(sensor)
        qtbot.addWidget(dialog)
        dialog.add_config(variant_path)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(dialog.comparisonSettled, timeout=_WAIT_MS):
                dialog.start_comparison()
        cmp_ = dialog.comparison
        assert cmp_ is not None
        assert cmp_.labels == ("current", "bigger_aperture")
        snr = cmp_.row("snr")
        assert snr.best_index == 1  # bigger aperture wins SNR
        # The rendered table marks the winner and shows the delta.
        headers = [
            dialog.table.horizontalHeaderItem(c).text()
            for c in range(dialog.table.columnCount())
        ]
        assert headers[:2] == ["metric", "unit"]
        row_names = [dialog.table.item(r, 0).text() for r in range(dialog.table.rowCount())]
        r = row_names.index("snr")
        winner_cell = dialog.table.item(r, 3).text()
        assert winner_cell.startswith("✓")
        assert "Δ" in winner_cell

    def test_bad_config_file_reports_actionably(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        dialog = ComparisonDialog(Sensor.from_yaml(_EXAMPLE))
        qtbot.addWidget(dialog)
        bad = tmp_path / "junk.yaml"
        bad.write_text("nonsense: {here: true}\n", encoding="utf-8")
        dialog.add_config(bad)
        dialog.start_comparison()
        assert "load failed" in dialog.status_text
