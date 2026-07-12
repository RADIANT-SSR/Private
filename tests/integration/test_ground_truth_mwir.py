"""Ground truth test: fully hand-computable MWIR single-wavelength case.

This is the single most important test in Phase 2B. Every intermediate
value is verified against a hand calculation performed with CODATA 2018
constants. See ``docs/validation/ground_truth_mwir_singlewave.md`` for
the step-by-step derivation.

Parameters:
    λ = 4.0 µm (3-point narrow grid: [3.999, 4.0, 4.001] µm)
    T = 300 K, ε = 1.0 (pure blackbody)
    Atmosphere: ExoAtmosphere (τ = 1, L_path = 0)
    Optics: D = 0.30 m, f = 1.50 m (f/5), τ_opt = 0.75
    Detector: pitch = 15 µm, QE = 0.70, dark = 0
    Readout: read noise = 30 e⁻ RMS, gain = 1 e/DN, 16-bit ADC
    Integration: 5 ms
    Regime: extended scene

Hand-calculated reference values (CODATA 2018 exact constants):
    B(4 µm, 300 K)  = 7.2197642257e-01 W/m²/sr/µm
    A_collect        = 7.0685834706e-02 m²
    Ω_pixel          = 1.0000000000e-10 sr
    signal_e         ≈ 539.51 e⁻  (narrow-band trapezoid)
    shot_noise       ≈ 23.23 e⁻ RMS
    read_noise       = 30.00 e⁻ RMS
    quant_noise      = 0.2887 e⁻ RMS
    SNR              ≈ 14.22  (Option C Stage 4: exo→ColdSpaceBackground→L_bg≡0;
                               Decision #15 removed the legacy scalar-bg
                               double-count; background_shot=0 here)
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.core.constants import c, h, hc, k_B
from radiant.io.config import load_config

# ---------------------------------------------------------------------------
# Hand-calculation constants (CODATA 2018 exact)
# ---------------------------------------------------------------------------

LAM_UM = 4.0
LAM_M = 4.0e-6
T = 300.0
EPS = 1.0
D = 0.30
F = 1.50
F_NUM = 5.0
TAU_OPT = 0.75
PITCH = 15e-6
QE = 0.70
T_INT = 0.005
READ_NOISE = 30.0
GAIN = 1.0

# Step 1: Planck at 4 µm, 300 K → W/m²/sr/µm
_exp_arg = h * c / (LAM_M * k_B * T)
B_4UM = (2 * h * c**2 / LAM_M**5) / (math.exp(_exp_arg) - 1) * 1e-6
L_TARGET = EPS * B_4UM

# Step 4: Collecting area
A_COLLECT = math.pi / 4 * D**2

# Step 5: Pixel solid angle
OMEGA_PIXEL = PITCH**2 / F**2


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


CONFIG_PATH = Path(__file__).parents[2] / "examples" / "ground_truth_mwir.yaml"


@pytest.fixture(scope="module")
def result():
    """Run the ground truth chain."""
    wl = np.array([3.999, 4.000, 4.001])
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    load_config(CONFIG_PATH, params)
    params.resolve()
    return session.run(params)


# ---------------------------------------------------------------------------
# Tests — each verifies one intermediate against hand calculation
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestGroundTruthMWIR:
    """Verify every intermediate against hand calculation."""

    def test_planck_radiance(self, result) -> None:
        """B(4 µm, 300 K) — Planck spectral radiance.

        Stage 4 Option C: at_target frame is removed.  For exo (τ_up=1,
        L_path_up=0) the at_aperture_target frame equals ε·B(T_t) directly.
        """
        L = result.frames["at_aperture_target"].spectral_radiance
        # Index 1 is the 4.000 µm grid point.
        assert L[1] == pytest.approx(L_TARGET, rel=1e-6)

    def test_atmosphere_transparent(self, result) -> None:
        """ExoAtmosphere: τ = 1, L_path = 0."""
        tau = result.stage_outputs["atmosphere"]["tau_atm"]
        L_path = result.stage_outputs["atmosphere"]["L_path"]
        np.testing.assert_array_equal(tau, np.ones_like(tau))
        np.testing.assert_array_equal(L_path, np.zeros_like(L_path))

    def test_L_at_aperture_equals_target(self, result) -> None:
        """L_aperture = L_aperture_target for exo (τ=1, L_path=0).

        Stage 4 Option C: the at_aperture frame is aliased to
        at_aperture_target (both equal ε·B(T_t)·τ_up + L_path_up = ε·B
        for exo).
        """
        L_t = result.frames["at_aperture_target"].spectral_radiance
        L_a = result.frames["at_aperture"].spectral_radiance
        np.testing.assert_allclose(L_a, L_t, rtol=1e-12)

    def test_L_post_optics(self, result) -> None:
        """L_post = L_aperture × τ_opt."""
        L_a = result.frames["at_aperture"].spectral_radiance
        L_p = result.frames["post_optics"].spectral_radiance
        np.testing.assert_allclose(L_p, L_a * TAU_OPT, rtol=1e-12)

    def test_A_collect(self, result) -> None:
        """A_collect = π/4 × D²."""
        assert result.stage_outputs["optics"]["A_collect"] == pytest.approx(
            A_COLLECT, rel=1e-10
        )

    def test_Omega_pixel(self, result) -> None:
        """Ω_pixel = pitch² / f²."""
        assert result.stage_outputs["optics"]["Omega_pixel"] == pytest.approx(
            OMEGA_PIXEL, rel=1e-10
        )

    def test_signal_electrons(self, result) -> None:
        """Signal ≈ hand-calculated value within 1e-4.

        The hand calculation uses L(4.0 µm) × Δλ for the integral.
        The chain uses np.trapezoid over 3 points where L varies
        slightly. The difference is < 1e-6 relative.
        """
        # Hand calc: e_rate_per_um × Δλ × t_int
        L_post = L_TARGET * TAU_OPT
        photon_rate_per_um = L_post * A_COLLECT * OMEGA_PIXEL * (LAM_M / hc)
        e_rate_per_um = photon_rate_per_um * QE
        delta_lam = 0.002  # µm
        hand_signal = e_rate_per_um * delta_lam * T_INT

        actual = result.frames["photoelectrons"].in_band_value
        assert actual == pytest.approx(hand_signal, rel=1e-4)

    def test_shot_noise(self, result) -> None:
        """Shot noise = √(signal_e)."""
        pe = result.frames["photoelectrons"].in_band_value
        shot = [n for n in result.noise_terms if n.name == "signal_shot"][0]
        assert shot.value_e == pytest.approx(math.sqrt(pe), rel=1e-10)

    def test_dark_shot_zero(self, result) -> None:
        """Dark rate = 0 → dark_shot = 0."""
        dark = [n for n in result.noise_terms if n.name == "dark_shot"][0]
        assert dark.value_e == 0.0

    def test_read_noise(self, result) -> None:
        """Read noise = 30 e⁻ RMS (direct parameter)."""
        read = [n for n in result.noise_terms if n.name == "read_noise"][0]
        assert read.value_e == pytest.approx(READ_NOISE, rel=1e-12)

    def test_quantization_noise(self, result) -> None:
        """Quantization noise = gain / √12."""
        quant = [n for n in result.noise_terms if n.name == "quantization"][0]
        assert quant.value_e == pytest.approx(GAIN / math.sqrt(12), rel=1e-10)

    def test_snr(self, result) -> None:
        """SNR = signal_e_final / RSS(all noise) ≈ 12.39."""
        signal_e = result.stage_outputs["readout"]["signal_e_final"]
        noise_sq = sum(n.value_e**2 for n in result.noise_terms)
        expected_snr = signal_e / math.sqrt(noise_sq)
        actual_snr = result.metrics["snr"]
        assert actual_snr == pytest.approx(expected_snr, rel=1e-10)
        # Cross-check against hand calculation (Stage 4 Option C:
        # ColdSpaceBackground → background_e = 0, background_shot = 0;
        # only shot (≈23.23 e⁻), read (30 e⁻) and quantization (0.29 e⁻)
        # contribute.  SNR = 539.51 / sqrt(30² + 23.23² + 0.29²) ≈ 14.22).
        assert actual_snr == pytest.approx(14.22, rel=1e-2)

    def test_snr_read_noise_dominated(self, result) -> None:
        """With ~540 e⁻ signal and 30 e⁻ read noise, SNR ~ 14.

        This confirms the read-noise-dominated regime: shot noise (23 e⁻)
        is comparable to read noise (30 e⁻), giving SNR well below the
        shot-limited value of √540 ≈ 23.
        """
        snr = result.metrics["snr"]
        pe = result.frames["photoelectrons"].in_band_value
        assert snr < math.sqrt(pe)  # below shot limit

    def test_history(self, result) -> None:
        assert result.history == (
            "geometry", "source", "atmosphere", "optics", "platform",
            "spectral_integration", "detector", "readout",
            "performance",
        )

    def test_determinism(self, result) -> None:
        """Same config → identical output."""
        wl = np.array([3.999, 4.000, 4.001])
        session = RadiantSession(wavelength_um=wl)
        params = session.default_params()
        load_config(CONFIG_PATH, params)
        params.resolve()
        r2 = session.run(params)
        assert result.metrics["snr"] == r2.metrics["snr"]
        assert result.frames["photoelectrons"].in_band_value == (
            r2.frames["photoelectrons"].in_band_value
        )
