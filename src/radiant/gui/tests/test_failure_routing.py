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


def _dialog_choose(window: RADIANTMainWindow, dotpath: str, text: str) -> None:
    """Pick *text* for an enum *dotpath* through the Parameter Editor's combo."""
    from PySide6.QtWidgets import QComboBox

    panel = window.parameter_panel
    dialog = ParameterEditorDialog(
        window.sensor,
        dotpath,
        panel._after_dialog_commit,
        panel,  # noqa: SLF001
    )
    editor = dialog.value_editor
    assert isinstance(editor, QComboBox)
    editor.setCurrentText(text)
    dialog.apply(close=True)


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


def _complete_window(qtbot, monkeypatch) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    window = _blank_window(qtbot)
    _capture_modals(
        monkeypatch,
    )
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        for dotpath, text in _COMPLETE:
            _dialog_set(window, dotpath, text)
    assert window.last_result is not None
    return window


def _chip_status(window: RADIANTMainWindow, namespace: str) -> str:
    return window.stage_strip.chip(namespace).status


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


class TestF09MidSwitchStatesAreAdvisories:
    """F-09: readout architecture and calibration scheme got the advisory; cal-point
    mode, transmission mode, geometry door conflicts and consistency groups got a
    modal per re-evaluation with all ten chips red."""

    def test_geometry_door_conflict_is_an_advisory_on_the_geometry_chip(
        self, qtbot, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """T-B b3: path_zenith_rad set, then ground_range_m (a second viewing door)."""
        window = _complete_window(qtbot, monkeypatch)
        opened = _capture_modals(monkeypatch)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, "geometry.path_zenith_rad", "17")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, "geometry.ground_range_m", "300000")
        assert opened == []
        assert _chip_status(window, "geometry") == "err"
        assert _chip_status(window, "optics") == "stale"
        assert window.statusBar().currentMessage().startswith("Geometry conflict")
        assert window.right_rail.messages.has_error()

    def test_over_constrained_group_is_an_advisory_naming_the_members(
        self, qtbot, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """Reached the way YAML / console / a config file reach it: past the door guard."""
        window = _complete_window(qtbot, monkeypatch)
        opened = _capture_modals(monkeypatch)
        window.sensor.set("optics.focal_length_m", 1.5)  # aperture 0.3, f/4 → disagrees
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window._evaluate_now()  # noqa: SLF001
        assert opened == []
        assert _chip_status(window, "optics") == "err"
        assert _chip_status(window, "geometry") == "stale"
        status = window.statusBar().currentMessage()
        assert "'fnumber'" in status and "optics.f_number" in status

    def test_transmission_mode_without_elements_is_an_advisory_pointing_at_the_tab(
        self, qtbot, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """T-B b10: optics.transmission_input_mode = key_elements with no element."""
        window = _complete_window(qtbot, monkeypatch)
        opened = _capture_modals(monkeypatch)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_choose(window, "optics.transmission_input_mode", "key_elements")
        assert opened == []
        assert _chip_status(window, "optics") == "err"
        assert "Transmission tab" in window.statusBar().currentMessage()

    def test_cal_point_mode_conflict_is_an_advisory_on_the_calibration_chip(
        self, qtbot, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """T-B b9: the routing seam, driven with the stage's own error type."""
        from radiant.calibration.errors import CalibrationModeConflictError

        window = _complete_window(qtbot, monkeypatch)
        opened = _capture_modals(monkeypatch)
        window._on_eval_failed(  # noqa: SLF001 — the worker's failure slot
            CalibrationModeConflictError(
                "calibration.cal_temp_low_K is set, but calibration.cal_point_mode = "
                "'flux_fraction'."
            )
        )
        assert opened == []
        assert _chip_status(window, "calibration") == "err"
        assert _chip_status(window, "readout") == "stale"
        assert "Calibration panel" in window.statusBar().currentMessage()


class TestF10TabulatedWithoutFiles:
    """F-10: a `tabulated` model with no files was announced in the status bar as
    "The atmosphere library does not cover this scene" — the loader raised the
    class the coverage predicate treats wholesale as a refusal."""

    def test_missing_files_read_as_an_incomplete_config_naming_the_file(
        self, qtbot, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """T-B b6: complete configuration, then atmosphere.model = tabulated."""
        window = _complete_window(qtbot, monkeypatch)
        opened = _capture_modals(monkeypatch)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_choose(window, "atmosphere.model", "tabulated")
        assert opened == []
        status = window.statusBar().currentMessage()
        assert status.startswith("Config incomplete — set atmosphere.tabulated_transmittance_file")
        assert "does not cover" not in status
        assert _chip_status(window, "atmosphere") == "err"
        assert _chip_status(window, "optics") == "stale"


class TestF12FailuresTitledByCause:
    """F-12: every evaluation failure was titled *Parameter Rejected — Cannot set
    "evaluate"*, and on a blank config the text was the configuration-set
    wrapper's ("Configuration 'Configuration 1' … configured values are [] …")."""

    def test_a_genuine_evaluation_failure_is_titled_as_one(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from radiant.core.exceptions import CoreValidationError

        window = _complete_window(qtbot, monkeypatch)
        opened = _capture_modals(monkeypatch)
        window._on_eval_failed(CoreValidationError("some genuine rejection"))  # noqa: SLF001
        assert len(opened) == 1
        dialog = opened[0]
        assert dialog.windowTitle() == "Evaluation Failed"
        assert dialog.header_text == "The configuration did not evaluate"
        assert "evaluate”" not in dialog.header_text

    def test_a_single_model_session_never_shows_the_configuration_set_wrapper(
        self, qtbot, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        window = _blank_window(qtbot)
        _capture_modals(monkeypatch)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, "geometry.sensor_altitude_m", "500000")
        error = window.right_rail.messages.error
        assert error is not None
        text = str(error)
        assert "configured values are" not in text
        assert "Configuration 1" not in text
        assert text.startswith("Required parameter ")

    def test_unwrap_walks_every_wrapper_layer(self) -> None:
        from radiant.api.config_set import ConfigSetError
        from radiant.core.parameters import RequiredParameterError
        from radiant.gui.main_window import RADIANTMainWindow

        root = RequiredParameterError("Required parameter 'x' is not set.", param="x")
        inner = ConfigSetError(what="inner", why="w", action="a")
        inner.__cause__ = root
        outer = ConfigSetError(what="outer", why="w", action="a")
        outer.__cause__ = inner
        assert RADIANTMainWindow._underlying(outer) is root  # noqa: SLF001


class TestF21BandEdgesAdvisory:
    """F-21: widening a band upward passed through a state that failed with an
    internal-grid message blaming emissivity, as a modal."""

    def test_inverted_band_is_an_advisory_naming_the_edges(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """J-1.3 step 29: filter_min_um = 8 while filter_max_um is still 5."""
        from radiant.api.errors import SpectralBandError

        window = _complete_window(qtbot, monkeypatch)
        opened = _capture_modals(monkeypatch)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, "spectral_integration.filter_min_um", "8")
        assert opened == []
        assert _chip_status(window, "spectral_integration") == "err"
        assert _chip_status(window, "source") == "stale"
        status = window.statusBar().currentMessage()
        assert "filter_min_um (8 µm)" in status and "filter_max_um (5 µm)" in status
        assert "emissivity" not in status
        assert isinstance(window.right_rail.messages.error, SpectralBandError)
        # The second edit of the widening completes it.
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, "spectral_integration.filter_max_um", "12")
        assert opened == []
        assert _chip_status(window, "spectral_integration") in ("ok", "warn")


class TestF44BareLaunchShowsWelcome:
    """F-44: `radiant gui` handed the window a blank Sensor, so the welcome screen
    appeared only after File ▸ New. The CLI half is pinned in cli/tests (gui may not
    import cli); this pins the window contract the CLI now relies on."""

    def test_launch_gui_with_no_document_opens_on_the_welcome_screen(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from PySide6.QtWidgets import QApplication

        from radiant.gui.app import launch_gui

        assert launch_gui(config_set=None) == 0  # pytest-qt owns the loop: returns at once
        windows = [w for w in QApplication.topLevelWidgets() if isinstance(w, RADIANTMainWindow)]
        assert windows, "launch_gui must have shown a main window"
        window = windows[-1]
        qtbot.addWidget(window)
        assert window.is_welcome()
        assert window.sensor is None
        assert "template" in window.statusBar().currentMessage()


class TestF47AdvisoryNamesTheOwningPanel:
    """F-47: the required-parameter advisory reddened the Spectral chip for
    spectral_integration.integration_time_s, and the Spectral form has no such field —
    it lives on Readout ▸ Acquisition."""

    def test_integration_time_advisory_points_at_readout(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _blank_window(qtbot)
        opened = _capture_modals(monkeypatch)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            for dotpath, text in _COMPLETE:
                if dotpath != "spectral_integration.integration_time_s":
                    _dialog_set(window, dotpath, text)
        assert opened == []
        status = window.statusBar().currentMessage()
        assert "set spectral_integration.integration_time_s on the Readout panel" in status
        assert _chip_status(window, "readout") == "err"
        assert _chip_status(window, "spectral_integration") == "stale"

    def test_owning_stage_is_read_from_the_forms(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _blank_window(qtbot)
        center = window.central_canvas.stage_center
        assert center.stage_owning_field("spectral_integration.integration_time_s") == "readout"
        assert center.stage_owning_field("detector.pixel_pitch_x_um") == "detector"
        assert center.stage_owning_field("spectral_integration.filter_min_um") == (
            "spectral_integration"
        )
