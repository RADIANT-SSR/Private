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

    def test_reset(self, sensor: Sensor) -> None:
        sensor.set("optics.transmission_scalar", 0.50)
        sensor.reset("optics.transmission_scalar")
        # After reset, should use config file value (0.70) or default
        val = sensor.get("optics.transmission_scalar")
        assert val == pytest.approx(0.70, rel=1e-10)

    def test_set_unknown_param_raises(self, sensor: Sensor) -> None:
        with pytest.raises(KeyError, match="Unknown parameter"):
            sensor.set("bogus.param", 42)


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
