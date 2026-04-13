"""Tests for TDI misalignment MTF.

Validates:
- MTF = |sinc(π·f·misalign)| against analytic formula
- Zero misalignment → unity MTF
- Pixel-to-metre conversion

See RADIANT_Spatial_Complete.md §6 (step 7).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.readout.tdi import (
    tdi_misalign_m,
    tdi_misalign_mtf_1d,
    tdi_scale_fpn,
    tdi_scale_read_noise,
    tdi_scale_shot_noise,
    tdi_scale_signal,
)

# ---------------------------------------------------------------------------
# tdi_misalign_mtf_1d
# ---------------------------------------------------------------------------


class TestTDIMisalignMTF:
    def test_dc_is_one(self) -> None:
        freq = np.array([0.0])
        mtf = tdi_misalign_mtf_1d(freq, misalign_m=1e-6)
        assert mtf[0] == pytest.approx(1.0, rel=1e-12)

    def test_analytic_sinc(self) -> None:
        """MTF matches |sinc(π·f·m)|."""
        m = 2e-6
        freq = np.linspace(0, 2.0 / m, 500)
        mtf_computed = tdi_misalign_mtf_1d(freq, m)
        mtf_analytic = np.abs(np.sinc(freq * m))
        np.testing.assert_allclose(mtf_computed, mtf_analytic, rtol=1e-12)

    def test_zero_misalign_is_unity(self) -> None:
        freq = np.linspace(0, 1e5, 100)
        mtf = tdi_misalign_mtf_1d(freq, 0.0)
        np.testing.assert_array_equal(mtf, np.ones_like(freq))

    def test_first_zero(self) -> None:
        m = 5e-6
        freq = np.array([1.0 / m])
        mtf = tdi_misalign_mtf_1d(freq, m)
        assert mtf[0] == pytest.approx(0.0, abs=1e-10)

    def test_negative_misalign_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            tdi_misalign_mtf_1d(np.array([0.0]), -1e-6)


# ---------------------------------------------------------------------------
# tdi_misalign_m
# ---------------------------------------------------------------------------


class TestTDIMisalignConversion:
    def test_basic(self) -> None:
        m = tdi_misalign_m(0.1, 15e-6)
        assert m == pytest.approx(0.1 * 15e-6, rel=1e-12)

    def test_negative_pixels_absolute(self) -> None:
        """Misalignment is absolute (direction doesn't matter)."""
        m = tdi_misalign_m(-0.1, 15e-6)
        assert m == pytest.approx(0.1 * 15e-6, rel=1e-12)

    def test_zero_misalign(self) -> None:
        assert tdi_misalign_m(0.0, 15e-6) == 0.0

    def test_zero_pitch_raises(self) -> None:
        with pytest.raises(ValueError, match="pixel_pitch_m"):
            tdi_misalign_m(0.1, 0.0)


# ---------------------------------------------------------------------------
# TDI signal/noise scaling
# ---------------------------------------------------------------------------


class TestTDISignalScaling:
    def test_signal_scales_linearly(self) -> None:
        """S_tdi = N × S_per_stage."""
        assert tdi_scale_signal(1000.0, 8) == pytest.approx(8000.0, rel=1e-12)

    def test_n_tdi_1_identity(self) -> None:
        assert tdi_scale_signal(1000.0, 1) == pytest.approx(1000.0, rel=1e-12)

    def test_invalid_n_tdi(self) -> None:
        with pytest.raises(ValueError, match="n_tdi"):
            tdi_scale_signal(1000.0, 0)


class TestTDIShotScaling:
    def test_shot_scales_sqrt_n(self) -> None:
        """Shot noise scales as √N_tdi."""
        assert tdi_scale_shot_noise(10.0, 4) == pytest.approx(20.0, rel=1e-12)

    def test_truth_anchor_snr_improvement(self) -> None:
        """N=8, S=1000 e-, σ_shot=√1000 → S_tdi=8000, σ_shot_tdi=√8000.

        SNR_tdi / SNR_1 = (8000/√8000) / (1000/√1000) = √8.
        """
        n = 8
        s = 1000.0
        snr_1 = s / math.sqrt(s)
        s_tdi = tdi_scale_signal(s, n)
        shot_tdi = tdi_scale_shot_noise(math.sqrt(s), n)
        snr_tdi = s_tdi / shot_tdi
        assert snr_tdi / snr_1 == pytest.approx(math.sqrt(n), rel=1e-10)


class TestTDIReadNoiseScaling:
    def test_read_noise_unchanged(self) -> None:
        """Read noise injected once — unchanged by TDI."""
        assert tdi_scale_read_noise(5.0) == pytest.approx(5.0, rel=1e-12)


class TestTDIFPNScaling:
    def test_fpn_scales_linearly(self) -> None:
        """FPN correlated → scales as N."""
        assert tdi_scale_fpn(10.0, 4) == pytest.approx(40.0, rel=1e-12)
