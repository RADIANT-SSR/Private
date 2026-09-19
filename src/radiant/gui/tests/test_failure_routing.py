"""Pinning tests for CU-373 — evaluation-failure routing (GUI usability audit 2026-09).

Each test reproduces one finding's numbered steps from **Blank config** through the
real entry paths (the Parameter Editor dialog, the window's failure slot, the CLI
loader) and asserts the fixed behaviour. Every test here failed on the pre-fix code;
the finding numbers refer to ``docs/reports/gui_usability_audit_2026-09/``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog  # noqa: E402

_WAIT_MS = 15000


def _blank_window(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """Blank config exactly as the welcome screen's card produces it."""
    window = RADIANTMainWindow()
    qtbot.addWidget(window)
    window._on_blank_config()  # noqa: SLF001 — the Blank card's slot
    return window


def _dialog_set(window: RADIANTMainWindow, dotpath: str, text: str) -> None:
    """Enter *text* for *dotpath* through the Parameter Editor's accept path."""
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


class TestF13BlankConfigFirstFailure:
    """F-13: on a blank configuration every accepted edit schedules an evaluation
    whose failure was the resolver's cycle diagnostic, routed to a modal."""

    def test_first_edit_on_blank_config_raises_no_modal(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Steps: (1) Blank config. (2) Set geometry.sensor_altitude_m = 500000 through
        the editor dialog (accepted). (3) The debounced evaluation runs."""
        window = _blank_window(qtbot)
        opened = _capture_modals(monkeypatch)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, "geometry.sensor_altitude_m", "500000")
        assert opened == [], "the blank-config failure must be an advisory, not a modal"
        status = window.statusBar().currentMessage()
        assert status.startswith("Config incomplete — set ")
        assert "Circular" not in status
        error = window.right_rail.messages.error
        assert error is not None
        assert "Circular dependency" not in str(error)
        assert "params.set" not in str(error)

    def test_detector_first_order_is_quiet_too(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """The audit's worst order (detector-first, six modals) is now zero modals."""
        window = _blank_window(qtbot)
        opened = _capture_modals(monkeypatch)
        for dotpath, text in (
            ("detector.pixel_pitch_x_um", "18"),
            ("detector.pixel_pitch_y_um", "18"),
            ("detector.qe_value", "0.7"),
        ):
            with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
                _dialog_set(window, dotpath, text)
        assert opened == []
        assert window.statusBar().currentMessage().startswith("Config incomplete — set ")
