"""The tolerance boxes speak the parameter's displayed unit (walkthrough item 2).

Before this, the Monte-Carlo tolerance fields were unlabelled and their numbers
went to ``Sensor.set_tolerance`` raw — so a target altitude displayed in km took
its spread in metres, with nothing on screen saying so. The operator had to know
the schema's input unit and convert in their head, which is exactly what the
display-unit rule forbids.

:mod:`radiant.gui.tests.test_tolerance_units` pins the conversion arithmetic.
This module pins the wiring: what the dialog *shows* beside each box, and that
what is typed in the shown unit is what gets stored in the input unit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog  # noqa: E402

_REPO = Path(__file__).resolve()
while not (_REPO / "pyproject.toml").exists():
    _REPO = _REPO.parent
_EXAMPLE = _REPO / "examples" / "mwir_leo_minimal.yaml"

# The parameter from the walkthrough screenshot: metres canonical, km a natural display.
_ALTITUDE = "geometry.target_altitude_m"


def _dialog(qtbot, dotpath: str, display_unit: str | None = None):  # type: ignore[no-untyped-def]
    sensor = Sensor.from_yaml(_EXAMPLE)
    dialog = ParameterEditorDialog(
        sensor, dotpath, lambda d, u: None, display_unit=display_unit
    )
    qtbot.addWidget(dialog)
    return sensor, dialog


class TestUnitSuffixIsShown:
    def test_dimensional_field_states_its_unit(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        _sensor, dialog = _dialog(qtbot, _ALTITUDE)
        dialog._tol_distribution.setCurrentText("gaussian")  # noqa: SLF001
        assert dialog._tol_units["std"].text() == "m"  # noqa: SLF001

    def test_suffix_follows_the_chosen_display_unit(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Open the row in km and the spread is stated in km, not metres."""
        _sensor, dialog = _dialog(qtbot, _ALTITUDE, display_unit="km")
        dialog._tol_distribution.setCurrentText("gaussian")  # noqa: SLF001
        assert dialog._tol_units["std"].text() == "km"  # noqa: SLF001

    def test_suffix_tracks_the_unit_combo(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Switching the unit combo relabels the tolerance box in the same breath."""
        _sensor, dialog = _dialog(qtbot, _ALTITUDE)
        dialog._tol_distribution.setCurrentText("gaussian")  # noqa: SLF001
        combo = dialog._unit_combo  # noqa: SLF001
        assert combo is not None
        index = combo.findData("km")
        assert index >= 0, "km must be an offered display unit for an altitude in m"
        combo.setCurrentIndex(index)
        assert dialog._tol_units["std"].text() == "km"  # noqa: SLF001

    def test_log_normal_sigma_is_not_labelled_as_a_length(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """σ is a dimensionless shape parameter — labelling it 'm' would be a lie."""
        _sensor, dialog = _dialog(qtbot, _ALTITUDE, display_unit="km")
        dialog._tol_distribution.setCurrentText("log_normal")  # noqa: SLF001
        assert dialog._tol_units["sigma"].text() == "(shape, ×nominal)"  # noqa: SLF001


class TestEnteredValueIsStoredInInputUnits:
    def test_km_spread_is_stored_in_metres(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Typing 1 beside 'km' stores a 1000 m spread, not a 1 m one."""
        sensor, dialog = _dialog(qtbot, _ALTITUDE, display_unit="km")
        dialog._tol_distribution.setCurrentText("gaussian")  # noqa: SLF001
        dialog._tol_params["std"].setText("1")  # noqa: SLF001
        dialog.apply(close=False)
        tol = sensor.tolerances()[_ALTITUDE]
        assert tol.params["std"] == pytest.approx(1000.0, rel=1e-9)

    def test_uniform_bounds_are_stored_in_metres(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor, dialog = _dialog(qtbot, _ALTITUDE, display_unit="km")
        dialog._tol_distribution.setCurrentText("uniform")  # noqa: SLF001
        dialog._tol_params["low"].setText("29")  # noqa: SLF001
        dialog._tol_params["high"].setText("31")  # noqa: SLF001
        dialog.apply(close=False)
        tol = sensor.tolerances()[_ALTITUDE]
        assert tol.params["low"] == pytest.approx(29_000.0, rel=1e-9)
        assert tol.params["high"] == pytest.approx(31_000.0, rel=1e-9)

    def test_input_unit_display_is_unchanged(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Regression guard: with no unit switch the number passes through as-is."""
        sensor, dialog = _dialog(qtbot, _ALTITUDE)
        dialog._tol_distribution.setCurrentText("gaussian")  # noqa: SLF001
        dialog._tol_params["std"].setText("250")  # noqa: SLF001
        dialog.apply(close=False)
        assert sensor.tolerances()[_ALTITUDE].params["std"] == pytest.approx(250.0, rel=1e-9)

    def test_log_normal_sigma_passes_through_unconverted(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor, dialog = _dialog(qtbot, _ALTITUDE, display_unit="km")
        dialog._tol_distribution.setCurrentText("log_normal")  # noqa: SLF001
        dialog._tol_params["sigma"].setText("0.25")  # noqa: SLF001
        dialog.apply(close=False)
        assert sensor.tolerances()[_ALTITUDE].params["sigma"] == pytest.approx(0.25, rel=1e-9)


class TestExistingToleranceIsShownInDisplayUnits:
    def test_stored_metres_prefill_as_km(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A 1000 m stored spread opens as '1' when the row is displaying km."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_tolerance(_ALTITUDE, "gaussian", std=1000.0)
        dialog = ParameterEditorDialog(
            sensor, _ALTITUDE, lambda d, u: None, display_unit="km"
        )
        qtbot.addWidget(dialog)
        assert float(dialog._tol_params["std"].text()) == pytest.approx(1.0, rel=1e-9)  # noqa: SLF001

    def test_round_trip_open_and_apply_is_lossless(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Opening in km and re-applying must not rescale the stored spread."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_tolerance(_ALTITUDE, "gaussian", std=1000.0)
        dialog = ParameterEditorDialog(
            sensor, _ALTITUDE, lambda d, u: None, display_unit="km"
        )
        qtbot.addWidget(dialog)
        dialog.apply(close=False)
        assert sensor.tolerances()[_ALTITUDE].params["std"] == pytest.approx(1000.0, rel=1e-9)
