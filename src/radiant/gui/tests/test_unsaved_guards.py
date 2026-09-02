"""Tests for the unsaved-edit guards + line numbers (CU-140, CU-144, CU-145)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets.script_editor import ScriptEditor  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 20000


def _window(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


class TestMainWindowGuard:
    """CU-140: File → New / Open ask before discarding unsaved edits."""

    def test_new_with_clean_state_asks_nothing(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _window(qtbot)
        from radiant.gui import main_window as mw

        asked: list[str] = []
        monkeypatch.setattr(
            mw.QMessageBox,
            "question",
            staticmethod(lambda *a, **k: asked.append("q") or mw.QMessageBox.StandardButton.Cancel),
        )
        window._on_new()  # noqa: SLF001
        assert asked == []  # clean state: no prompt, New proceeded
        # §4.4a: File → New lands on the welcome surface (no sensor); its
        # Blank config card performs the old blank-adopt.
        assert window.sensor is None
        assert window.is_welcome()

    def test_cancel_keeps_dirty_sensor(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _window(qtbot)
        window._mark_dirty()  # noqa: SLF001
        before = window.sensor
        from radiant.gui import main_window as mw

        monkeypatch.setattr(
            mw.QMessageBox,
            "question",
            staticmethod(lambda *a, **k: mw.QMessageBox.StandardButton.Cancel),
        )
        window._on_new()  # noqa: SLF001
        assert window.sensor is before  # cancelled: nothing swapped

    def test_discard_replaces_sensor(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _window(qtbot)
        window._mark_dirty()  # noqa: SLF001
        before = window.sensor
        from radiant.gui import main_window as mw

        monkeypatch.setattr(
            mw.QMessageBox,
            "question",
            staticmethod(lambda *a, **k: mw.QMessageBox.StandardButton.Discard),
        )
        window._on_new()  # noqa: SLF001
        assert window.sensor is not before


class TestScriptTabGuard:
    """CU-144: closing a dirty script tab asks Discard / Cancel."""

    def test_cancel_keeps_dirty_tab(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        editor = ScriptEditor()
        qtbot.addWidget(editor)
        tab = editor.new_tab()
        tab.setPlainText("x = 1")  # a user-style edit marks it dirty
        assert tab.is_dirty
        from radiant.gui.widgets import script_editor as se

        monkeypatch.setattr(
            se.QMessageBox,
            "question",
            staticmethod(lambda *a, **k: se.QMessageBox.StandardButton.Cancel),
        )
        count = editor._tabs.count()  # noqa: SLF001
        editor._on_close_requested(editor._tabs.indexOf(tab))  # noqa: SLF001
        assert editor._tabs.count() == count  # noqa: SLF001

    def test_discard_closes_tab(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        editor = ScriptEditor()
        qtbot.addWidget(editor)
        tab = editor.new_tab()
        tab.setPlainText("x = 1")
        from radiant.gui.widgets import script_editor as se

        monkeypatch.setattr(
            se.QMessageBox,
            "question",
            staticmethod(lambda *a, **k: se.QMessageBox.StandardButton.Discard),
        )
        count = editor._tabs.count()  # noqa: SLF001
        editor._on_close_requested(editor._tabs.indexOf(tab))  # noqa: SLF001
        assert editor._tabs.count() == count - 1  # noqa: SLF001

    def test_clean_tab_closes_without_prompt(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        editor = ScriptEditor()
        qtbot.addWidget(editor)
        tab = editor.new_tab()
        asked: list[str] = []
        from radiant.gui.widgets import script_editor as se

        monkeypatch.setattr(
            se.QMessageBox,
            "question",
            staticmethod(lambda *a, **k: asked.append("q") or se.QMessageBox.StandardButton.Cancel),
        )
        editor._on_close_requested(editor._tabs.indexOf(tab))  # noqa: SLF001
        assert asked == []


class TestLineNumbers:
    """CU-145: the Editor pane shows a line-number margin."""

    def test_margin_reserves_width_and_grows_with_digits(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = ScriptEditor()
        qtbot.addWidget(editor)
        editor.show()
        tab = editor.new_tab()
        w3 = tab.line_number_width()
        assert w3 > 0
        assert tab.viewportMargins().left() == w3
        tab.set_text("\n".join(f"line{i}" for i in range(1, 2001)))  # 4 digits
        assert tab.line_number_width() > w3
        assert tab.viewportMargins().left() == tab.line_number_width()
