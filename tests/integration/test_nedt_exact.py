"""Integration: Gap 43 — exact band-integrated NEDT dS/dT.

SpectralIntegrationStage now computes the exact temperature sensitivity of
the in-band signal, dS/dT = ∫ (signal integrand) · (dB/dT)/B dλ, and
PerformanceStage uses it for NEDT (σ / (dS/dT)) instead of the single-λ
Planck-factor approximation. In the narrow-band limit the two agree
exactly; over a wide band they differ by the band curvature of the Planck
function.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.performance.nedt import compute_nedt_from_snr


def _run(fmin: float, fmax: float, target_temp: float = 300.0):
    wl = np.linspace(fmin - 0.2, fmax + 0.2, 400)
    session = RadiantSession(wavelength_um=wl)
    p = session.default_params()
    p.set("source.target.temperature", target_temp)
    p.set("source.target.emissivity", 0.95)
    p.set("optics.aperture_diameter_m", 0.15)
    p.set("optics.focal_length_m", 0.5)
    p.set("optics.transmission_scalar", 0.8)
    p.set("detector.pixel_pitch_x_um", 25.0)
    p.set("detector.pixel_pitch_y_um", 25.0)
    p.set("detector.qe_value", 0.7)
    p.set("detector.dark_rate_e_per_s", 1e6)
    p.set("detector.detector_temperature_K", 77.0)
    p.set("geometry.sensor_altitude_m", 3000.0)
    p.set("spectral_integration.filter_min_um", fmin)
    p.set("spectral_integration.filter_max_um", fmax)
    p.set("spectral_integration.integration_time_s", 0.005)
    p.set("readout.read_noise_e_rms", 300.0)
    p.set("readout.gain_e_per_dn", 100.0)
    p.set("readout.adc_bits", 14)
    p.set("readout.full_well_capacity_e", 5e6)
    p.resolve()
    return session.run(p)


@pytest.mark.level2
class TestExactNedt:
    def test_ds_dt_positive_and_stored(self) -> None:
        res = _run(8.0, 12.0)
        ds_dt = res.stage_outputs["spectral_integration"]["ds_dt_e_per_K"]
        assert ds_dt > 0.0

    def test_narrow_band_matches_single_lambda(self) -> None:
        """Over a very narrow band the exact NEDT == the old approximation."""
        res = _run(9.99, 10.01)
        nedt_exact = res.metrics["nedt_K"]
        snr = res.metrics["snr"]
        nedt_approx = compute_nedt_from_snr(300.0, snr, 10.0).value_K
        assert nedt_exact == pytest.approx(nedt_approx, rel=1e-3)

    def test_wide_band_differs(self) -> None:
        """Over a wide MWIR band the exact and single-λ NEDT differ (band curvature)."""
        res = _run(3.5, 5.0)
        nedt_exact = res.metrics["nedt_K"]
        snr = res.metrics["snr"]
        nedt_approx = compute_nedt_from_snr(300.0, snr, 4.25).value_K
        # A few percent apart, but same order.
        assert nedt_exact != pytest.approx(nedt_approx, rel=1e-3)
        assert nedt_exact == pytest.approx(nedt_approx, rel=0.1)

    def test_nedt_matches_sigma_over_dsdt(self) -> None:
        """NEDT = σ / (dS/dT), with σ = signal_e / SNR."""
        res = _run(8.0, 12.0)
        ds_dt = res.stage_outputs["spectral_integration"]["ds_dt_e_per_K"]
        signal_e = res.stage_outputs["spectral_integration"]["signal_e"]
        snr = res.metrics["snr"]
        noise_e = signal_e / snr
        assert res.metrics["nedt_K"] == pytest.approx(noise_e / ds_dt, rel=1e-9)
