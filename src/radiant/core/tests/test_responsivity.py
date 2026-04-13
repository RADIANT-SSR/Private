"""Tests for spectral and band-integrated responsivity."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.constants import hc
from radiant.core.responsivity import (
    band_integrated_responsivity,
    electrons_to_radiance,
    spectral_responsivity,
)


def _make_state(
    A_collect: float = 0.1,
    Omega_pixel: float = 1e-10,
    tau_opt_val: float = 0.6,
) -> ChainState:
    """Build a ChainState with optics outputs for responsivity tests."""
    wl = np.linspace(3.5, 5.0, 100)
    state = ChainState(wavelength_um=wl)
    tau_opt = np.full_like(wl, tau_opt_val)
    state = state.with_stage_output("optics", "A_collect", A_collect)
    state = state.with_stage_output("optics", "Omega_pixel", Omega_pixel)
    return state.with_stage_output("optics", "tau_opt", tau_opt)


class TestSpectralResponsivity:
    def test_shape_matches_wavelength(self) -> None:
        state = _make_state()
        r = spectral_responsivity(state)
        assert r is not None
        assert r.shape == state.wavelength_um.shape

    def test_scales_with_A_collect(self) -> None:
        """Doubling A_collect doubles R(λ)."""
        s1 = _make_state(A_collect=0.1)
        s2 = _make_state(A_collect=0.2)
        r1 = spectral_responsivity(s1)
        r2 = spectral_responsivity(s2)
        assert r1 is not None and r2 is not None
        np.testing.assert_allclose(r2, 2.0 * r1, rtol=1e-12)

    def test_scales_with_tau_opt(self) -> None:
        """Halving τ_opt halves R(λ)."""
        s1 = _make_state(tau_opt_val=0.6)
        s2 = _make_state(tau_opt_val=0.3)
        r1 = spectral_responsivity(s1)
        r2 = spectral_responsivity(s2)
        assert r1 is not None and r2 is not None
        np.testing.assert_allclose(r2, 0.5 * r1, rtol=1e-12)

    def test_known_value_no_qe(self) -> None:
        """R(λ) = A·Ω·τ·λ/hc when no QE is in stage_outputs (QE defaults to 1).

        A=0.1 m², Ω=1e-10 sr, τ=0.6, λ=4.0 µm.
        R = 0.1 × 1e-10 × 0.6 × 1.0 × (4e-6 / 1.9878e-25)
        """
        wl = np.array([3.9, 4.0, 4.1])
        state = ChainState(wavelength_um=wl)
        state = state.with_stage_output("optics", "A_collect", 0.1)
        state = state.with_stage_output("optics", "Omega_pixel", 1e-10)
        state = state.with_stage_output("optics", "tau_opt", np.array([0.6, 0.6, 0.6]))

        r = spectral_responsivity(state)
        assert r is not None

        lam_m = 4.0e-6
        expected = 0.1 * 1e-10 * 0.6 * (lam_m / hc)
        assert r[1] == pytest.approx(expected, rel=1e-10)

    def test_known_value_with_qe(self) -> None:
        """R(λ) = A·Ω·τ·QE·λ/hc when QE is available in stage_outputs.

        A=0.1 m², Ω=1e-10 sr, τ=0.6, QE=0.7, λ=4.0 µm.
        R = 0.1 × 1e-10 × 0.6 × 0.7 × (4e-6 / 1.9878e-25)
        """
        wl = np.array([3.9, 4.0, 4.1])
        state = ChainState(wavelength_um=wl)
        state = state.with_stage_output("optics", "A_collect", 0.1)
        state = state.with_stage_output("optics", "Omega_pixel", 1e-10)
        state = state.with_stage_output("optics", "tau_opt", np.array([0.6, 0.6, 0.6]))
        state = state.with_stage_output("spectral_integration", "qe_scalar", 0.7)

        r = spectral_responsivity(state)
        assert r is not None

        lam_m = 4.0e-6
        expected = 0.1 * 1e-10 * 0.6 * 0.7 * (lam_m / hc)
        assert r[1] == pytest.approx(expected, rel=1e-10)

    def test_spectral_qe_curve(self) -> None:
        """R(λ) uses spectral qe_curve when provided."""
        wl = np.array([3.9, 4.0, 4.1])
        state = ChainState(wavelength_um=wl)
        state = state.with_stage_output("optics", "A_collect", 0.1)
        state = state.with_stage_output("optics", "Omega_pixel", 1e-10)
        state = state.with_stage_output("optics", "tau_opt", np.array([0.6, 0.6, 0.6]))
        qe_curve = np.array([0.5, 0.7, 0.6])
        state = state.with_stage_output("spectral_integration", "qe_curve", qe_curve)

        r = spectral_responsivity(state)
        assert r is not None

        lam_m = 4.0e-6
        expected = 0.1 * 1e-10 * 0.6 * 0.7 * (lam_m / hc)
        assert r[1] == pytest.approx(expected, rel=1e-10)

    def test_missing_optics_returns_none(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        state = ChainState(wavelength_um=wl)
        assert spectral_responsivity(state) is None


class TestBandIntegratedResponsivity:
    def test_full_band(self) -> None:
        state = _make_state()
        r_band = band_integrated_responsivity(state)
        assert r_band is not None
        assert r_band > 0.0

    def test_narrower_filter_gives_less(self) -> None:
        state = _make_state()
        r_full = band_integrated_responsivity(state, 3.5, 5.0)
        r_half = band_integrated_responsivity(state, 4.0, 4.5)
        assert r_full is not None and r_half is not None
        assert r_half < r_full

    def test_missing_optics_returns_none(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        state = ChainState(wavelength_um=wl)
        assert band_integrated_responsivity(state) is None


class TestElectronsToRadiance:
    def test_round_trip_consistency(self) -> None:
        """signal_e ÷ (R_band × t_int) should give back radiance."""
        state = _make_state(A_collect=0.1, Omega_pixel=1e-10, tau_opt_val=0.6)

        # Set up integration outputs
        state = state.with_stage_output("spectral_integration", "signal_e", 10000.0)
        state = state.with_stage_output("spectral_integration", "e_rate_per_s", 1e6)

        L = electrons_to_radiance(10000.0, state)
        assert L is not None
        assert L > 0.0

    def test_missing_data_returns_none(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        state = ChainState(wavelength_um=wl)
        assert electrons_to_radiance(10000.0, state) is None
