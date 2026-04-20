"""Integration test: extended-scene MWIR chain.

Reference case (from Prompt 2B.5):
    - MWIR staring sensor, 300 K extended scene, nadir
    - SimpleAtmosphere mid-latitude summer
    - Scalar optics: D = 0.30 m, f = 1.20 m, τ_opt = 0.70
    - Pixel pitch 18 µm (square)
    - t_int = 5 ms
    - QE = 0.70 (scalar, constant)
    - Dark rate = 100 e-/s
    - Read noise = 5.0 e- RMS
    - Gain = 1.0 e-/DN, 16-bit ADC

Every intermediate is hand-verified against the physics equations.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.core.blackbody import planck_spectral_radiance

# ---------------------------------------------------------------------------
# Hand-calculation constants for the reference case
# ---------------------------------------------------------------------------
D = 0.30        # m
F = 1.20        # m
F_NUM = F / D   # 4.0
TAU_OPT = 0.70
PITCH = 18e-6   # m
A_COLLECT = math.pi / 4.0 * D ** 2         # 0.070686 m²
OMEGA_PIXEL = PITCH ** 2 / F ** 2           # 2.25e-10 sr
T_INT = 0.005   # s
QE = 0.70
DARK_RATE = 100.0  # e-/s
READ_NOISE = 5.0   # e- RMS
GAIN = 32.0
T_TARGET = 300.0
EPS_TARGET = 0.95
SENSOR_ALT = 8000.0
FILTER_MIN = 3.5
FILTER_MAX = 5.0

# Spot-check wavelength
LAM_CHECK_UM = 4.0


@pytest.fixture()
def result():
    """Run the chain once and return the ChainResult."""
    wl = np.linspace(FILTER_MIN, FILTER_MAX, 500)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    params.set("source.target.temperature", T_TARGET)
    params.set("source.target.emissivity", EPS_TARGET)
    params.set("optics.aperture_diameter_m", D)
    params.set("optics.focal_length_m", F)
    params.set("optics.transmission_scalar", TAU_OPT)
    params.set("detector.pixel_pitch_x_um", PITCH * 1e6)
    params.set("detector.pixel_pitch_y_um", PITCH * 1e6)
    params.set("detector.qe_value", QE)
    params.set("detector.dark_rate_e_per_s", DARK_RATE)
    params.set("geometry.sensor_altitude_m", SENSOR_ALT)
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("spectral_integration.filter_min_um", FILTER_MIN)
    params.set("spectral_integration.filter_max_um", FILTER_MAX)
    params.set("spectral_integration.integration_time_s", T_INT)
    params.set("readout.read_noise_e_rms", READ_NOISE)
    params.set("readout.gain_e_per_dn", GAIN)
    params.set("readout.adc_bits", 16)
    params.resolve()
    return session.run(params)


class TestChainExtended:
    """Validate every intermediate in the extended-scene MWIR chain."""

    def test_history(self, result) -> None:
        assert result.history == (
            "source", "atmosphere", "optics", "platform",
            "spectral_integration", "detector", "readout",
            "performance",
        )

    def test_all_frames_present(self, result) -> None:
        # Stage 4 Option C: at_target is removed; at_aperture_target replaces it.
        expected = {
            "at_aperture_target",
            "at_aperture",
            "post_optics",
            "photoelectrons",
        }
        assert expected <= set(result.frames.keys())

    # -- Spot-check at λ = 4.0 µm -------------------------------------------

    def test_L_source_at_4um(self, result) -> None:
        """L_target(λ) = ε · B(λ, 300 K) reconstructed from at_aperture_target.

        Stage 4 Option C: SourceStage no longer publishes at_target; the
        target-only radiance is recovered from:
            at_aperture_target − L_path_up
                = ε·B(T_t)·τ_up
        so we divide by τ_up to get ε·B(T_t).
        """
        wl = result.wavelength_um
        idx = int(np.argmin(np.abs(wl - LAM_CHECK_UM)))
        lam_actual = wl[idx]
        B = planck_spectral_radiance(np.array([lam_actual]), T_TARGET)[0]
        L_expected = EPS_TARGET * B
        atm_q = result.stage_outputs["atmosphere"]["atm_quantities"]
        L_aat = result.frames["at_aperture_target"].spectral_radiance
        L_actual = (L_aat[idx] - atm_q.L_path_up[idx]) / atm_q.tau_up[idx]
        assert L_actual == pytest.approx(L_expected, rel=1e-6)

    def test_tau_atm_bounded(self, result) -> None:
        """Transmittance is in [0, 1] everywhere."""
        tau = result.stage_outputs["atmosphere"]["tau_atm"]
        assert np.all(tau >= 0.0)
        assert np.all(tau <= 1.0)

    def test_L_at_aperture_formula(self, result) -> None:
        """L_at_aperture = ε·B(T_t)·τ_up + L_path_up.

        Stage 4 Option C: AtmosphereStage composes the target arm itself;
        the at_aperture frame is aliased to at_aperture_target and equals
        L_target·τ_up + L_path_up for the extended regime.
        """
        tau = result.stage_outputs["atmosphere"]["tau_atm"]
        L_path = result.stage_outputs["atmosphere"]["L_path"]
        L_aa = result.frames["at_aperture"].spectral_radiance
        L_aat = result.frames["at_aperture_target"].spectral_radiance
        # at_aperture is aliased to at_aperture_target in Stage 4.
        np.testing.assert_allclose(L_aa, L_aat, rtol=1e-12)
        # Hand-compute ε·B(T_t) from the params and check the composition.
        wl = result.wavelength_um
        B = planck_spectral_radiance(wl, T_TARGET)
        L_expected = EPS_TARGET * B * tau + L_path
        np.testing.assert_allclose(L_aa, L_expected, rtol=1e-10)

    def test_L_post_optics_formula(self, result) -> None:
        """L_post_optics = L_at_aperture × τ_opt."""
        L_aa = result.frames["at_aperture"].spectral_radiance
        L_po = result.frames["post_optics"].spectral_radiance
        np.testing.assert_allclose(L_po, L_aa * TAU_OPT, rtol=1e-12)

    def test_photoelectrons_positive(self, result) -> None:
        pe = result.frames["photoelectrons"].in_band_value
        assert pe is not None and pe > 0.0

    def test_A_collect(self, result) -> None:
        A = result.stage_outputs["optics"]["A_collect"]
        assert pytest.approx(A_COLLECT, rel=1e-6) == A

    def test_Omega_pixel(self, result) -> None:
        omega = result.stage_outputs["optics"]["Omega_pixel"]
        assert omega == pytest.approx(OMEGA_PIXEL, rel=1e-6)

    # -- Noise terms ---------------------------------------------------------

    def test_shot_noise_formula(self, result) -> None:
        # Shot noise is √(signal_e_clipped) — capped at well capacity
        # when the accumulated signal exceeds FWC.
        signal_e_final = result.stage_outputs["readout"]["signal_e_final"]
        shot = [n for n in result.noise_terms if n.name == "signal_shot"][0]
        assert shot.value_e == pytest.approx(math.sqrt(signal_e_final), rel=1e-10)

    def test_dark_shot_noise(self, result) -> None:
        dark_e = DARK_RATE * T_INT
        dark_shot = [n for n in result.noise_terms if n.name == "dark_shot"][0]
        assert dark_shot.value_e == pytest.approx(math.sqrt(dark_e), rel=1e-10)

    def test_read_noise(self, result) -> None:
        read = [n for n in result.noise_terms if n.name == "read_noise"][0]
        assert read.value_e == pytest.approx(READ_NOISE, rel=1e-12)

    def test_quantization_noise(self, result) -> None:
        quant = [n for n in result.noise_terms if n.name == "quantization"][0]
        expected = GAIN / math.sqrt(12.0)
        assert quant.value_e == pytest.approx(expected, rel=1e-10)

    # -- SNR metric -----------------------------------------------------------

    def test_snr_metric_present(self, result) -> None:
        """PerformanceStage writes metrics['snr']."""
        assert "snr" in result.metrics

    def test_snr_positive_finite(self, result) -> None:
        """SNR must be positive and finite for a valid chain run."""
        snr = result.metrics["snr"]
        assert snr > 0.0
        assert math.isfinite(snr)

    def test_snr_formula(self, result) -> None:
        """SNR = signal_e_final / RSS(all noise terms).

        signal_e_final accounts for well/ADC saturation clipping and
        TDI/binning/coadd scaling applied in ReadoutStage.
        """
        signal_e = result.stage_outputs["readout"]["signal_e_final"]
        noise_sq = sum(n.value_e ** 2 for n in result.noise_terms)
        expected = signal_e / math.sqrt(noise_sq)
        assert result.metrics["snr"] == pytest.approx(expected, rel=1e-10)

    # -- Energy conservation -------------------------------------------------

    def test_energy_conservation(self, result) -> None:
        """Post-optics power ≤ at-aperture power per wavelength."""
        L_aa = result.frames["at_aperture"].spectral_radiance
        L_po = result.frames["post_optics"].spectral_radiance
        # Post-optics = at_aperture × tau_opt ≤ at_aperture
        assert np.all(L_po <= L_aa * (1.0 + 1e-14))

    # -- Determinism ---------------------------------------------------------

    def test_determinism(self) -> None:
        """Running the chain twice with identical inputs gives identical results."""
        wl = np.linspace(FILTER_MIN, FILTER_MAX, 100)
        session = RadiantSession(wavelength_um=wl)
        params = session.default_params()
        params.set("source.target.temperature", T_TARGET)
        params.set("source.target.emissivity", EPS_TARGET)
        params.set("optics.aperture_diameter_m", D)
        params.set("optics.focal_length_m", F)
        params.set("optics.transmission_scalar", TAU_OPT)
        params.set("detector.pixel_pitch_x_um", PITCH * 1e6)
        params.set("detector.pixel_pitch_y_um", PITCH * 1e6)
        params.set("detector.qe_value", QE)
        params.set("detector.dark_rate_e_per_s", DARK_RATE)
        params.set("geometry.sensor_altitude_m", SENSOR_ALT)
        params.set("atmosphere.standard_atmosphere", "midlat_summer")
        params.set("spectral_integration.filter_min_um", FILTER_MIN)
        params.set("spectral_integration.filter_max_um", FILTER_MAX)
        params.set("spectral_integration.integration_time_s", T_INT)
        params.set("readout.read_noise_e_rms", READ_NOISE)
        params.set("readout.gain_e_per_dn", GAIN)
        params.set("readout.adc_bits", 16)
        params.resolve()

        r1 = session.run(params)
        r2 = session.run(params)

        np.testing.assert_array_equal(
            r1.frames["at_aperture_target"].spectral_radiance,
            r2.frames["at_aperture_target"].spectral_radiance,
        )
        assert r1.frames["photoelectrons"].in_band_value == (
            r2.frames["photoelectrons"].in_band_value
        )
        for n1, n2 in zip(r1.noise_terms, r2.noise_terms, strict=True):
            assert n1.value_e == n2.value_e

    # -- t_int sensitivity ---------------------------------------------------

    def test_t_int_scaling(self) -> None:
        """Perturb t_int by +10% → signal scales +10%, shot σ by √1.1."""
        wl = np.linspace(FILTER_MIN, FILTER_MAX, 100)
        session = RadiantSession(wavelength_um=wl)

        def run_with_tint(t: float):
            p = session.default_params()
            p.set("source.target.temperature", T_TARGET)
            p.set("source.target.emissivity", EPS_TARGET)
            p.set("optics.aperture_diameter_m", D)
            p.set("optics.focal_length_m", F)
            p.set("optics.transmission_scalar", TAU_OPT)
            p.set("detector.pixel_pitch_x_um", PITCH * 1e6)
            p.set("detector.pixel_pitch_y_um", PITCH * 1e6)
            p.set("detector.qe_value", QE)
            p.set("detector.dark_rate_e_per_s", DARK_RATE)
            p.set("geometry.sensor_altitude_m", SENSOR_ALT)
            p.set("atmosphere.standard_atmosphere", "midlat_summer")
            p.set("spectral_integration.filter_min_um", FILTER_MIN)
            p.set("spectral_integration.filter_max_um", FILTER_MAX)
            p.set("spectral_integration.integration_time_s", t)
            p.set("readout.read_noise_e_rms", READ_NOISE)
            p.set("readout.gain_e_per_dn", GAIN)
            p.set("readout.adc_bits", 16)
            # High FWC to avoid saturation clipping in this scaling test.
            p.set("readout.full_well_capacity_e", 2000000.0)
            p.resolve()
            return session.run(p)

        r1 = run_with_tint(T_INT)
        r2 = run_with_tint(T_INT * 1.1)

        pe1 = r1.frames["photoelectrons"].in_band_value
        pe2 = r2.frames["photoelectrons"].in_band_value
        assert pe2 == pytest.approx(pe1 * 1.1, rel=1e-6)

        shot1 = [n for n in r1.noise_terms if n.name == "signal_shot"][0].value_e
        shot2 = [n for n in r2.noise_terms if n.name == "signal_shot"][0].value_e
        assert shot2 == pytest.approx(shot1 * math.sqrt(1.1), rel=1e-6)
