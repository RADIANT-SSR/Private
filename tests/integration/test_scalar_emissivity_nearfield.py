"""Integration: Gap 37 — scalar-mode warm optics emit nearfield when declared.

Runs the reference MWIR chain (see test_chain_extended.py) twice:
baseline scalar mode (default ``optics.scalar_emissivity = 0``) and with a
declared train emissivity. Verifies the declared emissivity produces a
nonzero nearfield_shot noise term, increases total noise (lower SNR), and
leaves the signal path untouched. Default behavior is regression-locked.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.session import RadiantSession

FILTER_MIN = 3.5
FILTER_MAX = 5.0
OPTICS_TEMP_K = 293.0
SCALAR_EPS = 0.25  # eps + tau = 0.95 <= 1


def _run(scalar_emissivity: float | None):
    wl = np.linspace(FILTER_MIN, FILTER_MAX, 500)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("source.target.is_hot_target", True)
    params.set("optics.aperture_diameter_m", 0.30)
    params.set("optics.focal_length_m", 1.20)
    params.set("optics.transmission_scalar", 0.70)
    params.set("optics.optics_temperature_K", OPTICS_TEMP_K)
    if scalar_emissivity is not None:
        params.set("optics.scalar_emissivity", scalar_emissivity)
    params.set("detector.pixel_pitch_x_um", 18.0)
    params.set("detector.pixel_pitch_y_um", 18.0)
    params.set("detector.qe_value", 0.70)
    params.set("detector.dark_rate_e_per_s", 100.0)
    params.set("geometry.sensor_altitude_m", 8000.0)
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("spectral_integration.filter_min_um", FILTER_MIN)
    params.set("spectral_integration.filter_max_um", FILTER_MAX)
    params.set("spectral_integration.integration_time_s", 0.005)
    params.set("readout.read_noise_e_rms", 5.0)
    params.set("readout.gain_e_per_dn", 32.0)
    params.set("readout.adc_bits", 16)
    params.resolve()
    return session.run(params)


@pytest.fixture(scope="module")
def baseline():
    return _run(None)


@pytest.fixture(scope="module")
def with_emissivity():
    return _run(SCALAR_EPS)


@pytest.mark.level2
class TestScalarEmissivityNearfield:
    def test_baseline_nearfield_is_zero(self, baseline) -> None:
        """Regression: default scalar mode keeps eps = 0, nearfield dark."""
        budget = baseline.stage_outputs["detector"]["noise_budget_raw"]
        assert budget.terms["nearfield_shot"] == pytest.approx(0.0, abs=1e-12)

    def test_declared_emissivity_produces_nearfield(self, with_emissivity) -> None:
        """Warm lumped train at 293 K in MWIR must emit."""
        budget = with_emissivity.stage_outputs["detector"]["noise_budget_raw"]
        assert budget.terms["nearfield_shot"] > 0.0

    def test_nearfield_irradiance_stored(self, with_emissivity) -> None:
        nf = with_emissivity.stage_outputs["optics"]["nearfield_irradiance_at_fpa"]
        assert float(np.max(nf.values)) > 0.0

    def test_snr_decreases(self, baseline, with_emissivity) -> None:
        """Added background noise must lower SNR, not raise it."""
        assert with_emissivity.metrics["snr"] < baseline.metrics["snr"]

    def test_signal_path_unchanged(self, baseline, with_emissivity) -> None:
        """Declared emissivity affects noise only — never signal throughput."""
        s_base = baseline.stage_outputs["spectral_integration"]["signal_e"]
        s_eps = with_emissivity.stage_outputs["spectral_integration"]["signal_e"]
        assert s_eps == pytest.approx(s_base, rel=1e-12)
