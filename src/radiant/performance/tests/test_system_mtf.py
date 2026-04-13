"""Tests for system MTF / Nyquist reporting.

See RADIANT_Metrics.md.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.performance.system_mtf import (
    mtf_at_freq,
    mtf_at_half_nyquist,
    mtf_at_nyquist,
    nyquist_freq,
)


class TestNyquistFreq:
    def test_basic(self) -> None:
        """f_Ny = 1/(2×15µm) ≈ 33333 cy/m."""
        f = nyquist_freq(15e-6)
        assert f == pytest.approx(1.0 / (2.0 * 15e-6), rel=1e-12)

    def test_zero_pitch_raises(self) -> None:
        with pytest.raises(ValueError, match="pixel_pitch_m"):
            nyquist_freq(0.0)


class TestMTFAtFreq:
    def test_interpolation(self) -> None:
        freq = np.linspace(0, 1e5, 100)
        mtf = np.exp(-freq / 3e4)
        val = mtf_at_freq(5e4, freq, mtf)
        expected = float(np.exp(-5e4 / 3e4))
        assert val == pytest.approx(expected, rel=1e-3)


class TestMTFAtNyquist:
    def test_basic(self) -> None:
        pitch = 15e-6
        freq = np.linspace(0, 1e5, 1000)
        mtf = np.exp(-freq / 5e4)
        val = mtf_at_nyquist(freq, mtf, pitch)
        expected = float(np.exp(-nyquist_freq(pitch) / 5e4))
        assert val == pytest.approx(expected, rel=1e-3)


class TestMTFAtHalfNyquist:
    def test_basic(self) -> None:
        pitch = 15e-6
        freq = np.linspace(0, 1e5, 1000)
        mtf = np.exp(-freq / 5e4)
        val = mtf_at_half_nyquist(freq, mtf, pitch)
        expected = float(np.exp(-nyquist_freq(pitch) / 2.0 / 5e4))
        assert val == pytest.approx(expected, rel=1e-3)
