"""Tests for the separate scripting window shell + Workspace (Pass 1, arch doc §4.6.1).

The scripting window is a **separate top-level window** (title "RADIANT Scripting"), not a
dock, hosting the reused Command Window REPL and a live Workspace variable browser. These
tests drive the real widgets on the shipped example config, headless (``offscreen``), and
cover:

  * Tools → Scripting Window opens a top-level :class:`ScriptingWindow` (a window, not a dock);
  * re-triggering raises the *same* instance (no duplicate spawn);
  * the old bottom-dock console is gone (no ``_console_dock`` / no ``consoleDock``);
  * the Command Window has ``sensor`` / ``result`` bound and executes a command;
  * the Workspace lists ``sensor`` / ``result`` and grows a new row when a command creates a
    variable (``x = result.snr()`` → ``x`` appears with type/value);
  * a ``sensor.set(...)`` from the command line still marks the MAIN window stale + Refresh
    re-reads (coherence preserved across the separate window);
  * app exit with the scripting window open is clean.

The pure-REPL contract (history, figure pop-out, coherence detail) lives in
``test_scripting_console.py``; the Workspace's summariser is unit-tested here directly.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from PySide6.QtWidgets import QDockWidget, QMainWindow  # noqa: E402

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets.scripting_window import ScriptingWindow  # noqa: E402
from radiant.gui.widgets.workspace_panel import WorkspacePanel, summarize_variable  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_APERTURE = "optics.aperture_diameter_m"
_WAIT_MS = 15000


def _load_window(qtbot):  # type: ignore[no-untyped-def]
    """Build a window on the example config and wait for its auto-evaluation."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


class TestScriptingWindowShell:
    def test_is_separate_top_level_window_not_a_dock(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Tools → Scripting Window opens a top-level window (not a dock)."""
        window = _load_window(qtbot)
        assert isinstance(window.scripting_window, ScriptingWindow)
        assert isinstance(window.scripting_window, QMainWindow)
        # A genuine separate top-level window (movable to another monitor), not a child dock.
        assert window.scripting_window.isWindow()
        assert window.scripting_window.windowTitle() == "RADIANT Scripting"

    def test_old_bottom_dock_console_is_gone(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The superseded dock is removed: no ``_console_dock`` and no ``consoleDock`` object."""
        window = _load_window(qtbot)
        assert not hasattr(window, "_console_dock")
        dock_names = {d.objectName() for d in window.findChildren(QDockWidget)}
        assert "consoleDock" not in dock_names
        assert "view.toggle_console" not in window._actions

    def test_hidden_until_launched(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The scripting window is hidden at launch (a global tool, opened on demand)."""
        window = _load_window(qtbot)
        assert not window.scripting_window.isVisible()

    def test_launcher_shows_window(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Triggering Tools → Scripting Window shows it."""
        window = _load_window(qtbot)
        window.show()
        qtbot.waitExposed(window)
        window.action("tools.scripting_window").trigger()
        assert window.scripting_window.isVisible()

    def test_relaunch_raises_same_instance_no_duplicate(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Re-triggering the launcher raises the SAME window — it never spawns a duplicate."""
        window = _load_window(qtbot)
        first = window.scripting_window
        window.action("tools.scripting_window").trigger()
        window.action("tools.scripting_window").trigger()
        assert window.scripting_window is first  # same object, not a fresh window


class TestCommandWindow:
    def test_sensor_and_result_bound_and_command_runs(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Command Window has the live ``sensor``/``result`` bound and executes a command."""
        window = _load_window(qtbot)
        console = window.scripting_window.console
        assert console.namespace_sensor() is window.sensor
        console.run_command("result.snr()")
        tail = console.output_text().strip().splitlines()[-1]
        assert float(tail) > 0  # SNR printed as a bare number


class TestWorkspacePane:
    def test_lists_sensor_and_result(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Workspace lists the live ``sensor`` and ``result`` with their types."""
        window = _load_window(qtbot)
        workspace = window.scripting_window.workspace
        names = workspace.variable_names()
        assert "sensor" in names
        assert "result" in names
        assert workspace.row_text("sensor")[1] == "Sensor"
        assert workspace.row_text("result")[1] == "ChainResult"

    def test_new_variable_appears_after_command(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A command that creates a variable makes it appear in the Workspace with type/value."""
        window = _load_window(qtbot)
        scripting = window.scripting_window
        assert "x" not in scripting.workspace.variable_names()

        scripting.console.run_command("x = result.snr()")
        row = scripting.workspace.row_text("x")
        assert row is not None
        name, type_name, value = row
        assert name == "x"
        assert type_name == "float"
        assert float(value) > 0  # the SNR value is shown in the value cell

    def test_array_variable_shows_shape(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """An ndarray variable summarises as its shape (a MATLAB-style size cell)."""
        window = _load_window(qtbot)
        scripting = window.scripting_window
        scripting.console.run_command("w = result.wavelength_um")
        row = scripting.workspace.row_text("w")
        assert row is not None
        assert row[1] == "ndarray"
        assert row[2].startswith("(") and "," in row[2]  # e.g. "(120,) float64"

    def test_selecting_variable_populates_detail(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Selecting a Workspace row shows a detail dump (the result's inspect tree)."""
        window = _load_window(qtbot)
        workspace = window.scripting_window.workspace
        # Programmatically select the `result` row and read the detail pane.
        for i in range(workspace.tree.invisibleRootItem().childCount()):
            item = workspace.tree.invisibleRootItem().child(i)
            if item.text(0) == "result":
                workspace.tree.setCurrentItem(item)
                break
        assert "ChainResult" in workspace.detail.toPlainText()


class TestCoherenceAcrossSeparateWindow:
    def test_console_set_marks_main_window_stale_and_refresh_rereads(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A ``sensor.set`` in the separate window marks the MAIN GUI stale; Refresh re-reads."""
        window = _load_window(qtbot)
        console = window.scripting_window.console
        before = window.parameter_panel.value_text(_APERTURE)

        console.run_command(f"sensor.set('{_APERTURE}', 0.25)")
        assert console.is_stale()  # the console flagged itself stale
        # The MAIN window echoed the staleness on its own surfaces (stage dots).
        assert all(c.dot.status == "stale" for c in window.stage_strip.chips)

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            console.refresh_button.click()

        after = window.parameter_panel.value_text(_APERTURE)
        assert after != before
        assert "0.25" in after
        assert not console.is_stale()

    def test_app_exit_clean_with_scripting_window_open(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Closing the main window with the scripting window open is clean (no hang/segfault)."""
        window = _load_window(qtbot)
        window.action("tools.scripting_window").trigger()
        assert window.close()
        assert not window.isVisible()


class TestSummariser:
    """Unit tests for the pure Workspace summariser (no widget needed)."""

    def test_none(self) -> None:
        assert summarize_variable(None) == ("NoneType", "None")

    def test_float(self) -> None:
        assert summarize_variable(616.0) == ("float", "616.0")

    def test_int(self) -> None:
        assert summarize_variable(120) == ("int", "120")

    def test_string(self) -> None:
        assert summarize_variable("hello") == ("str", "'hello'")

    def test_list_shows_length(self) -> None:
        assert summarize_variable([1, 2, 3]) == ("list", "len 3")

    def test_ndarray_shape(self) -> None:
        np = pytest.importorskip("numpy")
        type_name, summary = summarize_variable(np.zeros(500))
        assert type_name == "ndarray"
        assert summary.startswith("(500,)")

    def test_generic_object_has_blank_value(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A generic object's value cell is blank — its type already names it."""
        panel = WorkspacePanel()
        qtbot.addWidget(panel)
        sensor = Sensor.load(_EXAMPLE)
        type_name, summary = summarize_variable(sensor)
        assert type_name == "Sensor"
        assert summary == ""
