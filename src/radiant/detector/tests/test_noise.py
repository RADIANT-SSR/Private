"""Tests for radiant.detector.noise — all 16 noise sources.

Category C validation:
- Each noise source isolated with truth anchors
- Combined RSS verification
- Temporal/spatial separation
- Noise regime dominance checks
"""

from __future__ import annotations

import math

import pytest

from radiant.core.constants import k_B, q
from radiant.detector.noise import (
    ALL_NOISE_TERMS,
    SPATIAL_TERMS,
    TEMPORAL_TERMS,
    background_shot_noise,
    clutter_noise,
    compute_noise_budget,
    dark_shot_noise,
    dsnu_noise,
    flicker_1f_noise,
    glow_shot_noise,
    gr_noise,
    johnson_noise,
    ktc_reset_noise,
    nearfield_shot_noise,
    persistence_noise,
    prnu_noise,
    quantization_noise,
    read_noise_term,
    signal_shot_noise,
    straylight_shot_noise,
)

# ---------------------------------------------------------------------------
# Photon-shot family
# ---------------------------------------------------------------------------


class TestSignalShot:
    def test_poisson(self) -> None:
        assert signal_shot_noise(10000.0) == pytest.approx(100.0, rel=1e-12)

    def test_zero(self) -> None:
        assert signal_shot_noise(0.0) == 0.0

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="signal_e"):
            signal_shot_noise(-1.0)


class TestBackgroundShot:
    def test_poisson(self) -> None:
        assert background_shot_noise(2500.0) == pytest.approx(50.0, rel=1e-12)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="background_e"):
            background_shot_noise(-1.0)


class TestNearfieldShot:
    def test_poisson(self) -> None:
        assert nearfield_shot_noise(400.0) == pytest.approx(20.0, rel=1e-12)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="nearfield_e"):
            nearfield_shot_noise(-1.0)


class TestStraylightShot:
    def test_poisson(self) -> None:
        assert straylight_shot_noise(100.0) == pytest.approx(10.0, rel=1e-12)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="stray_e"):
            straylight_shot_noise(-1.0)


# ---------------------------------------------------------------------------
# Detector-material family
# ---------------------------------------------------------------------------


class TestDarkShot:
    def test_truth_anchor(self) -> None:
        """100 e-/s × 0.01 s = 1 e- → σ = 1.0 e-."""
        assert dark_shot_noise(1.0) == pytest.approx(1.0, rel=1e-12)

    def test_zero(self) -> None:
        assert dark_shot_noise(0.0) == 0.0


class TestGRNoise:
    def test_gr_factor_1(self) -> None:
        """gr_factor=1 → variance = 2×dark_e."""
        dark_e = 100.0
        expected = math.sqrt(2.0 * 1.0 * dark_e)
        assert gr_noise(dark_e, 1.0) == pytest.approx(expected, rel=1e-12)

    def test_gr_factor_0(self) -> None:
        assert gr_noise(100.0, 0.0) == 0.0

    def test_negative_factor_raises(self) -> None:
        with pytest.raises(ValueError, match="gr_factor"):
            gr_noise(100.0, -1.0)


class TestJohnsonNoise:
    def test_hand_calculation(self) -> None:
        """Truth anchor: R₀A=1e-5 Ω·cm², A=(18µm)², T=77K, t=0.01s.

        σ² = 4·k_B·77·(18e-6)²/(1e-5·1e-4)·0.01 / q²
        """
        r0a = 1.0e-5  # Ω·cm²
        area = (18.0e-6) ** 2
        temp = 77.0
        t_int = 0.01
        r0a_m2 = r0a * 1e-4
        variance = 4.0 * k_B * temp * area / r0a_m2 * t_int / (q * q)
        expected = math.sqrt(variance)
        actual = johnson_noise(r0a, area, temp, t_int)
        assert actual == pytest.approx(expected, rel=1e-10)

    def test_zero_r0a(self) -> None:
        assert johnson_noise(0.0, 1e-10, 77.0, 0.01) == 0.0

    def test_zero_temp(self) -> None:
        assert johnson_noise(1e-5, 1e-10, 0.0, 0.01) == 0.0


class TestFlicker1f:
    def test_known_value(self) -> None:
        """K=100 e-², f_low=1 Hz, f_high=1000 Hz → √(100·ln(1000))."""
        K = 100.0
        expected = math.sqrt(K * math.log(1000.0))
        assert flicker_1f_noise(K, 1.0, 1000.0) == pytest.approx(expected, rel=1e-12)

    def test_zero_K(self) -> None:
        assert flicker_1f_noise(0.0, 1.0, 1000.0) == 0.0

    def test_bad_freq_raises(self) -> None:
        with pytest.raises(ValueError, match="f_low_hz"):
            flicker_1f_noise(1.0, 0.0, 1000.0)
        with pytest.raises(ValueError, match="f_high_hz"):
            flicker_1f_noise(1.0, 100.0, 50.0)


# ---------------------------------------------------------------------------
# ROIC family
# ---------------------------------------------------------------------------


class TestReadNoise:
    def test_passthrough(self) -> None:
        assert read_noise_term(5.0) == pytest.approx(5.0, rel=1e-12)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="sigma_rms"):
            read_noise_term(-1.0)


class TestKtcReset:
    def test_cds_suppresses(self) -> None:
        assert ktc_reset_noise(1e-15, 77.0, cds_enabled=True) == 0.0

    def test_hand_calculation(self) -> None:
        """C=50 fF, T=77K → √(kTC)/q."""
        C = 50.0e-15
        T = 77.0
        expected = math.sqrt(k_B * T * C) / q
        actual = ktc_reset_noise(C, T, cds_enabled=False)
        assert actual == pytest.approx(expected, rel=1e-10)

    def test_zero_capacitance(self) -> None:
        assert ktc_reset_noise(0.0, 77.0, cds_enabled=False) == 0.0


class TestQuantization:
    def test_lsb_sqrt12(self) -> None:
        """gain=1.0 → σ = 1/√12 ≈ 0.2887."""
        expected = 1.0 / math.sqrt(12.0)
        assert quantization_noise(1.0) == pytest.approx(expected, rel=1e-12)

    def test_gain_2(self) -> None:
        expected = 2.0 / math.sqrt(12.0)
        assert quantization_noise(2.0) == pytest.approx(expected, rel=1e-12)

    def test_negative_gain_raises(self) -> None:
        with pytest.raises(ValueError, match="gain_e_per_dn"):
            quantization_noise(-1.0)


# ---------------------------------------------------------------------------
# Fixed-pattern family
# ---------------------------------------------------------------------------


class TestPRNU:
    def test_one_percent(self) -> None:
        """1% PRNU, 10000 e- → 100 e-."""
        assert prnu_noise(10000.0, 1.0) == pytest.approx(100.0, rel=1e-12)

    def test_zero_prnu(self) -> None:
        assert prnu_noise(10000.0, 0.0) == 0.0


class TestDSNU:
    def test_passthrough(self) -> None:
        assert dsnu_noise(3.5) == pytest.approx(3.5, rel=1e-12)


class TestClutter:
    def test_scaling(self) -> None:
        """clutter_sigma=0.01, bg=50000 e- → 500 e-."""
        assert clutter_noise(50000.0, 0.01) == pytest.approx(500.0, rel=1e-12)

    def test_zero_sigma(self) -> None:
        assert clutter_noise(50000.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# Other
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_known_value(self) -> None:
        """f=0.01, S_prev=10000, τ=1s, dt=0.1s."""
        frac = 0.01
        prior = 10000.0
        tau = 1.0
        dt = 0.1
        decay = 1.0 - math.exp(-dt / tau)
        expected = frac * prior * math.sqrt(decay)
        actual = persistence_noise(prior, frac, tau, dt)
        assert actual == pytest.approx(expected, rel=1e-10)

    def test_zero_fraction(self) -> None:
        assert persistence_noise(10000.0, 0.0, 1.0, 0.1) == 0.0

    def test_zero_prior(self) -> None:
        assert persistence_noise(0.0, 0.01, 1.0, 0.1) == 0.0

    def test_bad_tau_raises(self) -> None:
        with pytest.raises(ValueError, match="persistence_tau_s"):
            persistence_noise(100.0, 0.01, 0.0, 0.1)


class TestGlowShot:
    def test_poisson(self) -> None:
        assert glow_shot_noise(25.0) == pytest.approx(5.0, rel=1e-12)

    def test_zero(self) -> None:
        assert glow_shot_noise(0.0) == 0.0


# ---------------------------------------------------------------------------
# NoiseBudget aggregator
# ---------------------------------------------------------------------------


class TestNoiseBudget:
    def test_all_16_terms_present(self) -> None:
        budget = compute_noise_budget(signal_e=100.0)
        assert set(budget.terms.keys()) == ALL_NOISE_TERMS

    def test_temporal_spatial_partition(self) -> None:
        """TEMPORAL_TERMS + SPATIAL_TERMS = ALL_NOISE_TERMS, disjoint."""
        assert TEMPORAL_TERMS | SPATIAL_TERMS == ALL_NOISE_TERMS
        assert frozenset() == TEMPORAL_TERMS & SPATIAL_TERMS

    def test_rss_consistency(self) -> None:
        """sigma_total = √(σ_temporal² + σ_spatial²)."""
        budget = compute_noise_budget(
            signal_e=10000.0,
            background_e=5000.0,
            dark_e=50.0,
            read_noise_e_rms=5.0,
            prnu_pct=1.0,
            dsnu_e_rms=3.0,
        )
        temporal_var = sum(v**2 for k, v in budget.terms.items() if k in TEMPORAL_TERMS)
        spatial_var = sum(v**2 for k, v in budget.terms.items() if k in SPATIAL_TERMS)
        assert budget.sigma_temporal_e == pytest.approx(
            math.sqrt(temporal_var),
            rel=1e-12,
        )
        assert budget.sigma_spatial_e == pytest.approx(
            math.sqrt(spatial_var),
            rel=1e-12,
        )
        assert budget.sigma_total_e == pytest.approx(
            math.sqrt(temporal_var + spatial_var),
            rel=1e-12,
        )

    def test_blip_regime_shot_dominates(self) -> None:
        """High signal, low read noise → signal shot dominates."""
        budget = compute_noise_budget(
            signal_e=1_000_000.0,
            read_noise_e_rms=5.0,
        )
        fracs = budget.fractional_contributions()
        assert fracs["signal_shot"] > 0.99

    def test_read_limited_regime(self) -> None:
        """Low signal, high read noise → read noise dominates."""
        budget = compute_noise_budget(
            signal_e=1.0,
            read_noise_e_rms=50.0,
        )
        fracs = budget.fractional_contributions()
        assert fracs["read_noise"] > 0.99

    def test_fractional_contributions_sum_to_one(self) -> None:
        budget = compute_noise_budget(
            signal_e=10000.0,
            background_e=5000.0,
            dark_e=50.0,
            read_noise_e_rms=5.0,
        )
        total = sum(budget.fractional_contributions().values())
        assert total == pytest.approx(1.0, abs=1e-12)

    def test_all_zeros_no_crash(self) -> None:
        """All electron counts zero → budget with near-zero noise."""
        budget = compute_noise_budget(signal_e=0.0)
        # Only quantization noise is nonzero (gain default = 1.0)
        assert budget.sigma_temporal_e > 0.0
        assert budget.terms["quantization"] > 0.0
