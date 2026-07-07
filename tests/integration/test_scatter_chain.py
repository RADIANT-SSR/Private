"""Integration: Gap 31 — TIS scatter enters both spatial paths (Rule 4)."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from radiant.api.session import RadiantSession

ROUGHNESS_NM = 120.0  # → TIS ≈ 0.117 at 4.25 µm — big enough to see


def _run(roughness_nm: float | None):
    wl = np.linspace(3.5, 5.0, 300)
    session = RadiantSession(wavelength_um=wl)
    p = session.default_params()
    p.set("source.target.temperature", 300.0)
    p.set("source.target.emissivity", 0.95)
    p.set("source.target.is_hot_target", True)
    p.set("optics.aperture_diameter_m", 0.30)
    p.set("optics.focal_length_m", 1.20)
    p.set("optics.transmission_scalar", 0.70)
    if roughness_nm is not None:
        p.set("optics.surface_roughness_nm", roughness_nm)
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
    p.resolve()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return session.run(p)


@pytest.fixture(scope="module")
def baseline():
    return _run(None)


@pytest.fixture(scope="module")
def with_scatter():
    return _run(ROUGHNESS_NM)


@pytest.mark.level2
class TestScatterChain:
    def test_tis_stored(self, with_scatter) -> None:
        tis = with_scatter.stage_outputs["optics"]["scatter_tis"]
        assert 0.10 < tis < 0.13  # ≈ 0.117 at band-center ~4.25 µm

    def test_kernel_in_psf_history(self, with_scatter) -> None:
        epsf = with_scatter.stage_outputs["performance"]["effective_psf"]
        assert any("scatter" in h for h in epsf.convolution_history)

    def test_product_term_present(self, with_scatter, baseline) -> None:
        terms = with_scatter.state.mtf_terms
        assert "mtf_scatter_x" in terms and "mtf_scatter_y" in terms
        assert terms["mtf_scatter_x"].min() < 0.95
        assert "mtf_scatter_x" not in baseline.state.mtf_terms

    def test_mtf_degrades_both_axes(self, baseline, with_scatter) -> None:
        base = baseline.stage_outputs["performance"]
        scat = with_scatter.stage_outputs["performance"]
        assert with_scatter.metrics["mtf_at_nyquist"] < baseline.metrics["mtf_at_nyquist"]
        assert scat["mtf_y"][1:50].max() < base["mtf_y"][1:50].max()

    def test_dual_path_consistency_holds(self, with_scatter) -> None:
        """Scatter is included in (not excluded from) the Rule 4 check."""
        cons = with_scatter.stage_outputs["performance"]["dual_path_consistency"]
        assert cons.passed_x and cons.passed_y, f"consistency failed: {cons}"

    def test_signal_path_unchanged(self, baseline, with_scatter) -> None:
        """TIS redistributes PSF energy; total signal must be identical."""
        s0 = baseline.stage_outputs["spectral_integration"]["signal_e"]
        s1 = with_scatter.stage_outputs["spectral_integration"]["signal_e"]
        assert s1 == pytest.approx(s0, rel=1e-12)
