"""Level 0 tests for radiant.performance.temperature_retrieval (scenario 6.5).

Truth anchors from the forward/inverse Planck consistency (Rule 18):

- Round-trip: L = ε·B̄(T_true); retrieve with the SAME ε → T_true exactly.
- Wrong (higher) assumed ε → lower retrieved T (less emissive assumption
  needs a cooler surface to match the radiance) — biased retrieval.
- ∂L/∂ε = B̄(T); ∂L/∂T = ε·∫dB/dT dλ (finite-difference cross-check).
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.performance.temperature_retrieval import (
    TemperatureRetrievalError,
    band_planck_radiance,
    emissivity_jacobian,
    retrieve_temperature_K,
    temperature_jacobian,
)

BAND = np.linspace(8.0, 12.0, 200)


class TestRoundTrip:
    def test_exact_when_emissivity_correct(self) -> None:
        eps, t_true = 0.95, 300.0
        measured = eps * band_planck_radiance(t_true, BAND)
        assert retrieve_temperature_K(measured, eps, BAND) == pytest.approx(t_true, abs=1e-3)

    def test_higher_assumed_emissivity_lowers_retrieved_T(self) -> None:
        eps_true, t_true = 0.90, 305.0
        measured = eps_true * band_planck_radiance(t_true, BAND)
        t_hi = retrieve_temperature_K(measured, 0.98, BAND)  # over-estimate ε
        t_lo = retrieve_temperature_K(measured, 0.90, BAND)  # correct ε
        assert t_hi < t_lo
        assert t_lo == pytest.approx(t_true, abs=1e-3)

    def test_warmer_surface_more_radiance(self) -> None:
        assert band_planck_radiance(320.0, BAND) > band_planck_radiance(300.0, BAND)


class TestJacobian:
    def test_emissivity_jacobian_is_band_radiance(self) -> None:
        assert emissivity_jacobian(300.0, BAND) == pytest.approx(
            band_planck_radiance(300.0, BAND), rel=1e-12
        )

    def test_temperature_jacobian_finite_difference(self) -> None:
        eps, t = 0.95, 300.0
        analytic = temperature_jacobian(t, eps, BAND)
        d = 0.01
        fd = eps * (band_planck_radiance(t + d, BAND) - band_planck_radiance(t - d, BAND)) / (2 * d)
        assert analytic == pytest.approx(fd, rel=1e-4)

    def test_first_order_error_matches_exact(self) -> None:
        """ΔT ≈ −(∂L/∂ε / ∂L/∂T)·Δε vs the exact retrieval bias (small Δε)."""
        eps_true, t_true = 0.95, 300.0
        measured = eps_true * band_planck_radiance(t_true, BAND)
        d_eps = 0.01
        t_ret = retrieve_temperature_K(measured, eps_true + d_eps, BAND)
        exact_dt = t_ret - t_true
        approx_dt = (
            -(emissivity_jacobian(t_true, BAND) / temperature_jacobian(t_true, eps_true, BAND))
            * d_eps
        )
        assert exact_dt == pytest.approx(approx_dt, rel=0.05)


class TestValidation:
    def test_bad_emissivity_raises(self) -> None:
        with pytest.raises(TemperatureRetrievalError, match="assumed_emissivity"):
            retrieve_temperature_K(1.0, 0.0, BAND)

    def test_unreachable_radiance_raises(self) -> None:
        with pytest.raises(TemperatureRetrievalError, match="retrievable"):
            retrieve_temperature_K(1e12, 0.95, BAND)
