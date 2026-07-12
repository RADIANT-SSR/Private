"""In-chain point-source detection range (Gap 77).

PerformanceStage bisects for the range where SNR falls to
performance.detection_snr_threshold, inverse-square with constant
atmospheric extinction. Only computed in the point-source regime.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from radiant.api.session import RadiantSession

WL = np.linspace(3.5, 5.0, 200)


def _point_source(atmosphere: str = "midlat_summer", threshold: float = 5.0, regime="point_source"):
    session = RadiantSession(wavelength_um=WL)
    p = session.default_params()
    p.set("source.target.temperature", 500.0)
    p.set("source.target.emissivity", 0.95)
    p.set("source.target.projected_area_m2", 1.0)
    p.set("geometry.target_range_m", 50_000.0)
    p.set("source.regime_override", regime)
    p.set("source.background.temperature", 250.0)
    p.set("source.background.emissivity", 0.95)
    p.set("optics.aperture_diameter_m", 0.30)
    p.set("optics.focal_length_m", 1.20)
    p.set("optics.transmission_scalar", 0.70)
    p.set("detector.pixel_pitch_x_um", 18.0)
    p.set("detector.pixel_pitch_y_um", 18.0)
    p.set("detector.qe_value", 0.70)
    p.set("detector.dark_rate_e_per_s", 100.0)
    p.set("geometry.sensor_altitude_m", 8000.0)
    if atmosphere == "exo":
        p.set("atmosphere.model", "exo")
    else:
        p.set("atmosphere.standard_atmosphere", atmosphere)
    p.set("spectral_integration.filter_min_um", 3.5)
    p.set("spectral_integration.filter_max_um", 5.0)
    p.set("spectral_integration.integration_time_s", 0.001)
    p.set("readout.read_noise_e_rms", 5.0)
    p.set("readout.gain_e_per_dn", 1.0)
    p.set("readout.adc_bits", 16)
    p.set("readout.full_well_capacity_e", 5.0e7)
    p.set("performance.detection_snr_threshold", threshold)
    p.resolve()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return session.run(p)


@pytest.mark.level2
class TestDetectionRangeInChain:
    def test_metric_present_and_converges_to_threshold(self) -> None:
        result = _point_source(threshold=5.0)
        assert "detection_range_m" in result.metrics
        dr = result.stage_outputs["performance"]["detection_range_result"]
        assert dr.ok
        assert dr.snr_at_range == pytest.approx(5.0, rel=1e-3)

    def test_extinction_shortens_range_vs_vacuum(self) -> None:
        """A real atmosphere (α > 0) detects at shorter range than vacuum."""
        atm = _point_source(atmosphere="midlat_summer")
        vac = _point_source(atmosphere="exo")
        assert atm.metrics["detection_range_m"] < vac.metrics["detection_range_m"]

    def test_vacuum_follows_inverse_square(self) -> None:
        """In vacuum, detection range = R_ref · √(SNR_ref / threshold)."""
        import math

        r = _point_source(atmosphere="exo", threshold=5.0)
        snr_ref = r.metrics["snr"]
        expected = 50_000.0 * math.sqrt(snr_ref / 5.0)
        assert r.metrics["detection_range_m"] == pytest.approx(expected, rel=1e-2)

    def test_higher_threshold_shortens_range(self) -> None:
        lo = _point_source(threshold=5.0).metrics["detection_range_m"]
        hi = _point_source(threshold=20.0).metrics["detection_range_m"]
        assert hi < lo

    def test_not_computed_in_extended_regime(self) -> None:
        result = _point_source(regime="extended")
        assert "detection_range_m" not in result.metrics
