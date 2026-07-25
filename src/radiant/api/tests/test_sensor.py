"""Tests for the Sensor high-level API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from radiant.api.sensor import Sensor
from radiant.io.results import ChainResult

# Path to the minimal MWIR config shipped with the repo.
_MWIR_YAML = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


@pytest.fixture()
def sensor() -> Sensor:
    """Return a Sensor loaded from the minimal MWIR config."""
    return Sensor.from_yaml(_MWIR_YAML)


# ------------------------------------------------------------------
# Construction
# ------------------------------------------------------------------


@pytest.mark.level1
class TestConstruction:
    def test_from_yaml(self) -> None:
        s = Sensor.from_yaml(_MWIR_YAML)
        assert isinstance(s, Sensor)

    def test_from_yaml_custom_wl_points(self) -> None:
        s = Sensor.from_yaml(_MWIR_YAML, wavelength_points=100)
        assert s._wl_points == 100

    def test_from_dict(self) -> None:
        cfg: dict[str, Any] = {
            "source": {"target": {"temperature": 300.0, "emissivity": 0.95}},
            "atmosphere": {"standard_atmosphere": "midlat_summer"},
            "geometry": {"sensor_altitude_m": 8000.0},
            "optics": {
                "aperture_diameter_m": 0.30,
                "focal_length_m": 1.20,
                "transmission_scalar": 0.70,
            },
            "detector": {
                "pixel_pitch_x_um": 18.0,
                "pixel_pitch_y_um": 18.0,
                "qe_value": 0.70,
                "dark_rate_e_per_s": 100.0,
            },
            "spectral_integration": {
                "filter_min_um": 3.5,
                "filter_max_um": 5.0,
                "integration_time_s": 0.005,
            },
            "readout": {
                "read_noise_e_rms": 5.0,
                "gain_e_per_dn": 1.0,
                "adc_bits": 16,
            },
        }
        s = Sensor.from_dict(cfg)
        assert isinstance(s, Sensor)

    def test_bare_sensor(self) -> None:
        s = Sensor()
        assert isinstance(s, Sensor)


# ------------------------------------------------------------------
# Parameter access
# ------------------------------------------------------------------


@pytest.mark.level1
class TestParameterAccess:
    def test_set_and_get(self, sensor: Sensor) -> None:
        sensor.set("optics.aperture_diameter_m", 0.50)
        val = sensor.get("optics.aperture_diameter_m")
        assert val == pytest.approx(0.50, rel=1e-10)

    def test_set_returns_self(self, sensor: Sensor) -> None:
        ret = sensor.set("optics.aperture_diameter_m", 0.40)
        assert ret is sensor

    def test_set_many(self, sensor: Sensor) -> None:
        sensor.set_many(
            {
                "optics.aperture_diameter_m": 0.40,
                "detector.qe_value": 0.80,
            }
        )
        assert sensor.get("optics.aperture_diameter_m") == pytest.approx(0.40, rel=1e-10)
        assert sensor.get("detector.qe_value") == pytest.approx(0.80, rel=1e-10)

    def test_get_input(self, sensor: Sensor) -> None:
        val = sensor.get_input("optics.aperture_diameter_m")
        assert val == pytest.approx(0.30, rel=1e-10)

    def test_resolved_carries_structured_provenance(self, sensor: Sensor) -> None:
        """CU-105: Sensor.resolved returns a ResolvedValue with provenance, no text parse."""
        from radiant.core.parameters import Provenance, ResolvedValue

        sensor.set("optics.aperture_diameter_m", 0.42)
        rv = sensor.resolved("optics.aperture_diameter_m")
        assert isinstance(rv, ResolvedValue)
        assert rv.provenance is Provenance.USER_SET
        assert rv.value == pytest.approx(0.42, rel=1e-10)

    def test_provenance_convenience_accessor(self, sensor: Sensor) -> None:
        """CU-105: Sensor.provenance returns just the Provenance enum."""
        from radiant.core.parameters import Provenance

        sensor.set("optics.aperture_diameter_m", 0.42)
        assert sensor.provenance("optics.aperture_diameter_m") is Provenance.USER_SET

    def test_reset(self, sensor: Sensor) -> None:
        sensor.set("optics.transmission_scalar", 0.50)
        sensor.reset("optics.transmission_scalar")
        # After reset, should use config file value (0.70) or default
        val = sensor.get("optics.transmission_scalar")
        assert val == pytest.approx(0.70, rel=1e-10)

    def test_set_unknown_param_raises(self, sensor: Sensor) -> None:
        with pytest.raises(KeyError, match="Unknown parameter"):
            sensor.set("bogus.param", 42)

    def test_reset_unknown_param_raises(self, sensor: Sensor) -> None:
        """CU-046: a typo'd dotpath in reset() raises like set() does.

        Previously reset() silently no-oped on unknown names — the user
        believed a parameter was reverted when nothing happened.
        """
        with pytest.raises(KeyError, match="Unknown parameter"):
            sensor.reset("bogus.param")


@pytest.mark.level1
class TestProvenanceAndInputSeams:
    """CU-208: public source= / inputs() / resolve() seams."""

    def test_set_source_label_reaches_provenance(self, sensor: Sensor) -> None:
        from radiant.core.parameters import Provenance

        sensor.set("optics.aperture_diameter_m", 0.42, source="config:MWIR")
        rv = sensor.resolved("optics.aperture_diameter_m")
        assert rv.source == "config:MWIR"
        assert rv.provenance is Provenance.USER_SET

    def test_set_source_default_unchanged(self, sensor: Sensor) -> None:
        sensor.set("optics.aperture_diameter_m", 0.42)
        assert sensor.resolved("optics.aperture_diameter_m").source == "Sensor.set"

    def test_set_source_with_unit_conversion(self, sensor: Sensor) -> None:
        sensor.set("optics.aperture_diameter_m", 42.0, unit="cm", source="config:LWIR")
        assert sensor.get("optics.aperture_diameter_m") == pytest.approx(0.42, rel=1e-10)
        assert sensor.resolved("optics.aperture_diameter_m").source.startswith("config:LWIR")

    def test_set_many_source_label(self, sensor: Sensor) -> None:
        sensor.set_many({"detector.qe_value": 0.8}, source="config:LWIR")
        assert sensor.resolved("detector.qe_value").source == "config:LWIR"
        # Default label unchanged for callers that do not pass one.
        sensor.set_many({"optics.transmission_scalar": 0.6})
        assert sensor.resolved("optics.transmission_scalar").source == "Sensor.set_many"

    def test_inputs_holds_only_explicit_values(self, sensor: Sensor) -> None:
        sensor.set("optics.aperture_diameter_m", 0.42)
        inputs = sensor.inputs()
        assert inputs["optics.aperture_diameter_m"] == pytest.approx(0.42, rel=1e-10)
        # Defaults and derived values do not appear — inputs is a strict subset
        # of the schema (the persistence surface, not the resolved state).
        assert set(inputs) < set(sensor.parameter_defs())
        sensor.reset("optics.aperture_diameter_m")
        assert "optics.aperture_diameter_m" not in sensor.inputs()

    def test_inputs_is_read_only(self, sensor: Sensor) -> None:
        with pytest.raises(TypeError):
            sensor.inputs()["optics.aperture_diameter_m"] = 0.9  # type: ignore[index]

    def test_resolve_is_idempotent_and_chains(self, sensor: Sensor) -> None:
        assert sensor.resolve() is sensor
        first = sensor.get("optics.f_number")
        assert sensor.resolve() is sensor
        assert sensor.get("optics.f_number") == pytest.approx(first, rel=1e-12)

    def test_resolve_surfaces_configuration_error(self, sensor: Sensor) -> None:
        from radiant.core.exceptions import RadiantError

        sensor.set("detector.qe_value", 5.0)  # out of bounds (0–1)
        with pytest.raises(RadiantError):
            sensor.resolve()


# ------------------------------------------------------------------
# Evaluation
# ------------------------------------------------------------------


@pytest.mark.level2
class TestEvaluation:
    def test_evaluate_returns_chain_result(self, sensor: Sensor) -> None:
        result = sensor.evaluate()
        assert isinstance(result, ChainResult)

    def test_evaluate_has_snr(self, sensor: Sensor) -> None:
        result = sensor.evaluate()
        assert "snr" in result.metrics
        snr = result.metrics["snr"]
        assert isinstance(snr, float)
        assert snr > 0.0

    def test_evaluate_has_history(self, sensor: Sensor) -> None:
        result = sensor.evaluate()
        assert len(result.history) > 0
        assert "source" in result.history
        assert "performance" in result.history

    def test_evaluate_deterministic(self, sensor: Sensor) -> None:
        r1 = sensor.evaluate()
        r2 = sensor.evaluate()
        assert r1.metrics["snr"] == pytest.approx(r2.metrics["snr"], rel=1e-12)


# ------------------------------------------------------------------
# Sweep
# ------------------------------------------------------------------


@pytest.mark.level2
class TestSweep:
    def test_sweep_1d(self, sensor: Sensor) -> None:
        result = sensor.sweep(
            "optics.aperture_diameter_m",
            [0.20, 0.30, 0.40],
            metric="snr",
        )
        assert len(result.values) == 3
        assert len(result.metric_values) == 3
        # SNR should increase with aperture
        assert result.metric_values[2] > result.metric_values[0]

    def test_sweep_2d(self, sensor: Sensor) -> None:
        result = sensor.sweep_2d(
            "optics.aperture_diameter_m",
            [0.20, 0.30],
            "spectral_integration.integration_time_s",
            [0.003, 0.005],
            metric="snr",
        )
        assert result.grid.shape == (2, 2)


# ------------------------------------------------------------------
# Clone
# ------------------------------------------------------------------


@pytest.mark.level1
class TestClone:
    def test_clone_is_independent(self, sensor: Sensor) -> None:
        clone = sensor.clone()
        clone.set("optics.aperture_diameter_m", 0.99)
        assert sensor.get("optics.aperture_diameter_m") == pytest.approx(0.30, rel=1e-10)
        assert clone.get("optics.aperture_diameter_m") == pytest.approx(0.99, rel=1e-10)


# ------------------------------------------------------------------
# Summary and explain
# ------------------------------------------------------------------


class TestSummaryExplain:
    @pytest.mark.level1
    def test_summary(self, sensor: Sensor) -> None:
        text = sensor.summary()
        assert "Parameter Summary" in text
        assert "optics" in text

    @pytest.mark.level1
    def test_explain_param(self, sensor: Sensor) -> None:
        text = sensor.explain("optics.aperture_diameter_m")
        assert "aperture_diameter_m" in text
        assert "0.3" in text

    @pytest.mark.level2
    def test_explain_chain(self, sensor: Sensor) -> None:
        text = sensor.explain()
        assert "Chain Walkthrough" in text
        assert "Metrics" in text


class TestSchemaIntrospection:
    """Sensor passthroughs to the ParameterSet introspection surface (Gap 70)."""

    @pytest.mark.level1
    def test_parameter_defs_enumerates_schema(self, sensor: Sensor) -> None:
        defs = sensor.parameter_defs()
        assert "optics.aperture_diameter_m" in defs
        pdef = defs["optics.aperture_diameter_m"]
        assert pdef.dtype is float
        assert pdef.canonical_unit == "m"

    @pytest.mark.level1
    def test_parameter_defs_read_only(self, sensor: Sensor) -> None:
        with pytest.raises(TypeError):
            sensor.parameter_defs()["x"] = None  # type: ignore[index]

    @pytest.mark.level1
    def test_parameter_def_single_lookup(self, sensor: Sensor) -> None:
        pdef = sensor.parameter_def("detector.qe_value")
        assert pdef.name == "detector.qe_value"

    @pytest.mark.level1
    def test_parameter_def_unknown_suggests(self, sensor: Sensor) -> None:
        with pytest.raises(KeyError, match="Did you mean"):
            sensor.parameter_def("optics.aperture_diamter_m")


class TestStageOutputInjection:
    """Gap 68: non-scalar pre-chain inputs reach the chain through Sensor."""

    def _curve(self, sensor: Sensor, value: float) -> Any:
        import numpy as np

        from radiant.core.spectral import SpectralData

        wl = np.linspace(3.5, 5.0, 50)
        return SpectralData(
            name="tau_curve",
            wavelength_um=wl,
            values=np.full_like(wl, value),
            unit="",
            source="test",
        )

    @pytest.mark.level2
    def test_evaluate_one_off_injection(self, sensor: Sensor) -> None:
        sensor.set("optics.transmission_input_mode", "spectral_file")
        result = sensor.evaluate(
            extra_stage_outputs={
                "optics_config": {"transmission_spectral": self._curve(sensor, 0.42)}
            }
        )
        import numpy as np

        np.testing.assert_allclose(result.stage_outputs["optics"]["tau_opt"], 0.42, rtol=1e-9)

    @pytest.mark.level2
    def test_held_injection_used_by_evaluate_and_sweep(self, sensor: Sensor) -> None:
        sensor.set("optics.transmission_input_mode", "spectral_file")
        sensor.set_stage_output("optics_config", "transmission_spectral", self._curve(sensor, 0.42))
        import numpy as np

        r = sensor.evaluate()
        np.testing.assert_allclose(r.stage_outputs["optics"]["tau_opt"], 0.42, rtol=1e-9)

        sw = sensor.sweep("optics.aperture_diameter_m", [0.2, 0.3], metric="snr")
        assert len(sw.metric_values) == 2
        assert all(v > 0 for v in sw.metric_values)

    @pytest.mark.level2
    def test_injection_removable(self, sensor: Sensor) -> None:
        sensor.set("optics.transmission_input_mode", "spectral_file")
        sensor.set_stage_output("optics_config", "transmission_spectral", self._curve(sensor, 0.42))
        sensor.set_stage_output("optics_config", "transmission_spectral", None)
        with pytest.raises(Exception, match="transmission_spectral"):
            sensor.evaluate()


class TestGroundVelocityAndCollapse:
    """Gap 75: orbit-derived ground velocity + collapsed ground-speed pair."""

    @pytest.mark.level1
    def test_orbit_derives_ground_velocity(self, sensor: Sensor) -> None:
        from radiant.core.orbit import ground_track_speed_m_s

        sensor.set("geometry.sensor_altitude_m", 600_000.0)
        sensor.set_ground_velocity_from_orbit()
        assert sensor.get("platform.ground_velocity_m_s") == pytest.approx(
            ground_track_speed_m_s(600_000.0), rel=1e-12
        )

    @pytest.mark.level1
    def test_orbit_requires_altitude(self) -> None:
        from radiant.api.errors import ApiValidationError

        s = Sensor()
        with pytest.raises(ApiValidationError, match="sensor_altitude_m must be set"):
            s.set_ground_velocity_from_orbit()

    @pytest.mark.level1
    def test_set_velocity_derives_speed(self, sensor: Sensor) -> None:
        """Collapse: setting platform.ground_velocity_m_s derives
        geometry.ground_speed_m_s (one physical quantity)."""
        sensor.set("platform.ground_velocity_m_s", 6900.0)
        assert sensor.get("geometry.ground_speed_m_s") == pytest.approx(6900.0, rel=1e-12)

    @pytest.mark.level1
    def test_set_speed_derives_velocity(self, sensor: Sensor) -> None:
        sensor.set("geometry.ground_speed_m_s", 6900.0)
        assert sensor.get("platform.ground_velocity_m_s") == pytest.approx(6900.0, rel=1e-12)

    @pytest.mark.level1
    def test_disagreeing_values_raise(self, sensor: Sensor) -> None:
        from radiant.core.exceptions import RadiantError

        sensor.set("platform.ground_velocity_m_s", 7000.0)
        sensor.set("geometry.ground_speed_m_s", 6500.0)
        with pytest.raises(RadiantError, match="over-constrained"):
            sensor.get("platform.ground_velocity_m_s")

    @pytest.mark.level1
    def test_equal_values_ok(self, sensor: Sensor) -> None:
        sensor.set("platform.ground_velocity_m_s", 7000.0)
        sensor.set("geometry.ground_speed_m_s", 7000.0)
        assert sensor.get("platform.ground_velocity_m_s") == pytest.approx(7000.0, rel=1e-12)

    @pytest.mark.level1
    def test_neither_set_defaults_zero(self, sensor: Sensor) -> None:
        assert sensor.get("platform.ground_velocity_m_s") == 0.0
        assert sensor.get("geometry.ground_speed_m_s") == 0.0


class TestEnumValidation:
    """CU-076: string-mode params reject typos via enum_values."""

    @pytest.mark.level1
    def test_tdi_mode_rejects_invalid(self, sensor: Sensor) -> None:
        from radiant.core.exceptions import RadiantError

        sensor.set("readout.tdi_mode", "Digital")  # wrong case → typo
        with pytest.raises(RadiantError, match="must be one of"):
            sensor.get("readout.tdi_mode")

    @pytest.mark.level1
    def test_tdi_mode_accepts_valid(self, sensor: Sensor) -> None:
        sensor.set("readout.tdi_mode", "digital")
        assert sensor.get("readout.tdi_mode") == "digital"

    @pytest.mark.level1
    def test_noise_regime_rejects_invalid(self, sensor: Sensor) -> None:
        from radiant.core.exceptions import RadiantError

        sensor.set("detector.noise_regime", "temporal_spatial")
        with pytest.raises(RadiantError, match="must be one of"):
            sensor.get("detector.noise_regime")

    @pytest.mark.level1
    def test_noise_regime_accepts_valid(self, sensor: Sensor) -> None:
        sensor.set("detector.noise_regime", "detection")
        assert sensor.get("detector.noise_regime") == "detection"
