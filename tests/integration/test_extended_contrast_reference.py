"""Integration: ADR-0005 / Gap 52 — extended target-vs-background contrast.

Setting source.contrast_reference.temperature makes the extended
contrast_snr a true differential (signal_e − S_ref) with combined noise
√(N_t² + N_ref²), nulling at the radiance crossover. It must NOT change the
SNR (Decision #13: the reference never enters the noise budget), and the
default (no reference) must leave everything unchanged.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.session import RadiantSession


def _run(target_temp: float, ref_temp: float | None, ref_eps: float = 0.95):
    wl = np.linspace(7.5, 12.5, 220)
    session = RadiantSession(wavelength_um=wl)
    p = session.default_params()
    p.set("source.scene_type", "extended")
    p.set("source.target.temperature", target_temp)
    p.set("source.target.emissivity", 0.95)
    if ref_temp is not None:
        p.set("source.contrast_reference.temperature", ref_temp)
        p.set("source.contrast_reference.emissivity", ref_eps)
    p.set("optics.aperture_diameter_m", 0.15)
    p.set("optics.focal_length_m", 0.5)
    p.set("optics.transmission_scalar", 0.8)
    p.set("detector.pixel_pitch_x_um", 25.0)
    p.set("detector.pixel_pitch_y_um", 25.0)
    p.set("detector.qe_value", 0.7)
    p.set("detector.dark_rate_e_per_s", 5e6)
    p.set("geometry.sensor_altitude_m", 3000.0)
    p.set("spectral_integration.filter_min_um", 8.0)
    p.set("spectral_integration.filter_max_um", 12.0)
    p.set("spectral_integration.integration_time_s", 1e-4)
    p.set("readout.read_noise_e_rms", 300.0)
    p.set("readout.gain_e_per_dn", 120.0)
    p.set("readout.adc_bits", 14)
    p.set("readout.full_well_capacity_e", 6e6)
    p.resolve()
    return session.run(p)


@pytest.mark.level2
class TestExtendedContrastReference:
    def test_default_no_reference_signal(self) -> None:
        """No reference ⇒ no contrast_reference_signal_e; contrast is whole-scene."""
        res = _run(300.0, None)
        assert res.stage_outputs["spectral_integration"].get("contrast_reference_signal_e") is None
        # whole-scene contrast SNR is large and positive
        assert res.metrics["contrast_snr"] > 100.0

    def test_nulls_at_crossover(self) -> None:
        """Equal target/reference temperature & emissivity ⇒ contrast_snr ≈ 0."""
        res = _run(295.0, 295.0, ref_eps=0.95)
        assert abs(res.metrics["contrast_snr"]) < 1.0

    def test_sign_flips_across_crossover(self) -> None:
        cold = _run(290.0, 295.0)
        hot = _run(300.0, 295.0)
        assert cold.metrics["contrast_snr"] < 0.0  # target colder than reference
        assert hot.metrics["contrast_snr"] > 0.0  # target warmer

    def test_reference_does_not_change_snr(self) -> None:
        """Decision #13 preserved: the reference is noise-decoupled, so the
        absolute SNR is identical with and without the contrast reference."""
        without = _run(300.0, None)
        with_ref = _run(300.0, 295.0)
        assert with_ref.metrics["snr"] == pytest.approx(without.metrics["snr"], rel=1e-12)

    def test_combined_noise_used(self) -> None:
        """contrast_snr = ΔS / √(N_t² + N_ref²) — larger noise than single-pixel."""
        res = _run(305.0, 295.0)
        si = res.stage_outputs["spectral_integration"]
        contrast_e = res.stage_outputs["readout"].get("contrast_e_final", si["contrast_e"])
        sigma_t = res.stage_outputs["readout"]["sigma_total_e"]
        s_t = res.stage_outputs["readout"].get("signal_e_final", si["signal_e"])
        s_ref = si["contrast_reference_signal_e"] * (s_t / si["signal_e"])
        n_ref_sq = max(0.0, sigma_t**2 - s_t + s_ref)
        combined = np.sqrt(sigma_t**2 + n_ref_sq)
        assert res.metrics["contrast_snr"] == pytest.approx(contrast_e / combined, rel=1e-6)
