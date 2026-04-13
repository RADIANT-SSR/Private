"""Tests for platform/scan/target smear MTF.

Validates:
- MTF = |sinc(π·f·smear_width)| against analytic formula
- Kernel normalisation
- Zero motion → delta kernel / unity MTF
- Smear width calculation from velocity

See RADIANT_Spatial_Complete.md §7.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.platform.smear import smear_kernel_1d, smear_mtf_1d, smear_width_m


# ---------------------------------------------------------------------------
# smear_mtf_1d — Truth Anchor: analytic sinc
# ---------------------------------------------------------------------------


class TestSmearMTF:
    def test_dc_is_one(self) -> None:
        freq = np.array([0.0])
        mtf = smear_mtf_1d(freq, smear_width_m=10e-6)
        assert mtf[0] == pytest.approx(1.0, rel=1e-12)

    def test_analytic_sinc(self) -> None:
        """MTF matches |sinc(π·f·w)| within machine precision."""
        w = 10e-6
        freq = np.linspace(0, 2.0 / w, 500)
        mtf_computed = smear_mtf_1d(freq, w)
        mtf_analytic = np.abs(np.sinc(freq * w))
        np.testing.assert_allclose(mtf_computed, mtf_analytic, rtol=1e-12)

    def test_first_zero(self) -> None:
        """First zero at f = 1/w."""
        w = 20e-6
        freq = np.array([1.0 / w])
        mtf = smear_mtf_1d(freq, w)
        assert mtf[0] == pytest.approx(0.0, abs=1e-10)

    def test_zero_smear_is_unity(self) -> None:
        freq = np.linspace(0, 1e5, 100)
        mtf = smear_mtf_1d(freq, 0.0)
        np.testing.assert_array_equal(mtf, np.ones_like(freq))

    def test_larger_smear_lower_mtf(self) -> None:
        freq = np.array([5e4])
        mtf_small = smear_mtf_1d(freq, 2e-6)
        mtf_large = smear_mtf_1d(freq, 20e-6)
        assert mtf_large[0] < mtf_small[0]

    def test_negative_smear_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            smear_mtf_1d(np.array([0.0]), -1e-6)

    def test_several_widths(self) -> None:
        """Verify at several smear widths per prompt requirements."""
        freq = np.linspace(0, 1e5, 200)
        for w in [1e-6, 5e-6, 15e-6, 50e-6]:
            mtf = smear_mtf_1d(freq, w)
            expected = np.abs(np.sinc(freq * w))
            np.testing.assert_allclose(mtf, expected, rtol=1e-12)


# ---------------------------------------------------------------------------
# smear_width_m
# ---------------------------------------------------------------------------


class TestSmearWidth:
    def test_basic(self) -> None:
        """v=7500 m/s, alt=700km, f=1.5m, t=5ms → smear on FPA."""
        v = 7500.0
        alt = 700e3
        f = 1.5
        t = 0.005
        w = smear_width_m(v, t, f, alt)
        expected = (v / alt) * f * t
        assert w == pytest.approx(expected, rel=1e-12)

    def test_zero_velocity(self) -> None:
        w = smear_width_m(0.0, 0.005, 1.5, 700e3)
        assert w == 0.0

    def test_zero_t_int(self) -> None:
        w = smear_width_m(7500.0, 0.0, 1.5, 700e3)
        assert w == 0.0

    def test_negative_t_int_raises(self) -> None:
        with pytest.raises(ValueError, match="t_int_s"):
            smear_width_m(7500.0, -0.001, 1.5, 700e3)

    def test_zero_focal_length_raises(self) -> None:
        with pytest.raises(ValueError, match="focal_length_m"):
            smear_width_m(7500.0, 0.005, 0.0, 700e3)

    def test_zero_altitude_raises(self) -> None:
        with pytest.raises(ValueError, match="altitude_m"):
            smear_width_m(7500.0, 0.005, 1.5, 0.0)


# ---------------------------------------------------------------------------
# smear_kernel_1d
# ---------------------------------------------------------------------------


class TestSmearKernel:
    def test_unit_volume(self) -> None:
        kernel = smear_kernel_1d(65, 1e-6, 15e-6)
        assert float(kernel.sum()) == pytest.approx(1.0, rel=1e-6)

    def test_non_negative(self) -> None:
        kernel = smear_kernel_1d(65, 1e-6, 15e-6)
        assert np.all(kernel >= 0.0)

    def test_zero_smear_is_delta(self) -> None:
        kernel = smear_kernel_1d(11, 1e-6, 0.0)
        c = 11 // 2
        assert kernel[c] == 1.0
        kernel[c] = 0.0
        assert float(kernel.sum()) == 0.0

    def test_even_npix_raises(self) -> None:
        with pytest.raises(ValueError, match="odd"):
            smear_kernel_1d(64, 1e-6, 10e-6)

    def test_negative_smear_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            smear_kernel_1d(65, 1e-6, -10e-6)


# ---------------------------------------------------------------------------
# Cross-model: rotated smear should be equivalent
# ---------------------------------------------------------------------------


class TestSmearCrossModel:
    def test_along_vs_cross_track_same_formula(self) -> None:
        """Along-track and cross-track smear use the same sinc formula.

        Rotated 90° just means applying to fy instead of fx.
        """
        freq = np.linspace(0, 1e5, 100)
        w = 10e-6
        mtf_along = smear_mtf_1d(freq, w)
        mtf_cross = smear_mtf_1d(freq, w)
        np.testing.assert_array_equal(mtf_along, mtf_cross)
