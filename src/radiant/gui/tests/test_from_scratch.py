"""Tests for the from-scratch workflow (owner bug report 2026-07-17).

A bare launch (or File → New) must yield an **editable** blank configuration:
the editor dialog opens on unresolvable configs, accepts valid first values
(the config's incompleteness is not the value's fault), still rejects values
that are wrong in themselves (bounds/enum — Rule 16), and Evaluate remains the
surface that reports what is missing.
"""

from __future__ import annotations

import warnings

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.core.exceptions import RadiantError  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog  # noqa: E402


class TestBareLaunch:
    # The CLI-loader assertion (blank Sensor for no config) lives with the
    # CLI tests — src/radiant/cli/tests/test_gui_cli.py — because gui code
    # (tests included) may not import radiant.cli (import table; CU-158).

    def test_blank_window_is_editable(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = RADIANTMainWindow(Sensor())
        qtbot.addWidget(window)
        # Sensor-gated actions are live; the tree is populated with unset rows.
        assert window.action("run.evaluate").isEnabled()
        assert "optics.aperture_diameter_m" in window._parameter_panel._items  # noqa: SLF001


class TestBootstrapEditing:
    def test_dialog_opens_and_accepts_first_value(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor()
        dialog = ParameterEditorDialog(sensor, "optics.aperture_diameter_m", lambda *a: None)
        qtbot.addWidget(dialog)  # construction itself was the crash
        canonical, rejection, unexpected = dialog._try_resolve(0.3, None)  # noqa: SLF001
        assert rejection is None and unexpected is None

    def test_bad_values_still_rejected_on_blank_config(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor()
        dialog = ParameterEditorDialog(sensor, "optics.aperture_diameter_m", lambda *a: None)
        qtbot.addWidget(dialog)
        _c, rejection, _u = dialog._try_resolve(-5.0, None)  # noqa: SLF001
        assert rejection is not None  # Rule 16: wrong is wrong, incomplete or not
        enum_dialog = ParameterEditorDialog(sensor, "atmosphere.model", lambda *a: None)
        qtbot.addWidget(enum_dialog)
        assert enum_dialog._validate_value_shallow("marshmallow", None) is not None  # noqa: SLF001

    def test_full_from_scratch_config_builds_and_evaluates(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The complete journey: blank sensor → set values (the dialog's accept path
        per parameter) → Evaluate succeeds once required values exist."""
        sensor = Sensor()
        required = {
            "optics.aperture_diameter_m": 0.3,
            "optics.f_number": 4.0,
            "detector.pixel_pitch_x_um": 18.0,
            "detector.pixel_pitch_y_um": 18.0,
            "detector.qe_value": 0.7,
            "spectral_integration.filter_min_um": 3.4,
            "spectral_integration.filter_max_um": 5.0,
            "spectral_integration.integration_time_s": 0.005,
            "source.target.temperature": 300.0,
            "source.target.emissivity": 0.95,
            "geometry.sensor_altitude_m": 500000.0,
        }
        for dotpath, value in required.items():
            dialog = ParameterEditorDialog(sensor, dotpath, lambda *a: None)
            qtbot.addWidget(dialog)
            _c, rejection, unexpected = dialog._try_resolve(value, None)  # noqa: SLF001
            assert rejection is None and unexpected is None, f"{dotpath} rejected: {rejection}"
            sensor.set(dotpath, value)  # the accept path's one API call
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                result = sensor.evaluate()
            except RadiantError as exc:
                # If the minimal set above is short a required param, the error
                # must be actionable enough to continue from scratch.
                pytest.fail(f"from-scratch evaluate failed actionably short: {exc}")
        assert result.metrics["snr"] > 0
