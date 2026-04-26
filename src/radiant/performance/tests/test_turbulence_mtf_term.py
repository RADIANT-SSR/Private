"""Tests for the Kolmogorov turbulence MTF term.

Validates the analytic formula: MTF = exp(-3.44 * (lambda * f / r0)^(5/3))
against known values and limiting cases.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.performance.turbulence_mtf_term import kolmogorov_mtf_1d

WAVELENGTH_M = 4.0e-6
FOCAL_LENGTH_M = 1.0


class TestKnownValues:
    """Validate against hand-calculated values."""

    @pytest.mark.level0
    def test_dc_is_unity(self) -> None:
        """MTF at zero frequency = 1.0."""
        freq_m = np.array([0.0])
        mtf = kolmogorov_mtf_1d(freq_m, WAVELENGTH_M, r0_m=0.10, focal_length_m=1.0)
        assert mtf[0] == pytest.approx(1.0, abs=1e-15)

    @pytest.mark.level0
    def test_hand_calculation(self) -> None:
        """Check against a manually computed value.

        r0 = 0.10 m, lambda = 4e-6 m, f_focal = 10000 cy/m, f_l = 1.0 m
        f_angular = 10000 * 1.0 = 10000 cy/rad
        arg = 4e-6 * 10000 / 0.10 = 0.4
        MTF = exp(-3.44 * 0.4^(5/3)) = exp(-3.44 * 0.27568) = exp(-0.9483)
        """
        freq_m = np.array([10000.0])
        mtf = kolmogorov_mtf_1d(freq_m, 4.0e-6, r0_m=0.10, focal_length_m=1.0)
        arg = 0.4
        expected = np.exp(-3.44 * arg ** (5.0 / 3.0))
        assert mtf[0] == pytest.approx(expected, rel=1e-10)


class TestLimitingCases:
    """MTF behaviour at extreme r0 values."""

    @pytest.mark.level0
    def test_large_r0_approaches_unity(self) -> None:
        """Very large r0 → MTF ≈ 1 at all frequencies."""
        freq_m = np.linspace(0, 50000, 100)
        mtf = kolmogorov_mtf_1d(freq_m, WAVELENGTH_M, r0_m=100.0, focal_length_m=1.0)
        assert np.all(mtf > 0.999)

    @pytest.mark.level0
    def test_small_r0_approaches_zero(self) -> None:
        """Very small r0 → MTF ≈ 0 at moderate frequencies."""
        freq_m = np.linspace(1000, 50000, 100)
        mtf = kolmogorov_mtf_1d(freq_m, WAVELENGTH_M, r0_m=0.001, focal_length_m=1.0)
        assert np.all(mtf < 0.01)


class TestMonotonicity:
    """MTF is monotonically decreasing with frequency."""

    @pytest.mark.level0
    def test_decreasing(self) -> None:
        freq_m = np.linspace(0, 50000, 200)
        mtf = kolmogorov_mtf_1d(freq_m, WAVELENGTH_M, r0_m=0.10, focal_length_m=1.0)
        assert np.all(np.diff(mtf) <= 0.0)
