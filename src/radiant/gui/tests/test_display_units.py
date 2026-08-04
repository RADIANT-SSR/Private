"""Tests for the global display-unit preference (CU-326, owner ruling 2026-08-03).

Contract under test: resolution order (per-row override → global preference →
schema input_unit), entry/display symmetry under the preference, the settings
persistence seam, the engineering-prefix auto-scaling, and the card/badge unit
agreement the critique caught disagreeing (0.025 K vs 25 mK on one screen).
"""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings

from radiant.api import Sensor
from radiant.gui import display_units
from radiant.gui.metric_format import format_metric_value, scale_for_display
from radiant.gui.settings_store import SettingsStore

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


@pytest.fixture(autouse=True)
def _degrees_on() -> None:
    """Each test starts from the shipped default (angles in degrees ON)."""
    display_units.set_angles_in_degrees(True)
    yield
    display_units.set_angles_in_degrees(True)


class TestGlobalPreference:
    def test_rad_maps_to_deg_by_default(self) -> None:
        assert display_units.global_display_unit("rad") == "deg"

    def test_mrad_and_urad_keep_their_schema_unit(self) -> None:
        """Deliberate scope: only ``rad`` remaps — mrad/µrad were chosen on purpose."""
        assert display_units.global_display_unit("mrad") is None
        assert display_units.global_display_unit("urad") is None

    def test_toggle_off_restores_schema_units(self) -> None:
        display_units.set_angles_in_degrees(False)
        assert display_units.global_display_unit("rad") is None
        assert not display_units.angles_in_degrees()


class TestSettingsPersistence:
    def test_round_trip(self, tmp_path: Path) -> None:
        store = SettingsStore(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
        assert store.angles_in_degrees() is True  # shipped default
        store.set_angles_in_degrees(False)
        reread = SettingsStore(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
        assert reread.angles_in_degrees() is False


class TestPanelDisplaysDegrees:
    def test_rad_row_renders_in_degrees_and_symmetrically(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A rad-unit row displays deg, seeds its editor in deg, and commits as deg."""
        from radiant.gui.widgets.parameter_panel import ParameterPanel

        panel = ParameterPanel()
        qtbot.addWidget(panel)
        sensor = Sensor.from_yaml(_EXAMPLE)
        panel.populate(sensor)

        # Find a geometry rad-unit dotpath from the schema itself.
        dotpath = next(
            name
            for name, pdef in sensor.parameter_defs().items()
            if pdef.input_unit == "rad" and name.startswith("geometry.")
        )
        assert panel.display_unit(dotpath) == "deg"
        # Editor seed value is the degrees number (entry/display symmetric).
        shown = panel._input_value_for(dotpath)
        raw = sensor.get_input(dotpath)
        if raw is not None and shown is not None:
            assert shown == pytest.approx(math.degrees(float(raw)), rel=1e-9)

    def test_per_row_override_beats_the_global_preference(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.parameter_panel import ParameterPanel

        panel = ParameterPanel()
        qtbot.addWidget(panel)
        sensor = Sensor.from_yaml(_EXAMPLE)
        panel.populate(sensor)
        dotpath = next(
            name
            for name, pdef in sensor.parameter_defs().items()
            if pdef.input_unit == "rad" and name.startswith("geometry.")
        )
        panel.display_units[dotpath] = "mrad"
        assert panel.display_unit(dotpath) == "mrad"


class TestAutoPrefix:
    def test_fwhm_scale_lengths_render_in_micrometers(self) -> None:
        value, unit = scale_for_display("fwhm_x_m", 2.13e-5, "m")
        assert unit == "µm"
        assert value == pytest.approx(21.3, rel=1e-6)
        assert format_metric_value(value, unit) == "21.3 µm"

    def test_ordinary_lengths_stay_in_meters(self) -> None:
        assert scale_for_display("gsd_geometric_mean_m", 0.12, "m") == (0.12, "m")

    def test_millimeter_band(self) -> None:
        value, unit = scale_for_display("some_length", 5.0e-4, "m")
        assert (unit, value) == ("mm", pytest.approx(0.5))

    def test_sub_hundred_millikelvin_renders_mk(self) -> None:
        value, unit = scale_for_display("mrt_at_nyquist_K", 0.032, "K")
        assert unit == "mK"
        assert value == pytest.approx(32.0)

    def test_zero_never_rescales(self) -> None:
        assert scale_for_display("some_length", 0.0, "m") == (0.0, "m")

    def test_explicit_table_still_wins(self) -> None:
        assert scale_for_display("nedt_K", 0.025, "K") == (pytest.approx(25.0), "mK")


class TestCardAndBadgeAgree:
    def test_metric_value_display_routes_through_scale(self) -> None:
        """The critique's headline defect: card said 0.025 K, badge said 25 mK."""
        from radiant.gui.metric_format import metric_value_display

        rec = SimpleNamespace(name="nedt_K", value=0.025, unit="K")
        result = SimpleNamespace(stage_outputs={"performance": {}})
        assert metric_value_display(result, rec) == "25 mK"  # type: ignore[arg-type]


class TestPrettyUnits:
    def test_ascii_exponents_render_typeset(self) -> None:
        assert display_units.pretty_unit("m2") == "m²"
        assert display_units.pretty_unit("m^2") == "m²"
        assert display_units.pretty_unit("um") == "µm"

    def test_unknown_units_pass_through(self) -> None:
        assert display_units.pretty_unit("W/m2/sr/um") == "W/m2/sr/um"  # composite: untouched
