"""Integration: Gap 10 — Sensor.solve_for inverse solver.

Verifies the Brent solver recovers a known forward value (round-trip
anchor), respects the bracket contract, and reports actionable errors
when the target is not bracketed.
"""

from __future__ import annotations

import pytest

from radiant.api.sensor import Sensor
from radiant.api.solve import SolveBracketError


def _sensor() -> Sensor:
    s = Sensor(wavelength_points=200)
    s.set_many(
        {
            "source.target.temperature": 300.0,
            "source.target.emissivity": 0.95,
            "source.target.is_hot_target": True,
            "optics.aperture_diameter_m": 0.30,
            "optics.focal_length_m": 1.20,
            "optics.transmission_scalar": 0.70,
            "detector.pixel_pitch_x_um": 18.0,
            "detector.pixel_pitch_y_um": 18.0,
            "detector.qe_value": 0.70,
            "detector.dark_rate_e_per_s": 100.0,
            "geometry.sensor_altitude_m": 8000.0,
            "atmosphere.standard_atmosphere": "midlat_summer",
            "spectral_integration.filter_min_um": 3.5,
            "spectral_integration.filter_max_um": 5.0,
            # Short integration keeps the well unsaturated across the
            # solve bracket — a saturated plateau has no unique root.
            "spectral_integration.integration_time_s": 0.0002,
            "readout.read_noise_e_rms": 5.0,
            "readout.gain_e_per_dn": 32.0,
            "readout.adc_bits": 16,
        }
    )
    return s


@pytest.mark.level2
@pytest.mark.filterwarnings("ignore::UserWarning")
class TestSolveFor:
    def test_round_trip_recovers_known_aperture(self) -> None:
        """Forward-evaluate SNR at D = 0.2 m, then solve back for D."""
        s = _sensor()
        target_snr = float(
            s.clone().set("optics.aperture_diameter_m", 0.20).evaluate().metrics["snr"]
        )
        res = s.solve_for(
            "optics.aperture_diameter_m",
            target_snr,
            bounds=(0.05, 0.60),
            metric="snr",
        )
        assert res.solution == pytest.approx(0.20, rel=1e-4)
        assert res.achieved == pytest.approx(target_snr, rel=1e-4)
        assert res.result.metrics["snr"] == pytest.approx(target_snr, rel=1e-4)

    def test_unbracketed_target_actionable_error(self) -> None:
        s = _sensor()
        with pytest.raises(SolveBracketError, match="does not reach the target"):
            s.solve_for(
                "optics.aperture_diameter_m",
                1e9,  # unreachable SNR
                bounds=(0.05, 0.60),
                metric="snr",
            )

    def test_invalid_bounds_rejected(self) -> None:
        s = _sensor()
        with pytest.raises(SolveBracketError, match="lo < hi"):
            s.solve_for("optics.aperture_diameter_m", 100.0, bounds=(0.6, 0.05))

    def test_evaluation_count_reported(self) -> None:
        s = _sensor()
        target_snr = float(
            s.clone().set("optics.aperture_diameter_m", 0.20).evaluate().metrics["snr"]
        )
        res = s.solve_for(
            "optics.aperture_diameter_m",
            target_snr,
            bounds=(0.05, 0.60),
        )
        assert res.n_evaluations >= 3  # two endpoints + at least the root
        assert res.metric_name == "snr"
