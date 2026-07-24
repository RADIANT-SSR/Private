"""Tests for spectral and band-integrated responsivity.

All tests are Level 0: verify the analytic identity R(λ) = A·Ω·τ·QE·λ/hc and
its scaling/limit behaviors against closed-form values; pytest.approx uses
explicit rel= tolerance.
"""

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
    @pytest.mark.level0
    def test_shape_matches_wavelength(self) -> None:
        state = _make_state()
        r = spectral_responsivity(state)
        assert r is not None
        assert r.shape == state.wavelength_um.shape

    @pytest.mark.level0
    def test_scales_with_A_collect(self) -> None:
        """Doubling A_collect doubles R(λ)."""
        s1 = _make_state(A_collect=0.1)
        s2 = _make_state(A_collect=0.2)
        r1 = spectral_responsivity(s1)
        r2 = spectral_responsivity(s2)
        assert r1 is not None and r2 is not None
        np.testing.assert_allclose(r2, 2.0 * r1, rtol=1e-12)

    @pytest.mark.level0
    def test_scales_with_tau_opt(self) -> None:
        """Halving τ_opt halves R(λ)."""
        s1 = _make_state(tau_opt_val=0.6)
        s2 = _make_state(tau_opt_val=0.3)
        r1 = spectral_responsivity(s1)
        r2 = spectral_responsivity(s2)
        assert r1 is not None and r2 is not None
        np.testing.assert_allclose(r2, 0.5 * r1, rtol=1e-12)

    @pytest.mark.level0
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

    @pytest.mark.level0
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

    @pytest.mark.level0
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

    @pytest.mark.level0
    def test_missing_optics_returns_none(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        state = ChainState(wavelength_um=wl)
        assert spectral_responsivity(state) is None


class TestBandIntegratedResponsivity:
    @pytest.mark.level0
    def test_full_band(self) -> None:
        state = _make_state()
        r_band = band_integrated_responsivity(state)
        assert r_band is not None
        assert r_band > 0.0

    @pytest.mark.level0
    def test_narrower_filter_gives_less(self) -> None:
        state = _make_state()
        r_full = band_integrated_responsivity(state, 3.5, 5.0)
        r_half = band_integrated_responsivity(state, 4.0, 4.5)
        assert r_full is not None and r_half is not None
        assert r_half < r_full

    @pytest.mark.level0
    def test_band_integral_closed_form_anchor(self) -> None:
        """Absolute value anchor for the band integral (audit finding B2-2).

        For flat τ·QE the spectral responsivity R(λ) = A·Ω·τ·QE·(λ_m/hc) is
        *linear* in wavelength, so the band integral over the µm grid has the
        closed form

            R_band = A·Ω·τ·QE · (1e-6/hc) · (λ_max² − λ_min²)/2   [λ in µm]

        The 1e-6 is the µm→m Jacobian of λ inside R(λ); it appears once
        (R is linear in λ), and the integration variable dλ is in µm — the
        convention band-averaged radiance [W/m²/sr] uses. Trapezoid is exact
        for a linear integrand, so this pins the value, not just the sign.
        A factor-of-2, factor-of-π, or 1e6 unit slip in the integral fails.
        """
        A, Om, tau, qe = 0.1, 1e-10, 0.6, 0.7
        lo, hi = 3.5, 5.0
        state = _make_state(A_collect=A, Omega_pixel=Om, tau_opt_val=tau)
        state = state.with_stage_output("spectral_integration", "qe_scalar", qe)

        expected = A * Om * tau * qe * (1e-6 / hc) * (hi**2 - lo**2) / 2.0
        r_band = band_integrated_responsivity(state, lo, hi)
        assert r_band is not None
        assert r_band == pytest.approx(expected, rel=1e-9)

    @pytest.mark.level0
    def test_missing_optics_returns_none(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        state = ChainState(wavelength_um=wl)
        assert band_integrated_responsivity(state) is None


class TestElectronsToRadiance:
    @pytest.mark.level0
    def test_round_trip_recovers_known_radiance(self) -> None:
        """End-to-end anchor: recover a known input radiance (audit finding B2-1).

        The prior test asserted only ``L > 0``, which passes even if the impl
        drops ``t_int``, the QE factor, or the λ/hc term. Here the expected
        radiance is built from an *independently* computed R_band (the B2-2
        closed form) and the t_int the impl must infer, so a dropped factor
        moves the recovered value off the anchor.
        """
        A, Om, tau, qe = 0.1, 1e-10, 0.6, 0.7
        lo, hi = 3.5, 5.0
        state = _make_state(A_collect=A, Omega_pixel=Om, tau_opt_val=tau)
        state = state.with_stage_output("spectral_integration", "qe_scalar", qe)

        # e_rate/signal fix the inferred integration time: t_int = 1e4/1e6 = 0.01 s.
        signal_e_stored, e_rate = 10000.0, 1e6
        t_int = signal_e_stored / e_rate
        state = state.with_stage_output("spectral_integration", "signal_e", signal_e_stored)
        state = state.with_stage_output("spectral_integration", "e_rate_per_s", e_rate)

        # Independent R_band (closed form, flat τ·QE) — see test_band_integral_closed_form_anchor.
        r_band = A * Om * tau * qe * (1e-6 / hc) * (hi**2 - lo**2) / 2.0

        signal_e_probe = 12345.0
        expected_L = signal_e_probe / (r_band * t_int)
        L = electrons_to_radiance(signal_e_probe, state)
        assert L is not None
        assert L == pytest.approx(expected_L, rel=1e-9)

    @pytest.mark.level0
    def test_missing_data_returns_none(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        state = ChainState(wavelength_um=wl)
        assert electrons_to_radiance(10000.0, state) is None
