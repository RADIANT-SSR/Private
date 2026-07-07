"""Integration: Gap 32 — electronics MTF enters both spatial paths.

Rule 4: readout.electronics_sigma_um must degrade the PSF-path MTF
(x-axis kernel) AND appear as an analytic term in the MTF product path,
with the dual-path consistency check still passing.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.session import RadiantSession

SIGMA_UM = 9.0


def _run(sigma_um: float | None):
    wl = np.linspace(3.5, 5.0, 300)
    session = RadiantSession(wavelength_um=wl)
    p = session.default_params()
    p.set("source.target.temperature", 300.0)
    p.set("source.target.emissivity", 0.95)
    p.set("source.target.is_hot_target", True)
    p.set("optics.aperture_diameter_m", 0.30)
    p.set("optics.focal_length_m", 1.20)
    p.set("optics.transmission_scalar", 0.70)
    p.set("detector.pixel_pitch_x_um", 18.0)
    p.set("detector.pixel_pitch_y_um", 18.0)
    p.set("detector.qe_value", 0.70)
    p.set("detector.dark_rate_e_per_s", 100.0)
    p.set("geometry.sensor_altitude_m", 8000.0)
    p.set("atmosphere.standard_atmosphere", "midlat_summer")
    p.set("spectral_integration.filter_min_um", 3.5)
    p.set("spectral_integration.filter_max_um", 5.0)
    p.set("spectral_integration.integration_time_s", 0.005)
    p.set("readout.read_noise_e_rms", 5.0)
    p.set("readout.gain_e_per_dn", 32.0)
    p.set("readout.adc_bits", 16)
    if sigma_um is not None:
        p.set("readout.electronics_sigma_um", sigma_um)
    p.resolve()
    return session.run(p)


@pytest.fixture(scope="module")
def baseline():
    return _run(None)


@pytest.fixture(scope="module")
def with_elec():
    return _run(SIGMA_UM)


@pytest.mark.level2
class TestElectronicsMtfChain:
    def test_product_term_present_and_degrading(self, with_elec) -> None:
        terms = with_elec.state.mtf_terms
        assert "mtf_electronics_x" in terms
        assert terms["mtf_electronics_x"].min() < 0.9
        np.testing.assert_array_equal(terms["mtf_electronics_y"], 1.0)

    def test_baseline_term_is_unity(self, baseline) -> None:
        np.testing.assert_array_equal(baseline.state.mtf_terms["mtf_electronics_x"], 1.0)

    def test_psf_path_degraded_x_only(self, baseline, with_elec) -> None:
        """Kernel blurs x; y MTF must be unchanged (Rule 4 both-paths)."""
        base = baseline.stage_outputs["performance"]
        elec = with_elec.stage_outputs["performance"]
        assert with_elec.metrics["mtf_at_nyquist"] < baseline.metrics["mtf_at_nyquist"]
        np.testing.assert_allclose(elec["mtf_y"], base["mtf_y"], atol=1e-10)

    def test_kernel_in_convolution_history(self, with_elec) -> None:
        epsf = with_elec.stage_outputs["performance"]["effective_psf"]
        assert any("electronics" in h for h in epsf.convolution_history)

    def test_dual_path_consistency_holds(self, with_elec) -> None:
        """Electronics is NOT excluded from the consistency check."""
        cons = with_elec.stage_outputs["performance"]["dual_path_consistency"]
        assert cons.passed_x and cons.passed_y, f"dual-path consistency failed: {cons}"
