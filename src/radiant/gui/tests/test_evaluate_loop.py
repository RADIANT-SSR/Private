"""Integration tests for the Phase 3 evaluate loop (GUI plan Phase 3, task 6).

These drive the real evaluate loop end to end, offscreen, on the shipped example
config: a worker-thread ``sensor.evaluate()`` feeding the metric badges, the
matplotlib canvas, the saturation banner, and the failed-evaluation stale state.
The worker is awaited with ``qtbot.waitSignal`` on ``evaluationFinished`` — no
sleeps (GUI plan §4.10).

Category D: this is the D2 milestone's UX round trip. The golden/regression half is
the separate full ``pytest tests/integration/`` run (the GUI never touches computed
results); these tests assert the *view* over those results.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from radiant.api.sensor import Sensor
from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.widgets import actionable_error_dialog as aed
from radiant.gui.widgets.messages_panel import MessagesPanel
from radiant.gui.widgets.warning_list_dialog import WarningListDialog

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

# Dotpaths driven by the tests (verified against the shipped schema).
_APERTURE = "optics.aperture_diameter_m"
_FULL_WELL = "readout.full_well_capacity_e"

_WAIT_MS = 15000  # generous headroom over the ~0.22 s full-chain evaluate


def _load_window(qtbot):  # type: ignore[no-untyped-def]
    """Build a window on the example config and wait for its auto-evaluation."""
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass  # the on-load auto-evaluate fires via a 0 ms timer
    return window


class TestEvaluateRoundTrip:
    def test_pinned_cards_fill_with_real_values_and_units(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """After evaluate, every Pinned card shows a real value; dimensional ones carry units."""
        window = _load_window(qtbot)
        cards = window.right_rail.pinned.cards

        # No card is left at the em-dash placeholder.
        for card in cards.values():
            assert card.value_text() != "—", card.pin_key

        # R-UNITS: dimensional metrics render their unit (sourced from metadata).
        assert cards["nedt_K"].value_text().endswith("K")
        assert cards["gsd_geometric_mean_m"].value_text().endswith("m")
        # Dimensionless / rating-scale metrics render as a bare number.
        assert cards["snr"].value_text().replace(".", "").isdigit()

        # The center swapped from the placeholder to the default stage's composite,
        # whose plot section rendered a real figure.
        center = window.central_canvas.stage_center
        assert not center.is_placeholder()
        default_pane = center.pane(center.selected_stage)
        assert any(c.has_figure() for c in default_pane.plot_canvases)

    def test_edit_reevaluates_and_moves_metrics(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Editing the aperture re-runs the chain and changes SNR (the D2 click)."""
        window = _load_window(qtbot)
        cards = window.right_rail.pinned.cards
        snr_before = cards["snr"].value_text()

        # Simulate the parameter panel's edit: mutate the shared sensor and signal
        # the edit, which schedules the debounced re-evaluation.
        window.sensor.set(_APERTURE, 0.5)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_APERTURE)

        snr_after = cards["snr"].value_text()
        assert snr_after != snr_before  # a bigger aperture moved SNR
        assert snr_after != "—"


class TestErrorPath:
    def test_failed_eval_shows_dialog_keeps_previous_result_stale(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """An invalid config raises: dialog renders, previous result stays, stale shows."""
        window = _load_window(qtbot)
        cards = window.right_rail.pinned.cards
        snr_before = cards["snr"].value_text()

        # Capture the actionable dialog instead of letting it block the event loop.
        shown: list[aed.ActionableErrorDialog] = []
        monkeypatch.setattr(
            aed.ActionableErrorDialog,
            "exec",
            lambda self: shown.append(self) or 0,
        )

        # Aperture 0 passes set() but the resolver rejects it at evaluate() time
        # (CoreValidationError, a RadiantError) — a real failed evaluation.
        window.sensor.set(_APERTURE, 0.0)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_APERTURE)

        # The actionable (RadiantError) dialog was shown.
        assert len(shown) == 1
        # The previous result stays on screen, flagged stale (never blank/partial).
        assert window.central_canvas.stale_notice.isHidden() is False
        assert cards["snr"].value_text().startswith(snr_before)
        assert cards["snr"].value_text().endswith("→?")  # stale marker (§8.4)
        # The error surfaces in the Messages panel too (§4.5, now carries errors).
        assert window.right_rail.messages.has_error()


class TestSaturationBanner:
    def test_banner_appears_on_clip_and_clears_on_fix(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The non-dismissible banner shows the well numbers on a clip and clears after."""
        window = _load_window(qtbot)
        banner = window.central_canvas.saturation_banner
        # The nominal config does not clip: banner hidden.
        assert banner.isHidden() is True

        # Drive saturation: a tiny full well forces a hard clip.
        window.sensor.set(_FULL_WELL, 100000.0)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_FULL_WELL)

        assert banner.isHidden() is False
        text = banner.text()
        assert "e-" in text  # the well numbers carry their unit (R-UNITS)
        assert "×" in text  # the fill fraction is shown as a multiple
        assert "100,000 e- capacity" in text

        # Restore a large well: the banner clears on the next unsaturated result.
        window.sensor.set(_FULL_WELL, 2000000.0)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_FULL_WELL)
        assert banner.isHidden() is True


class TestMessagesPanel:
    """Item 3 (owner feedback 2026-07-13): chain warnings surface in-window, not the terminal.

    Relocated to the right-rail Messages panel (arch doc §4.5, contextual layout).
    """

    def test_chain_warnings_appear_in_messages(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """After evaluate, the Messages panel carries the chain UserWarnings by count.

        A valid, nominally-operating scenario now evaluates warning-free (CU-166 —
        out-of-calibration NIIRS is structured status, not a warning), so this drives a
        genuinely *actionable* warning — a hard full-well clip — and confirms it reaches
        the Messages panel (the in-window channel replacing the terminal, CU-167).
        """
        window = _load_window(qtbot)
        messages = window.right_rail.messages
        window.sensor.set(_FULL_WELL, 100000.0)  # forces a hard full-well clip
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_FULL_WELL)
        assert messages.warning_count >= 1
        assert any("saturat" in m.lower() for m in messages.warnings)

    def test_saturation_adds_its_warning_and_the_list_dialog_shows_all(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A saturating edit adds the full-well warning; the dialog lists all verbatim."""
        window = _load_window(qtbot)
        messages = window.right_rail.messages
        before = messages.warning_count

        window.sensor.set(_FULL_WELL, 100000.0)  # forces a hard full-well clip
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_FULL_WELL)

        assert messages.warning_count > before
        assert any("saturat" in m.lower() for m in messages.warnings)

        # The click-through list dialog lists every captured warning verbatim.
        dialog = WarningListDialog(messages.warnings)
        qtbot.addWidget(dialog)
        assert dialog.messages == messages.warnings
        body = dialog.body.toPlainText()
        assert all(m in body for m in messages.warnings)

    def test_messages_clear_on_a_warning_free_evaluation(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A warning-free result clears the warnings (widget contract, offscreen)."""
        panel = MessagesPanel()
        qtbot.addWidget(panel)
        panel.set_warnings(["UserWarning: something", "UserWarning: else"])
        assert panel.warning_count == 2
        panel.set_warnings([])  # a clean run
        assert panel.warning_count == 0


class TestTriggersAndDebounce:
    def test_f5_action_triggers_evaluation(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Run → Evaluate (F5) action runs the chain."""
        window = _load_window(qtbot)
        count_before = window.evaluation_count
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("run.evaluate").trigger()
        assert window.evaluation_count == count_before + 1

    def test_run_button_enabled_with_sensor(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The accent Run button (right-rail footer) is enabled once a sensor is loaded."""
        window = _load_window(qtbot)
        assert window.right_rail.run_button.isEnabled()

        empty = RADIANTMainWindow()
        qtbot.addWidget(empty)
        assert not empty.right_rail.run_button.isEnabled()
        assert not empty.action("run.evaluate").isEnabled()

    def test_debounce_collapses_rapid_edits_into_one_run(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A burst of edits within the debounce window yields a single evaluation."""
        window = _load_window(qtbot)
        count_before = window.evaluation_count

        # Fire several edits synchronously — the debounce timer restarts each time,
        # so no worker starts until the burst goes quiet.
        for _ in range(6):
            window.parameter_panel.parameterEdited.emit(_APERTURE)

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            pass  # the single coalesced run fires ~200 ms after the last edit

        assert window.evaluation_count == count_before + 1


class TestThreading:
    def test_chain_runs_off_the_gui_thread(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """The full chain executes on the worker thread, never the GUI thread (§4.5)."""
        main_tid = threading.get_ident()
        seen: dict[str, int] = {}
        original = Sensor.evaluate

        def spy(self, **kwargs):  # type: ignore[no-untyped-def]
            seen["tid"] = threading.get_ident()
            return original(self, **kwargs)

        monkeypatch.setattr(Sensor, "evaluate", spy)

        window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
        qtbot.addWidget(window)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            pass

        assert "tid" in seen
        assert seen["tid"] != main_tid


@pytest.mark.parametrize("dotpath", [_APERTURE, _FULL_WELL])
def test_driven_dotpaths_exist_in_schema(dotpath: str) -> None:
    """Guard: the dotpaths these tests drive are real schema parameters."""
    sensor = Sensor.load(_EXAMPLE)
    assert dotpath in sensor.parameter_defs()
