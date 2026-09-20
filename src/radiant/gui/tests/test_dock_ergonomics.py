"""Pinning tests for CU-376 — Parameters dock ergonomics (GUI usability audit 2026-09).

Each test reproduces one finding's numbered steps from **Blank config** (or the
complete configuration the audit built from it) at the audit's window sizes and
asserts the fixed behaviour. Every test here failed on the pre-fix code; the finding
numbers refer to ``docs/reports/gui_usability_audit_2026-09/``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog  # noqa: E402

_WAIT_MS = 15000

# The audit's minimal complete configuration (Findings_Bootstrap_Recovery §1).
_COMPLETE: tuple[tuple[str, str], ...] = (
    ("optics.aperture_diameter_m", "0.3"),
    ("optics.f_number", "4"),
    ("detector.pixel_pitch_x_um", "18"),
    ("detector.pixel_pitch_y_um", "18"),
    ("detector.qe_value", "0.7"),
    ("spectral_integration.filter_min_um", "3.4"),
    ("spectral_integration.filter_max_um", "5.0"),
    ("spectral_integration.integration_time_s", "0.005"),
    ("source.target.temperature", "300"),
    ("source.target.emissivity", "0.95"),
    ("geometry.sensor_altitude_m", "500000"),
)


def _blank_window(qtbot, width: int = 1400, height: int = 900) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """Blank config as the welcome card produces it, shown at the audit's window size."""
    window = RADIANTMainWindow()
    qtbot.addWidget(window)
    window.resize(width, height)
    window.show()
    qtbot.waitExposed(window)
    window._on_blank_config()  # noqa: SLF001 — the Blank card's slot
    return window


def _dialog_set(window: RADIANTMainWindow, dotpath: str, text: str) -> None:
    panel = window.parameter_panel
    dialog = ParameterEditorDialog(
        window.sensor,
        dotpath,
        panel._after_dialog_commit,
        panel,  # noqa: SLF001
    )
    dialog.value_editor.setText(text)
    dialog.apply(close=True)


def _capture_modals(monkeypatch) -> list[object]:  # type: ignore[no-untyped-def]
    opened: list[object] = []
    monkeypatch.setattr(
        "radiant.gui.main_window.exec_dialog", lambda dlg, *a, **k: opened.append(dlg) or 0
    )
    return opened


class TestF45EditKeepsPlace:
    """F-45: the dock rebuilt on every accepted edit — selection lost, view at the top."""

    def test_accepted_edit_keeps_selection_and_scroll(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Steps: (1) Blank config. (2) Scroll to and select a row far down the tree.
        (3) Set a value through the editor dialog (accepted). (4) Look at the dock."""
        window = _blank_window(qtbot)
        _capture_modals(monkeypatch)
        panel = window.parameter_panel
        tree = panel.tree
        target = "readout.read_noise_e_rms"
        panel.reveal_row(target)
        row_before = tree.currentItem()
        assert row_before is not None and row_before.data(0, 0x0100) == target
        scroll_before = tree.verticalScrollBar().value()
        assert scroll_before > 0, "the row must sit below the fold for the test to mean anything"

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, target, "12")

        assert tree.currentItem() is row_before  # the same item object: no rebuild
        assert tree.verticalScrollBar().value() == scroll_before
        assert panel.value_text(target) == "12 e-" or panel.value_text(target).startswith("12 ")
        assert panel.source_text(target) == "user-set"

    def test_refresh_rerenders_every_row_state(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """A refresh must be indistinguishable from a rebuild: derived and user-set
        badges, the editable flag and the value all follow the sensor."""
        window = _blank_window(qtbot)
        _capture_modals(monkeypatch)
        panel = window.parameter_panel
        focal = "optics.focal_length_m"
        item = panel._items[focal]  # noqa: SLF001
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            for dotpath, text in _COMPLETE:
                _dialog_set(window, dotpath, text)
        assert panel._items[focal] is item  # noqa: SLF001 — never rebuilt
        assert panel.value_text(focal) == "⚡ 1.2 m"
        assert panel.source_text(focal) == "derived"
        assert not panel.is_editable(focal)
        # A take-over flips it back to user-set + editable, in place.
        dialog = ParameterEditorDialog(window.sensor, focal, panel._after_dialog_commit, panel)  # noqa: SLF001
        qtbot.addWidget(dialog)
        dialog.value_editor.setText("1.8")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            dialog.apply(close=True)
        assert panel._items[focal] is item  # noqa: SLF001
        assert panel.value_text(focal) == "1.8 m"
        assert panel.is_editable(focal)
        assert panel.value_text("optics.f_number") == "⚡ 6"
        assert not panel.is_editable("optics.f_number")


class TestF46ValueColumnHasWidthOnBlankConfig:
    """F-46: on a blank configuration the Value column collapsed to about ten pixels
    ("Va"), so the first double-click landed on the name column."""

    def test_value_column_keeps_its_floor_on_a_blank_config(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.parameter_panel import _VALUE_FLOOR_PX

        window = _blank_window(qtbot)
        header = window.parameter_panel.tree.header()
        assert header.sectionSize(1) >= _VALUE_FLOOR_PX
        assert header.sectionSize(1) >= 60  # a real click target, whatever the constant

    def test_value_cell_is_the_one_a_double_click_lands_on(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The delegate's editor opens from the Value cell, not the dialog from the name."""
        window = _blank_window(qtbot)
        panel = window.parameter_panel
        tree = panel.tree
        item = panel._items["geometry.sensor_altitude_m"]  # noqa: SLF001
        from PySide6.QtCore import QPoint

        rect = tree.visualItemRect(item)
        header = tree.header()
        x = header.sectionPosition(1) + header.sectionSize(1) // 2
        index = tree.indexAt(QPoint(x, rect.center().y()))
        assert index.column() == 1


class TestF14NamesReadableAtDefaultWidth:
    """F-14: at the default dock width in a 1400x900 window the name column showed
    `sens…de_m`, `targ…ge_m`; the eight target.shape.* rows were indistinguishable."""

    def test_geometry_leaf_names_fit_unelided(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from PySide6.QtGui import QFontMetrics

        window = _blank_window(qtbot, 1400, 900)
        _capture_modals(monkeypatch)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            for dotpath, text in _COMPLETE:
                _dialog_set(window, dotpath, text)  # values present, as in the finding
        panel = window.parameter_panel
        tree = panel.tree
        width = tree.header().sectionSize(0)
        metrics = QFontMetrics(tree.font())
        indent = tree.indentation()
        elided = [
            item.text(0)
            for dotpath, item in panel._items.items()  # noqa: SLF001
            if dotpath.startswith("geometry.")
            and metrics.horizontalAdvance(item.text(0)) + indent + 6 > width
        ]
        assert elided == [], f"name column {width}px elides {elided}"
        shape_rows = [
            item.text(0)
            for dotpath, item in panel._items.items()  # noqa: SLF001
            if dotpath.startswith("geometry.target.shape")
        ]
        assert len(shape_rows) >= 6 and len(set(shape_rows)) == len(shape_rows)
