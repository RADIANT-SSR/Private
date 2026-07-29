"""Tests for the contextual-layout right rail (arch doc §4.5, retrofit Step A).

These drive the persistent right rail on the shipped example config, offscreen: the
Pinned metric cards (default set + pin/unpin), the in-app Edit Config (YAML) modal
(open → valid Apply swaps + re-evaluates; invalid Apply surfaces an actionable error and
leaves the live config untouched), and the Messages panel (warnings + errors). They also
guard that the retired global metric-badge row is gone from the central layout.

Category A (infrastructure/UX rearrangement): the worker is awaited with
``qtbot.waitSignal`` on ``evaluationFinished`` — no sleeps (GUI plan §4.10). The GUI
never touches computed results; these assert the *view* over them.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialog

from radiant.api.sensor import Sensor
from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.widgets import actionable_error_dialog as aed
from radiant.gui.widgets.pin_picker_dialog import PinPickerDialog

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 15000
_FULL_WELL = "readout.full_well_capacity_e"

_DEFAULT_KEYS = ["snr", "nedt_K", "niirs", "gsd_geometric_mean_m", "mtf_at_nyquist"]


def _load_window(qtbot):  # type: ignore[no-untyped-def]
    """Build a window on the example config and wait for its auto-evaluation."""
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


class TestPinPersistence:
    """CU-115: the pin set persists across sessions via an (injected) QSettings."""

    @staticmethod
    def _panel(qtbot, ini_path):  # type: ignore[no-untyped-def]
        from PySide6.QtCore import QSettings

        from radiant.gui.widgets.pinned_panel import PinnedPanel

        settings = QSettings(str(ini_path), QSettings.Format.IniFormat)
        panel = PinnedPanel(settings=settings)
        qtbot.addWidget(panel)
        return panel, settings

    def test_pin_persists_across_panels(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        ini = tmp_path / "pins.ini"
        p1, s1 = self._panel(qtbot, ini)
        p1.pin("custom_metric", "Custom")
        s1.sync()
        assert "custom_metric" in p1.pinned_keys
        # A fresh panel on the same settings file restores the pin.
        p2, _ = self._panel(qtbot, ini)
        assert "custom_metric" in p2.pinned_keys

    def test_unpin_persists_across_panels(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        ini = tmp_path / "pins.ini"
        p1, s1 = self._panel(qtbot, ini)
        p1.unpin("snr")  # remove a default
        s1.sync()
        p2, _ = self._panel(qtbot, ini)
        assert "snr" not in p2.pinned_keys

    def test_empty_settings_yields_default_set(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        p, _ = self._panel(qtbot, tmp_path / "empty.ini")
        assert p.pinned_keys == _DEFAULT_KEYS

    def test_stage_output_pin_round_trips(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        ini = tmp_path / "pins.ini"
        p1, s1 = self._panel(qtbot, ini)
        p1.pin_stage_output("optics", "A_collect", "A collect", "m²")
        s1.sync()
        p2, _ = self._panel(qtbot, ini)
        assert "optics.A_collect" in p2.pinned_keys


class TestPinned:
    def test_default_set_present_with_units(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The default pinned set is the five performance metrics, with units (R-UNITS)."""
        window = _load_window(qtbot)
        cards = window.right_rail.pinned.cards
        assert list(cards.keys()) == _DEFAULT_KEYS
        # Dimensional metrics carry their unit; dimensionless render bare.
        assert cards["nedt_K"].value_text().endswith("K")
        assert cards["gsd_geometric_mean_m"].value_text().endswith("m")
        assert cards["snr"].value_text().replace(".", "").isdigit()

    def test_unpin_removes_a_card(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The unpin affordance removes a card from the panel."""
        window = _load_window(qtbot)
        pinned = window.right_rail.pinned
        pinned.cards["niirs"].unpin_button.click()
        assert "niirs" not in pinned.cards
        assert "niirs" not in pinned.pinned_keys

    def test_pin_adds_a_metric(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Pinning a metric from the surface adds a card that fills from the last result."""
        window = _load_window(qtbot)
        pinned = window.right_rail.pinned
        # Pick a metric not in the default set from the picker's candidate list.
        result = window.last_result
        picker = PinPickerDialog(result, pinned.pinned_keys)
        qtbot.addWidget(picker)
        assert picker.list_widget.count() > 0  # more metrics than the five defaults
        key = picker.selected_key()
        assert key is not None and key not in _DEFAULT_KEYS

        pinned.pin(key, key)
        assert key in pinned.cards
        # The new card is populated from the stored result (not left at the em-dash).
        assert pinned.cards[key].value_text() != "—"


class TestYamlEditor:
    def test_modal_opens_with_current_config_text(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The editor preloads the live config YAML (the Sensor.save round-trip)."""
        window = _load_window(qtbot)
        dialog = window.open_yaml_editor()
        qtbot.addWidget(dialog)
        assert dialog is not None
        assert dialog.yaml_text() == window.sensor.to_yaml(scope="inputs")
        assert "aperture_diameter_m: 0.3" in dialog.yaml_text()

    def test_valid_apply_swaps_config_and_reevaluates(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Apply with valid edited YAML re-parses through the framework and moves SNR."""
        window = _load_window(qtbot)
        snr_before = window.right_rail.pinned.cards["snr"].value_text()

        dialog = window.open_yaml_editor()
        qtbot.addWidget(dialog)
        edited = dialog.yaml_text().replace("aperture_diameter_m: 0.3", "aperture_diameter_m: 0.9")
        dialog.editor.setPlainText(edited)

        # Apply → configApplied → _apply_new_config → a fresh full-chain evaluation.
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            dialog.apply_button.click()

        # The live sensor was swapped and the whole GUI refreshed: SNR moved.
        assert "aperture_diameter_m: 0.9" in window.sensor.to_yaml(scope="inputs")
        snr_after = window.right_rail.pinned.cards["snr"].value_text()
        assert snr_after != snr_before
        # A successful Apply closes the modal.
        assert dialog.result() == QDialog.DialogCode.Accepted

    def test_invalid_apply_shows_error_and_leaves_config_unchanged(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """Apply with invalid YAML shows the actionable error; the live config is untouched."""
        window = _load_window(qtbot)
        before = window.sensor.to_yaml(scope="inputs")
        sensor_obj = window.sensor

        shown: list[aed.ActionableErrorDialog] = []
        monkeypatch.setattr(aed.ActionableErrorDialog, "exec", lambda self: shown.append(self) or 0)

        dialog = window.open_yaml_editor()
        qtbot.addWidget(dialog)
        applied: list[object] = []
        dialog.configApplied.connect(lambda s: applied.append(s))
        dialog.editor.setPlainText("optics:\n  aperture_diameter_m: [broken")
        dialog.apply_button.click()

        # The actionable (RadiantError) dialog was shown; the config is NEVER mutated.
        assert len(shown) == 1
        assert applied == []  # configApplied did not fire
        assert window.sensor is sensor_obj  # same live sensor object
        assert window.sensor.to_yaml(scope="inputs") == before  # unchanged via the public surface
        # The dialog stays open with the bad text (not accepted/closed).
        assert dialog.result() != QDialog.DialogCode.Accepted
        assert "broken" in dialog.yaml_text()

    def test_revert_restores_current_config_text(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Revert restores the editor to the current config text."""
        window = _load_window(qtbot)
        dialog = window.open_yaml_editor()
        qtbot.addWidget(dialog)
        original = dialog.yaml_text()
        dialog.editor.setPlainText("garbage: true")
        dialog.revert_button.click()
        assert dialog.yaml_text() == original


class TestMessages:
    def test_warnings_listed_on_a_warning_run(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """An actionable-warning-emitting run populates the Messages panel.

        A valid scenario evaluates warning-free (CU-166); a hard full-well clip is a
        genuine, actionable warning that must surface in the panel (CU-167).
        """
        window = _load_window(qtbot)
        window.sensor.set(_FULL_WELL, 100000.0)  # forces a hard full-well clip
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_FULL_WELL)
        assert window.right_rail.messages.warning_count >= 1

    def test_messages_clear_on_a_clean_run(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Setting a clean (warning-free) result clears the warnings (widget contract)."""
        window = _load_window(qtbot)
        messages = window.right_rail.messages
        messages.set_warnings([])
        assert messages.warning_count == 0
        assert messages.has_error() is False


class TestBadgeRowRemoved:
    def test_no_kpi_row_in_central_layout(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The retired global metric-badge row is gone from the central canvas."""
        window = _load_window(qtbot)
        assert not hasattr(window.central_canvas, "kpi_row")
        # The run button relocated to the right-rail footer (§4.5); it is no longer on the
        # central canvas at all (owner feedback 2026-07-13).
        assert not hasattr(window.central_canvas, "run_button")
        assert window.right_rail.run_button.objectName() == "runButton"

    def test_retired_widget_modules_are_deleted(self) -> None:
        """The KpiBadgeRow / MetricBadge / WarningStrip modules are removed (retired)."""
        for name in (
            "radiant.gui.widgets.kpi_badge_row",
            "radiant.gui.widgets.metric_badge",
            "radiant.gui.widgets.warning_strip",
        ):
            with pytest.raises(ModuleNotFoundError):
                importlib.import_module(name)
