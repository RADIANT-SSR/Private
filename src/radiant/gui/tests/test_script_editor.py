"""Tests for the scripting window's multi-tab script Editor (Pass 2, arch doc §4.6.1).

Pass 2 adds the third pane — a multi-tab Python **Editor** — above the Pass-1 Command Window
+ Workspace. These tests drive the real widgets on the shipped example config, headless
(``offscreen``), and cover the MATLAB core:

  * **New** opens a blank *untitled* tab; multiple tabs open independently;
  * **Open** loads a ``.py`` file into a new tab (from ``tmp_path``) and records it in the
    persisted recent-scripts list; a bad path leaves the open tabs intact;
  * editing a tab sets its dirty ``*`` marker; **Save** writes the file, clears the marker,
    and round-trips (reload matches);
  * **Run** executes the active tab in the **shared** command namespace — a script that binds a
    variable (``x = result.snr()``) leaves ``x`` in the Command Window namespace *and* the
    Workspace (the key MATLAB behaviour);
  * **Run Selection** runs only the selected lines;
  * a script that raises shows the traceback in the Command Window (surfaced, not swallowed);
  * a script that does ``sensor.set(...)`` marks the MAIN window stale (coherence preserved).

The Editor's own unit contract (tab titles, dirty flags) is exercised on the widgets directly;
the shared-namespace / coherence behaviour is exercised through the full main window.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from PySide6.QtCore import QSettings  # noqa: E402

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.settings_store import SettingsStore  # noqa: E402
from radiant.gui.widgets.script_editor import ScriptEditor  # noqa: E402
from radiant.gui.widgets.script_tab import ScriptTab  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_APERTURE = "optics.aperture_diameter_m"
_WAIT_MS = 15000


def _temp_settings(tmp_path: Path) -> SettingsStore:
    """A temp-file-backed settings store (never touches the developer's real settings)."""
    qs = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    return SettingsStore(qs)


def _load_window(qtbot, tmp_path):  # type: ignore[no-untyped-def]
    """Build a main window on the example config (temp settings) and await auto-evaluation."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        window = RADIANTMainWindow(Sensor.load(_EXAMPLE), settings=_temp_settings(tmp_path))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


class TestEditorWidget:
    """The Editor widget's own tab / dirty contract (no main window needed)."""

    def test_opens_on_one_blank_untitled_tab(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = ScriptEditor()
        qtbot.addWidget(editor)
        assert len(editor.tabs()) == 1
        tab = editor.current_tab()
        assert isinstance(tab, ScriptTab)
        assert tab.path is None
        assert tab.display_name == "untitled"
        assert not tab.is_dirty

    def test_new_opens_additional_independent_tab(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = ScriptEditor()
        qtbot.addWidget(editor)
        first = editor.current_tab()
        second = editor.new_tab()
        assert len(editor.tabs()) == 2
        assert editor.current_tab() is second
        # Editing the second leaves the first untouched (independent buffers).
        second.setPlainText("y = 2")
        assert second.is_dirty
        assert not first.is_dirty
        assert first.toPlainText() == ""

    def test_editing_sets_dirty_marker(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = ScriptEditor()
        qtbot.addWidget(editor)
        tab = editor.current_tab()
        assert editor.tab_titles()[0] == "untitled"
        tab.setPlainText("x = 1")
        assert tab.is_dirty
        assert editor.tab_titles()[0] == "*untitled"

    def test_close_last_tab_keeps_editor_nonempty(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = ScriptEditor()
        qtbot.addWidget(editor)
        editor.tab_widget.tabCloseRequested.emit(0)
        assert len(editor.tabs()) == 1  # a fresh blank tab replaces the closed one


class TestFileOps:
    def test_open_loads_file_into_new_tab_and_records_recent(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _load_window(qtbot, tmp_path)
        scripting = window.scripting_window
        script = tmp_path / "hello.py"
        script.write_text("a = 41 + 1\n", encoding="utf-8")

        tab = scripting._open_path(str(script))
        assert tab is not None
        assert tab.display_name == "hello.py"
        assert tab.toPlainText() == "a = 41 + 1\n"
        assert not tab.is_dirty
        # It appears in the persisted recent-scripts list.
        assert str(script) in window._settings.recent_scripts()

    def test_bad_open_leaves_tabs_intact(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _load_window(qtbot, tmp_path)
        scripting = window.scripting_window
        # A missing file surfaces the (modal) error dialog; stub its blocking exec so the
        # offscreen test does not hang, and assert the dialog would have been shown.
        shown: list[str] = []
        monkeypatch.setattr(
            "radiant.gui.widgets.scripting_window.UnexpectedErrorDialog.exec",
            lambda self: shown.append(self.windowTitle()) or 0,
        )
        before = len(scripting.editor.tabs())
        tab = scripting._open_path(str(tmp_path / "does_not_exist.py"))
        assert tab is None
        assert shown  # the actionable error dialog was raised (not swallowed, Rule 17)
        assert len(scripting.editor.tabs()) == before  # no tab added, none lost

    def test_save_writes_clears_dirty_and_round_trips(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _load_window(qtbot, tmp_path)
        scripting = window.scripting_window
        tab = scripting.editor.current_tab()
        tab.setPlainText("z = 3.14\n")
        assert tab.is_dirty

        dest = tmp_path / "saved.py"
        scripting._save_tab_to(tab, dest)
        assert not tab.is_dirty
        assert tab.path == dest
        assert scripting.editor.tab_titles()[0] == "saved.py"
        # Round-trip: reopening the file matches what was saved.
        assert dest.read_text(encoding="utf-8") == "z = 3.14\n"
        reopened = scripting._open_path(str(dest))
        assert reopened is not None
        assert reopened.toPlainText() == "z = 3.14\n"


class TestRunSharesNamespace:
    """The MATLAB core: Run executes in the SHARED command-window namespace."""

    def test_run_binds_variable_in_shared_namespace_and_workspace(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _load_window(qtbot, tmp_path)
        scripting = window.scripting_window
        console = scripting.console
        tab = scripting.editor.current_tab()
        tab.setPlainText("x = result.snr()\ny = x * 2")
        assert "x" not in console.namespace_variables()

        scripting._on_run()

        # The script's top-level bindings live in the ONE shared namespace...
        ns = console.namespace_variables()
        assert "x" in ns
        assert "y" in ns
        assert ns["y"] == pytest.approx(ns["x"] * 2, rel=1e-12)
        assert ns["x"] > 0
        # ...and the Workspace, which refreshes on the Run's commandExecuted, shows them.
        assert "x" in scripting.workspace.variable_names()
        assert "y" in scripting.workspace.variable_names()

    def test_run_variable_usable_at_command_line(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _load_window(qtbot, tmp_path)
        scripting = window.scripting_window
        console = scripting.console
        scripting.editor.current_tab().setPlainText("k = 6 * 7")
        scripting._on_run()
        # A subsequent command line sees the script's variable (shared state).
        console.run_command("print(k)")
        assert "42" in console.output_text()

    def test_run_selection_runs_only_selected_lines(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _load_window(qtbot, tmp_path)
        scripting = window.scripting_window
        console = scripting.console
        tab = scripting.editor.current_tab()
        tab.setPlainText("first = 111\nsecond = 222\nthird = 333")
        # Select only the middle line.
        text = tab.toPlainText()
        start = text.index("second")
        cursor = tab.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(start + len("second = 222"), cursor.MoveMode.KeepAnchor)
        tab.setTextCursor(cursor)

        scripting._on_run_selection()

        ns = console.namespace_variables()
        assert ns.get("second") == 222
        assert "first" not in ns  # the unselected lines did not run
        assert "third" not in ns

    def test_script_exception_shows_traceback_not_swallowed(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _load_window(qtbot, tmp_path)
        scripting = window.scripting_window
        console = scripting.console
        scripting.editor.current_tab().setPlainText("raise ValueError('boom from script')")

        scripting._on_run()

        transcript = console.output_text()
        assert "Traceback" in transcript
        assert "ValueError" in transcript
        assert "boom from script" in transcript


class TestRunAutoDisplaysBareExpressions:
    """Run auto-displays top-level bare expressions like the command line (arch doc §4.6.1).

    A bare ``plot.mtf()`` on its own line pops its figure and a bare ``result.snr()`` echoes
    its value with **no** ``show()`` / ``sys.displayhook(...)`` wrapper — the MATLAB "run a
    script, see the plots" behaviour. These need the live ``result`` / ``plot`` a real
    evaluation binds, so they drive the full window.
    """

    def test_bare_plot_call_pops_a_figure(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _load_window(qtbot, tmp_path)
        scripting = window.scripting_window
        console = scripting.console
        scripting.editor.current_tab().setPlainText("plot.mtf()")  # bare, no show()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(console.figureProduced, timeout=_WAIT_MS):
                scripting._on_run()
        assert len(console.figures_produced()) == 1
        assert "figure opened in its own window" in console.output_text()

    def test_bare_metric_echoes_its_value(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _load_window(qtbot, tmp_path)
        scripting = window.scripting_window
        console = scripting.console
        before = console.output_text()
        scripting.editor.current_tab().setPlainText("result.snr()")  # bare expression
        scripting._on_run()
        delta = console.output_text()[len(before) :]
        # The metric's value was echoed into the transcript (it fired the displayhook).
        assert any(ch.isdigit() for ch in delta)

    def test_bare_sensor_set_does_not_echo_none(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _load_window(qtbot, tmp_path)
        scripting = window.scripting_window
        console = scripting.console
        before = console.output_text()
        scripting.editor.current_tab().setPlainText(f"sensor.set('{_APERTURE}', 0.24)")
        scripting._on_run()
        delta = console.output_text()[len(before) :]
        assert "None" not in delta  # a None-returning bare call stays silent

    def test_explicit_displayhook_path_still_works(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Backward compatible: the old ``sys.displayhook(fig)`` wrapper still pops a figure."""
        window = _load_window(qtbot, tmp_path)
        scripting = window.scripting_window
        console = scripting.console
        scripting.editor.current_tab().setPlainText(
            "import sys\nfig = plot.mtf()\nsys.displayhook(fig)"
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(console.figureProduced, timeout=_WAIT_MS):
                scripting._on_run()
        assert len(console.figures_produced()) == 1  # exactly one, not doubled


class TestRunCoherence:
    def test_script_sensor_set_marks_main_window_stale(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _load_window(qtbot, tmp_path)
        scripting = window.scripting_window
        console = scripting.console
        scripting.editor.current_tab().setPlainText(f"sensor.set('{_APERTURE}', 0.25)")

        scripting._on_run()

        # The console flags itself stale and the MAIN window echoes it on its stage dots —
        # a script mutation is coherent with the GUI exactly like a typed command.
        assert console.is_stale()
        assert all(c.dot.status == "stale" for c in window.stage_strip.chips)

        # And Refresh re-reads the script's change into the parameter tree.
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            console.refresh_button.click()
        assert "0.25" in window.parameter_panel.value_text(_APERTURE)


class TestLayout:
    def test_editor_pane_present_above_command_and_workspace(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """The window hosts the Editor as its own pane alongside the Command Window + Workspace."""
        window = _load_window(qtbot, tmp_path)
        scripting = window.scripting_window
        assert isinstance(scripting.editor, ScriptEditor)
        # The Run action exists and is reachable (F5 / the toolbar).
        assert scripting.action("file.run") is not None
        assert scripting.action("file.new") is not None
