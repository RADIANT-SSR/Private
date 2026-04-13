"""Tests for NEDT, NEDL, NEDR metrics."""

from __future__ import annotations

import math

import pytest

from radiant.performance.nedt import (
    compute_nedl,
    compute_nedr,
    compute_nedt,
    compute_nedt_from_snr,
)


class TestNEDT:
    """NEDT = σ_total / (dS/dT)."""

    def test_basic(self) -> None:
        """σ=100 e-, dS/dT=200 e-/K → NEDT = 0.5 K."""
        result = compute_nedt(noise_e=100.0, ds_dt_e_per_K=200.0)
        assert result.value_K == pytest.approx(0.5, rel=1e-12)
        assert result.ok is True

    def test_low_noise(self) -> None:
        """σ=1 e-, dS/dT=1000 e-/K → NEDT = 0.001 K (1 mK)."""
        result = compute_nedt(noise_e=1.0, ds_dt_e_per_K=1000.0)
        assert result.value_K == pytest.approx(0.001, rel=1e-12)

    def test_zero_ds_dt_fails(self) -> None:
        result = compute_nedt(noise_e=100.0, ds_dt_e_per_K=0.0)
        assert not result.ok
        assert math.isnan(result.value_K)

    def test_negative_ds_dt_fails(self) -> None:
        result = compute_nedt(noise_e=100.0, ds_dt_e_per_K=-10.0)
        assert not result.ok

    def test_negative_noise_fails(self) -> None:
        result = compute_nedt(noise_e=-1.0, ds_dt_e_per_K=100.0)
        assert not result.ok

    def test_zero_noise(self) -> None:
        """σ=0 → NEDT = 0 (perfect sensor)."""
        result = compute_nedt(noise_e=0.0, ds_dt_e_per_K=100.0)
        assert result.value_K == pytest.approx(0.0, abs=1e-15)
        assert result.ok is True


class TestNEDTFromSNR:
    """Planck-derivative approximation: NEDT = T / (SNR · x·eˣ/(eˣ-1))."""

    def test_mwir_300k(self) -> None:
        """MWIR (λ=4.5 µm), T=300 K, SNR=100.

        x = hc/(λkT) = 6.626e-34 × 3e8 / (4.5e-6 × 1.381e-23 × 300) ≈ 10.66
        Planck factor = x·eˣ/(eˣ-1) ≈ 10.66 (Wien limit: eˣ >> 1)
        NEDT = 300 / (100 × 10.66) ≈ 0.281 K.
        """
        result = compute_nedt_from_snr(
            target_temp_K=300.0,
            snr=100.0,
            lambda_eff_um=4.5,
        )
        assert result.ok is True
        assert result.value_K == pytest.approx(0.281, rel=0.01)

    def test_lwir_300k(self) -> None:
        """LWIR (λ=10 µm), T=300 K, SNR=100.

        x = hc/(λkT) ≈ 4.80 → Planck factor ≈ 4.84
        NEDT = 300/(100×4.84) ≈ 0.620 K.
        """
        result = compute_nedt_from_snr(
            target_temp_K=300.0,
            snr=100.0,
            lambda_eff_um=10.0,
        )
        assert result.ok is True
        assert result.value_K == pytest.approx(0.620, rel=0.01)

    def test_mwir_nedt_less_than_lwir(self) -> None:
        """MWIR has higher Planck derivative → lower NEDT at same SNR."""
        mwir = compute_nedt_from_snr(300.0, 100.0, 4.5)
        lwir = compute_nedt_from_snr(300.0, 100.0, 10.0)
        assert mwir.value_K < lwir.value_K

    def test_snr_inversely_proportional(self) -> None:
        """Doubling SNR halves NEDT."""
        r1 = compute_nedt_from_snr(300.0, 50.0, 4.5)
        r2 = compute_nedt_from_snr(300.0, 100.0, 4.5)
        assert r1.value_K == pytest.approx(2.0 * r2.value_K, rel=1e-10)

    def test_zero_temperature_fails(self) -> None:
        result = compute_nedt_from_snr(0.0, 100.0, 4.5)
        assert not result.ok

    def test_zero_snr_fails(self) -> None:
        result = compute_nedt_from_snr(300.0, 0.0, 4.5)
        assert not result.ok

    def test_inf_snr_fails(self) -> None:
        result = compute_nedt_from_snr(300.0, float("inf"), 4.5)
        assert not result.ok

    def test_zero_wavelength_fails(self) -> None:
        result = compute_nedt_from_snr(300.0, 100.0, 0.0)
        assert not result.ok


class TestNEDL:
    """NEDL = L / SNR."""

    def test_basic(self) -> None:
        """L=1.0 W/m²/sr/µm, SNR=100 → NEDL = 0.01."""
        result = compute_nedl(radiance=1.0, snr=100.0)
        assert result.value == pytest.approx(0.01, rel=1e-12)
        assert result.ok is True

    def test_snr_inversely_proportional(self) -> None:
        r1 = compute_nedl(1.0, 50.0)
        r2 = compute_nedl(1.0, 100.0)
        assert r1.value == pytest.approx(2.0 * r2.value, rel=1e-10)

    def test_zero_radiance_fails(self) -> None:
        result = compute_nedl(0.0, 100.0)
        assert not result.ok

    def test_zero_snr_fails(self) -> None:
        result = compute_nedl(1.0, 0.0)
        assert not result.ok


class TestNEDR:
    """NEΔρ = ρ / SNR."""

    def test_basic(self) -> None:
        """ρ=0.3, SNR=100 → NEΔρ = 0.003."""
        result = compute_nedr(reflectance=0.3, snr=100.0)
        assert result.value == pytest.approx(0.003, rel=1e-12)
        assert result.ok is True

    def test_snr_inversely_proportional(self) -> None:
        r1 = compute_nedr(0.3, 50.0)
        r2 = compute_nedr(0.3, 100.0)
        assert r1.value == pytest.approx(2.0 * r2.value, rel=1e-10)

    def test_zero_reflectance_fails(self) -> None:
        result = compute_nedr(0.0, 100.0)
        assert not result.ok

    def test_zero_snr_fails(self) -> None:
        result = compute_nedr(0.3, 0.0)
        assert not result.ok
