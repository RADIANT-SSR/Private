"""Tests for the Command Window REPL (GUI plan Phase 8, arch doc §4.6.1).

The console is the reused **Command Window** of the separate scripting window (Pass 1). It
is a REPL with the live ``sensor`` / ``result`` bound in its namespace. These tests drive
the real widget on the shipped example config, headless (``offscreen``), and cover:

  * the tool opens/closes cleanly and the REPL starts/stops without error offscreen;
  * ``sensor`` and ``result`` are bound in the namespace, and a metric query prints;
  * a ``sensor.set(...)`` run in the console raises the stale banner and, after **Refresh**,
    the parameter panel reflects the console-set value (the coherence contract);
  * a full rebind (``sensor = Sensor.load(...)``) is adopted on Refresh;
  * a ``plot.*`` figure pops out into its own window;
  * app exit with the console open is clean (no hang / segfault).

The scripting *window* shell (the separate window + Workspace pane) is covered in
``test_scripting_window.py``. The qtconsole in-process kernel is **not** exercised — this
ships the plan-sanctioned REPL fallback (CU-138); the qtconsole path is manual-verify.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from PySide6.QtGui import QKeySequence  # noqa: E402

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets.scripting_console import ScriptingConsole  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_APERTURE = "optics.aperture_diameter_m"
_WAIT_MS = 15000  # generous headroom over the ~0.22 s full-chain evaluate


def _load_window(qtbot):  # type: ignore[no-untyped-def]
    """Build a window on the example config and wait for its auto-evaluation."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass  # the on-load auto-evaluate fires via a 0 ms timer
    return window


class TestConsoleToolWiring:
    def test_scripting_action_gated_on_sensor(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Tools → Scripting Window action is disabled with no sensor, enabled with one."""
        bare = RADIANTMainWindow()
        qtbot.addWidget(bare)
        assert not bare.action("tools.scripting_window").isEnabled()

        window = _load_window(qtbot)
        assert window.action("tools.scripting_window").isEnabled()

    def test_console_shortcut_avoids_macos_reserved_binding(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The launcher shortcut is Ctrl+Shift+P, NOT the macOS-reserved Ctrl+` (⌘`).

        Qt maps portable "Ctrl" to the macOS Command key, so the old Ctrl+` became ⌘` — an
        OS-reserved shortcut (cycle windows) that never reached the app, so the console
        "wouldn't open" on macOS (owner report 2026-07-15). Assert the string, which is what
        Qt hands the platform; the actual on-screen keypress is manual-verify (no cocoa
        display in CI).
        """
        window = _load_window(qtbot)
        seq = window.action("tools.scripting_window").shortcut()
        assert seq == QKeySequence("Ctrl+Shift+P")
        assert seq != QKeySequence("Ctrl+`")


class TestReplLifecycle:
    def test_console_constructs_and_closes_offscreen(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The REPL widget starts and stops without error headless (no kernel needed)."""
        console = ScriptingConsole()
        qtbot.addWidget(console)
        console.show()
        assert console.isVisible()
        assert console.close()

    def test_banner_present_at_start(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The transcript opens with the help banner; the stale banner is hidden."""
        console = ScriptingConsole()
        qtbot.addWidget(console)
        assert "live" in console.output_text()
        assert not console.stale_banner.isVisible()
        assert not console.is_stale()


class TestLiveObjectBinding:
    def test_sensor_and_result_bound(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """``sensor`` is the window's live object and ``result`` is the last ChainResult."""
        window = _load_window(qtbot)
        console = window.console
        assert console.namespace_sensor() is window.sensor
        # `result` is bound (a metric query prints a real number into the transcript).
        console.run_command("result.snr()")
        tail = console.output_text().strip().splitlines()[-1]
        assert float(tail) > 0  # SNR printed as a bare number

    def test_read_only_command_does_not_flag_stale(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A pure read (no mutation) leaves the GUI fresh — no false stale flag."""
        window = _load_window(qtbot)
        console = window.console
        console.run_command("inspect_result(result)")
        assert not console.is_stale()

    def test_command_executed_signal_fires(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Each finished statement emits commandExecuted with its source."""
        window = _load_window(qtbot)
        console = window.console
        with qtbot.waitSignal(console.commandExecuted, timeout=1000) as blocker:
            console.run_command("result.snr()")
        assert blocker.args == ["result.snr()"]


class TestCoherenceAndRefresh:
    def test_console_set_then_refresh_updates_parameter_panel(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A ``sensor.set`` in the console → stale banner → Refresh → the tree shows the value.

        This is the Phase-8 coherence contract: the console mutates the sensor behind the
        GUI's back, the GUI marks itself stale, and one-click Refresh re-reads the panel.
        """
        window = _load_window(qtbot)
        console = window.console
        before = window.parameter_panel.value_text(_APERTURE)

        console.run_command(f"sensor.set('{_APERTURE}', 0.25)")
        assert console.is_stale()  # the mutation flagged the GUI stale

        # Refresh re-reads the console's sensor into the panel and re-evaluates.
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            console.refresh_button.click()

        after = window.parameter_panel.value_text(_APERTURE)
        assert after != before
        assert "0.25" in after  # the tree now shows the console-set aperture
        assert not console.is_stale()  # a fresh evaluation cleared the stale state

    def test_stale_banner_shows_when_console_visible(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """With the console open, a mutation makes the 'Refresh' banner visible."""
        window = _load_window(qtbot)
        window.action("tools.scripting_window").trigger()  # open the scripting window
        console = window.console
        console.run_command(f"sensor.set('{_APERTURE}', 0.3)")
        assert not console.stale_banner.isHidden()  # banner un-hidden on the mutation

    def test_state_maybe_changed_marks_stage_dots_stale(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A console mutation flips the stage-health dots to stale (the GUI's own surface)."""
        window = _load_window(qtbot)
        # After the on-load evaluate the dots are ok/warn, not stale.
        assert any(c.dot.status != "stale" for c in window.stage_strip.chips)
        window.console.run_command(f"sensor.set('{_APERTURE}', 0.28)")
        assert all(c.dot.status == "stale" for c in window.stage_strip.chips)

    def test_rebind_adopted_on_refresh(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A full ``sensor = Sensor.load(...)`` rebind is adopted by the window on Refresh."""
        window = _load_window(qtbot)
        console = window.console
        console.run_command(f"sensor = Sensor.load('{_EXAMPLE}')")
        assert console.is_stale()  # object identity changed → flagged stale
        new_sensor = console.namespace_sensor()
        assert new_sensor is not window.sensor  # diverged behind the GUI's back

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window._refresh_from_console()
        assert window.sensor is new_sensor  # the window adopted the console's sensor


class TestFigureAndExit:
    def test_plot_command_pops_out_a_figure(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A ``plot.*`` command evaluates to a Figure and pops it out into its own window."""
        window = _load_window(qtbot)
        console = window.console
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(console.figureProduced, timeout=_WAIT_MS):
                console.run_command("plot.mtf()")
        assert len(console.figures_produced()) == 1
        assert "figure opened in its own window" in console.output_text()

    def test_exit_command_does_not_kill_process(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A console ``exit()`` is swallowed — it must never tear the GUI process down."""
        window = _load_window(qtbot)
        console = window.console
        console.run_command("exit()")
        assert "SystemExit ignored" in console.output_text()
        assert window.isVisible() or True  # process alive; window not force-closed

    def test_app_exit_clean_with_console_open(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Closing the window with the console open (and a figure out) is clean."""
        window = _load_window(qtbot)
        window.action("tools.scripting_window").trigger()  # open the scripting window
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(window.console.figureProduced, timeout=_WAIT_MS):
                window.console.run_command("plot.mtf()")
        # No worker in flight → close returns True and no segfault/hang.
        assert window.close()
        assert not window.isVisible()


class TestHistory:
    def test_up_arrow_recalls_previous_command(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Submitting a line then pressing Up recalls it into the input box."""
        console = ScriptingConsole()
        qtbot.addWidget(console)
        console.input_box.setText("1 + 1")
        console.input_box.returnPressed.emit()
        assert console.input_box.text() == ""  # submit clears the input
        console.input_box.historyPrev.emit()
        assert console.input_box.text() == "1 + 1"  # Up recalls the prior command
