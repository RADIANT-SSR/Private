"""Tests for the Compare Config Files dialog (Tier-2 GT-3 over Gap 79).

The wording is asserted, not incidental: CU-214 relabelled this surface from
"Compare Configurations…" because ADR-0010 D-10 reserves bare "configuration" for a
member of a study's configuration set (whose comparison surface is the Performance
stage's columns, §4.4.1). :class:`TestMenuLabel` pins the Tools action text, the window
title, and the fact that the action still opens this dialog.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets.comparison_dialog import (  # noqa: E402
    COMPARE_FILES_MENU_TEXT,
    COMPARE_FILES_TITLE,
    ComparisonDialog,
)

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
            dialog.table.horizontalHeaderItem(c).text() for c in range(dialog.table.columnCount())
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


def _open_window(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """A main window whose first (debounced) evaluation has completed.

    Awaited so the window is never torn down with its evaluate-all worker in flight —
    the same discipline the multi-configuration GUI modules use.
    """
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


class TestMenuLabel:
    """CU-214: the Tools item says "config files", and still opens this dialog."""

    def test_tools_action_is_labelled_for_files_not_configurations(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _open_window(qtbot)
        try:
            text = window.action("tools.compare").text()
            assert text == COMPARE_FILES_MENU_TEXT == "Compare Config Files…"
            # The D-10 collision this closes: the Tools item must no longer read as the
            # per-configuration surface the Edit item's "Configurations…" manages.
            assert "Configurations" not in text
        finally:
            window.close()
            window.deleteLater()

    def test_dialog_title_matches_the_action(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = ComparisonDialog(Sensor.from_yaml(_EXAMPLE))
        qtbot.addWidget(dialog)
        assert dialog.windowTitle() == COMPARE_FILES_TITLE == "Compare Config Files"

    def test_the_action_still_opens_the_dialog(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Relabelling changed the wording only — the wire-up is untouched."""
        window = _open_window(qtbot)
        opened: list[ComparisonDialog] = []
        monkeypatch.setattr(ComparisonDialog, "exec", lambda self: opened.append(self) or 0)
        try:
            window.action("tools.compare").trigger()
        finally:
            window.close()
            window.deleteLater()
        assert len(opened) == 1
        assert opened[0].windowTitle() == COMPARE_FILES_TITLE
