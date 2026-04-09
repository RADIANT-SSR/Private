"""Level 0 tests for the Planck spectral radiance function.

Truth anchors (three independent sources, none of which call
planck_spectral_radiance):

1. Stefan–Boltzmann law. Hand-integrated closed form: ∫₀^∞ B(λ,T) dλ = σT⁴/π.
2. Wien displacement law. Hand-derived peak location: λ_peak · T = 2897.772 µm·K.
3. Hand-computed Planck values from the analytic formula (second radiation
   constant c₂ = 14387.77 µm·K, first radiation constant c₁L = 1.19104e8 W·µm⁴/(m²·sr))
   using the "µm-native" form
        B(λ,T) = c₁L · λ⁻⁵ / (exp(c₂/(λT)) − 1)
   which is algebraically distinct from the SI-meters form used internally
   (no 1e-6 Jacobian, constants sourced from NIST ITS-90 tables).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.blackbody import (
    planck_spectral_radiance,
    planck_spectral_radiance_dT,
)
from radiant.core.constants import sigma_sb

# ---------------------------------------------------------------------------
# Truth Anchor 1 — Stefan–Boltzmann closed form.
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("T", [300.0, 1000.0, 3000.0])
def test_stefan_boltzmann_integral(T: float) -> None:
    """∫B(λ,T) dλ over all λ equals σT⁴/π to better than 0.1%."""
    # Grid spans thermal significance for all tested T. Dense log grid.
    lam = np.logspace(np.log10(0.05), np.log10(1000.0), 20000)
    B = planck_spectral_radiance(lam, T)
    integrated = float(np.trapezoid(B, lam))  # W/m²/sr
    expected = sigma_sb * T**4 / math.pi  # W/m²/sr (Lambertian)
    rel_err = abs(integrated - expected) / expected
    assert rel_err < 1.0e-3, (
        f"T={T}: integrated={integrated:.6e}, expected={expected:.6e}, rel_err={rel_err:.3e}"
    )


# ---------------------------------------------------------------------------
# Truth Anchor 2 — Wien displacement.
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("T", [300.0, 1000.0, 3000.0])
def test_wien_displacement(T: float) -> None:
    """λ_peak · T ≈ 2897.77 µm·K to better than 0.01%."""
    wien_b = 2897.771955  # µm·K, CODATA 2018
    lam_peak_expected = wien_b / T
    # Dense grid around the expected peak
    lam = np.linspace(0.2 * lam_peak_expected, 5.0 * lam_peak_expected, 200000)
    B = planck_spectral_radiance(lam, T)
    lam_peak_actual = float(lam[int(np.argmax(B))])
    rel_err = abs(lam_peak_actual - lam_peak_expected) / lam_peak_expected
    assert rel_err < 1.0e-4, (
        f"T={T}: λ_peak actual={lam_peak_actual:.6f} µm, "
        f"expected={lam_peak_expected:.6f} µm, rel_err={rel_err:.3e}"
    )


# ---------------------------------------------------------------------------
# Truth Anchor 3 — independent formulation (µm-native constants, NIST c₁L, c₂).
# ---------------------------------------------------------------------------


def _planck_um_native(lam_um: float, T: float) -> float:
    """B(λ,T) via µm-native radiation constants (NIST values, hand-entered).

    c₁L = 2 h c² expressed as W·µm⁴/(m²·sr)
    c₂  = h c / k_B expressed as µm·K
    B = c₁L · λ_µm⁻⁵ / (exp(c₂/(λ_µm T)) − 1)    → W/m²/sr/µm
    """
    c1L = 1.191042972e8  # W·µm⁴/(m²·sr)  — NIST
    c2 = 14387.76877  # µm·K           — NIST
    return c1L / (lam_um**5 * (math.exp(c2 / (lam_um * T)) - 1.0))


@pytest.mark.level0
def test_independent_formulation_five_points() -> None:
    """Five (λ, T) points across regimes agree with hand-computed values < 0.01%."""
    cases = [
        # Visible / solar photosphere
        (0.55, 5778.0),
        # MWIR tail of a hot plume
        (4.0, 1500.0),
        # LWIR peak of room-temp
        (10.0, 300.0),
        # Rayleigh–Jeans regime (long λ, modest T)
        (100.0, 300.0),
        # Wien regime without underflow (short λ, cool T)
        (3.0, 1000.0),
    ]
    for lam_um, T in cases:
        actual = float(planck_spectral_radiance(lam_um, T)[0])
        expected = _planck_um_native(lam_um, T)
        rel_err = abs(actual - expected) / expected
        assert rel_err < 1.0e-4, (
            f"λ={lam_um} µm, T={T} K: actual={actual:.6e}, "
            f"expected={expected:.6e}, rel_err={rel_err:.3e}"
        )


# ---------------------------------------------------------------------------
# Limit checks — Rayleigh–Jeans and Wien approximations.
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_rayleigh_jeans_limit() -> None:
    """Full Planck → 2ckT/λ⁴ (in W/m²/sr/µm) when hc/λkT << 1."""
    from radiant.core.constants import c, hc_over_kB, k_B

    T = 300.0
    lam_um = 1.0e4  # 1 cm — deep RJ for room temp (x ≈ 0.0048)
    x = hc_over_kB / (lam_um * 1e-6 * T)
    assert x < 0.01, f"Sanity: x={x}"

    actual = float(planck_spectral_radiance(lam_um, T)[0])
    # RJ: B = 2 c k T / λ⁴  with λ in m → W/m²/sr/m,  × 1e-6 → W/m²/sr/µm
    lam_m = lam_um * 1e-6
    rj_per_m = 2.0 * c * k_B * T / lam_m**4
    expected = rj_per_m * 1e-6
    rel_err = abs(actual - expected) / expected
    assert rel_err < 0.01, (
        f"RJ limit: actual={actual:.6e}, expected={expected:.6e}, rel_err={rel_err:.3e}"
    )


@pytest.mark.level0
def test_wien_approximation_limit() -> None:
    """Full Planck → (2hc²/λ⁵)·exp(-hc/λkT) when hc/λkT >> 1."""
    from radiant.core.constants import hc_over_kB, two_hc2

    T = 300.0
    lam_um = 2.0  # hc/λkT ≈ 23.97 at T=300 K
    x = hc_over_kB / (lam_um * 1e-6 * T)
    assert x > 10.0, f"Sanity: x={x}"

    actual = float(planck_spectral_radiance(lam_um, T)[0])
    lam_m = lam_um * 1e-6
    wien_per_m = (two_hc2 / lam_m**5) * math.exp(-x)
    expected = wien_per_m * 1e-6
    rel_err = abs(actual - expected) / expected
    assert rel_err < 0.01, (
        f"Wien limit: actual={actual:.6e}, expected={expected:.6e}, rel_err={rel_err:.3e}"
    )


# ---------------------------------------------------------------------------
# Failure modes.
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_T_zero_returns_zero() -> None:
    """T = 0 K returns exactly zero at all wavelengths (documented behavior)."""
    lam = np.linspace(0.4, 14.0, 50)
    B = planck_spectral_radiance(lam, 0.0)
    assert np.all(B == 0.0)


@pytest.mark.level0
def test_T_very_high_no_overflow() -> None:
    """T → very large does not produce inf or nan."""
    lam = np.linspace(0.1, 100.0, 100)
    B = planck_spectral_radiance(lam, 100_000.0)
    assert np.all(np.isfinite(B))
    assert np.all(B > 0.0)


@pytest.mark.level0
def test_lambda_tiny_wien_tail_no_overflow() -> None:
    """λ → 0 (deep Wien / exp-overflow region) returns zero, not inf."""
    lam = np.array([0.01, 0.05, 0.1])  # way below peak for T=100 K
    B = planck_spectral_radiance(lam, 100.0)
    assert np.all(np.isfinite(B))
    assert np.all(B == 0.0)


@pytest.mark.level0
def test_lambda_huge_RJ_no_underflow() -> None:
    """λ → ∞ (RJ regime) returns small but strictly positive finite values."""
    lam = np.array([1e4, 1e5, 1e6])  # 1 cm, 10 cm, 1 m
    B = planck_spectral_radiance(lam, 300.0)
    assert np.all(np.isfinite(B))
    assert np.all(B > 0.0)
    # Monotonically decreasing in RJ tail
    assert B[0] > B[1] > B[2]


@pytest.mark.level0
def test_negative_temperature_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        planck_spectral_radiance(np.array([10.0]), -1.0)


@pytest.mark.level0
def test_zero_wavelength_raises() -> None:
    with pytest.raises(ValueError, match="non-positive"):
        planck_spectral_radiance(np.array([0.0, 1.0]), 300.0)


@pytest.mark.level0
def test_negative_wavelength_raises() -> None:
    with pytest.raises(ValueError, match="non-positive"):
        planck_spectral_radiance(np.array([-1.0, 1.0]), 300.0)


# ---------------------------------------------------------------------------
# Determinism / traceability.
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_deterministic() -> None:
    """Same inputs → bitwise-identical outputs."""
    lam = np.linspace(0.4, 14.0, 500)
    B1 = planck_spectral_radiance(lam, 300.0)
    B2 = planck_spectral_radiance(lam, 300.0)
    assert np.array_equal(B1, B2)


@pytest.mark.level0
def test_scalar_input_returns_1d() -> None:
    B = planck_spectral_radiance(10.0, 300.0)
    assert B.ndim == 1
    assert B.shape == (1,)
    assert B[0] > 0


# ---------------------------------------------------------------------------
# dB/dT tests.
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_dBdT_finite_difference() -> None:
    """Analytic ∂B/∂T matches a centered finite difference to < 1e-4 rel."""
    lam = np.array([0.5, 2.0, 4.0, 10.0, 20.0])
    T = 300.0
    dT = 1e-3
    B_plus = planck_spectral_radiance(lam, T + dT)
    B_minus = planck_spectral_radiance(lam, T - dT)
    fd = (B_plus - B_minus) / (2.0 * dT)

    analytic = planck_spectral_radiance_dT(lam, T)
    rel_err = np.abs(analytic - fd) / np.abs(fd)
    assert np.all(rel_err < 1e-4), f"rel_err={rel_err}"


@pytest.mark.level0
def test_dBdT_positive_below_wien_peak() -> None:
    """∂B/∂T > 0 at all wavelengths (Planck is monotone increasing in T)."""
    lam = np.linspace(0.4, 50.0, 200)
    dBdT = planck_spectral_radiance_dT(lam, 300.0)
    assert np.all(dBdT > 0)


@pytest.mark.level0
def test_dBdT_T_zero_raises() -> None:
    with pytest.raises(ValueError, match="T = 0"):
        planck_spectral_radiance_dT(np.array([10.0]), 0.0)
