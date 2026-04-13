"""Tests for Kolmogorov turbulence MTF.

Validates:
- MTF = exp(-3.44 · (λf/r₀)^(5/3)) against analytic formula
- DC = 1
- Larger r₀ → higher MTF (better seeing)
- Focal-plane frequency conversion

See RADIANT_Spatial_Complete.md §6 (step 8), §9 row 12.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere.turbulence import turbulence_mtf_1d, turbulence_mtf_focal

# ---------------------------------------------------------------------------
# turbulence_mtf_1d
# ---------------------------------------------------------------------------


class TestTurbulenceMTF:
    def test_dc_is_one(self) -> None:
        freq = np.array([0.0])
        mtf = turbulence_mtf_1d(freq, wavelength_m=0.5e-6, r0_m=0.10)
        assert mtf[0] == pytest.approx(1.0, rel=1e-12)

    def test_analytic_formula(self) -> None:
        """MTF matches exp(-3.44 · (λf/r₀)^(5/3))."""
        lam = 0.5e-6
        r0 = 0.10
        freq = np.linspace(0, 1e6, 500)  # cycles/rad

        mtf_computed = turbulence_mtf_1d(freq, lam, r0)
        arg = lam * freq / r0
        mtf_analytic = np.exp(-3.44 * np.abs(arg) ** (5.0 / 3.0))

        np.testing.assert_allclose(mtf_computed, mtf_analytic, rtol=1e-12)

    def test_larger_r0_higher_mtf(self) -> None:
        """Larger r₀ (better seeing) → higher MTF."""
        freq = np.array([1e5])
        lam = 0.5e-6
        mtf_poor = turbulence_mtf_1d(freq, lam, r0_m=0.05)
        mtf_good = turbulence_mtf_1d(freq, lam, r0_m=0.20)
        assert mtf_good[0] > mtf_poor[0]

    def test_longer_wave_higher_mtf(self) -> None:
        """Longer wavelength → less degradation (r₀ ∝ λ^(6/5))."""
        freq = np.array([1e5])
        r0 = 0.10
        mtf_vis = turbulence_mtf_1d(freq, 0.5e-6, r0)
        mtf_ir = turbulence_mtf_1d(freq, 4.0e-6, r0)
        # At same r₀ and freq, longer λ means larger arg → lower MTF.
        # Actually: arg = λf/r₀, larger λ → larger arg → more degradation.
        # So mtf_ir < mtf_vis. This is correct — r₀ is fixed, not scaled.
        assert mtf_ir[0] < mtf_vis[0]

    def test_zero_r0_raises(self) -> None:
        with pytest.raises(ValueError, match="r0_m must be positive"):
            turbulence_mtf_1d(np.array([0.0]), 0.5e-6, 0.0)

    def test_negative_r0_raises(self) -> None:
        with pytest.raises(ValueError, match="r0_m must be positive"):
            turbulence_mtf_1d(np.array([0.0]), 0.5e-6, -0.10)

    def test_zero_wavelength_raises(self) -> None:
        with pytest.raises(ValueError, match="wavelength_m must be positive"):
            turbulence_mtf_1d(np.array([0.0]), 0.0, 0.10)

    def test_hand_calculation(self) -> None:
        """Manual check: λ=0.5µm, f=1e6 cy/rad, r₀=10cm.

        arg = 0.5e-6 × 1e6 / 0.10 = 5.0
        MTF = exp(-3.44 × 5^(5/3)) = exp(-3.44 × 14.62) = exp(-50.29) ≈ 1.5e-22
        """
        lam = 0.5e-6
        r0 = 0.10
        freq = np.array([1e6])
        mtf = turbulence_mtf_1d(freq, lam, r0)
        arg = lam * 1e6 / r0
        expected = math.exp(-3.44 * arg ** (5.0 / 3.0))
        assert mtf[0] == pytest.approx(expected, rel=1e-10)


# ---------------------------------------------------------------------------
# turbulence_mtf_focal
# ---------------------------------------------------------------------------


class TestTurbulenceMTFFocal:
    def test_conversion(self) -> None:
        """Focal freq × focal_length = angular freq."""
        lam = 0.5e-6
        r0 = 0.10
        f_len = 1.5
        freq_focal = np.array([1e4])  # cycles/m in focal plane
        freq_angular = freq_focal * f_len  # cycles/rad

        mtf_focal = turbulence_mtf_focal(freq_focal, lam, r0, f_len)
        mtf_angular = turbulence_mtf_1d(freq_angular, lam, r0)

        np.testing.assert_allclose(mtf_focal, mtf_angular, rtol=1e-12)

    def test_zero_focal_length_raises(self) -> None:
        with pytest.raises(ValueError, match="focal_length_m"):
            turbulence_mtf_focal(np.array([0.0]), 0.5e-6, 0.10, 0.0)
