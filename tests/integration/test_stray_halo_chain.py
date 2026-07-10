"""Integration: Gap 60 (partial) — veiling-glare halo enters both spatial paths.

The radiometric pedestal (CU-062) captures the NOISE impact of veiling
glare; this opt-in model captures its SPATIAL impact: the stray fraction
re-imaged as a Gaussian halo, entering the PSF path as a kernel
(1−vgf)·δ + vgf·G(σ) and the MTF product path as the exact Fourier pair
(1−vgf) + vgf·exp(−2π²σ²f²) — Rule 4 on both paths, reusing the Gap-31
TIS scatter builders with vgf as the fraction.

Off by default (``optics.stray.veiling_glare_mtf = 0``): the pedestal-only
historical behavior is bit-identical.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from radiant.api.session import RadiantSession

VGF = 0.05  # 5 % veiling glare — big enough to see on the MTF floor


def _run(*, halo_enabled: bool):
    wl = np.linspace(3.5, 5.0, 300)
    session = RadiantSession(wavelength_um=wl)
    p = session.default_params()
    p.set("source.target.temperature", 300.0)
    p.set("source.target.emissivity", 0.95)
    p.set("source.target.is_hot_target", True)
    p.set("optics.aperture_diameter_m", 0.30)
    p.set("optics.focal_length_m", 1.20)
    p.set("optics.transmission_scalar", 0.70)
    p.set("optics.stray.veiling_glare_fraction", VGF)
    if halo_enabled:
        p.set("optics.stray.veiling_glare_mtf", 1)
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
def pedestal_only():
    """vgf > 0 but the spatial model off — the historical default."""
    return _run(halo_enabled=False)


@pytest.fixture(scope="module")
def with_halo():
    return _run(halo_enabled=True)


@pytest.mark.level2
class TestStrayHaloChain:
    def test_default_off_is_spatially_inert(self, pedestal_only) -> None:
        """Flag off (default): no kernel, no MTF term — pedestal only."""
        epsf = pedestal_only.stage_outputs["performance"]["effective_psf"]
        assert not any("stray" in h for h in epsf.convolution_history)
        assert "mtf_stray_x" not in pedestal_only.state.mtf_terms

    def test_kernel_in_psf_history(self, with_halo) -> None:
        epsf = with_halo.stage_outputs["performance"]["effective_psf"]
        assert any("stray_halo" in h for h in epsf.convolution_history)

    def test_product_term_present_with_vgf_floor(self, with_halo) -> None:
        """MTF term present on both axes; high-f asymptote is (1 − vgf)."""
        terms = with_halo.state.mtf_terms
        assert "mtf_stray_x" in terms and "mtf_stray_y" in terms
        mtf = terms["mtf_stray_x"]
        assert mtf[0] == pytest.approx(1.0, abs=1e-12)  # DC
        # σ = 50 µm default → the Gaussian dies well before Nyquist; the
        # analytic floor is exactly (1 − vgf).
        assert mtf[-1] == pytest.approx(1.0 - VGF, abs=1e-6)

    def test_mtf_degrades(self, pedestal_only, with_halo) -> None:
        assert with_halo.metrics["mtf_at_nyquist"] < pedestal_only.metrics["mtf_at_nyquist"]

    def test_dual_path_consistency_holds(self, with_halo) -> None:
        """The halo is included in (not excluded from) the Rule 4 check."""
        cons = with_halo.stage_outputs["performance"]["dual_path_consistency"]
        assert cons.passed_x and cons.passed_y, f"consistency failed: {cons}"

    def test_signal_path_unchanged(self, pedestal_only, with_halo) -> None:
        """The halo redistributes PSF energy; total signal must be identical
        (vgf, and hence the radiometric pedestal, is the same in both runs)."""
        s0 = pedestal_only.stage_outputs["spectral_integration"]["signal_e"]
        s1 = with_halo.stage_outputs["spectral_integration"]["signal_e"]
        assert s1 == pytest.approx(s0, rel=1e-12)

    def test_noise_path_unchanged(self, pedestal_only, with_halo) -> None:
        """The spatial model must not double-count the pedestal: enabling
        the halo leaves every noise term untouched."""
        n0 = pedestal_only.stage_outputs["readout"]["sigma_total_e"]
        n1 = with_halo.stage_outputs["readout"]["sigma_total_e"]
        assert n1 == pytest.approx(n0, rel=1e-12)
