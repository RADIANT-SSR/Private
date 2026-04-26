"""Level 0 tests for folded (aliased) MTF computation.

Truth anchors:
1. Analytical Gaussian MTF: exp(-a*f^2) folded sum computable analytically
2. Well-sampled limit: Q >> 1 → folded = optical (alias fraction ≈ 0)
3. Holst Ch.7: sinc detector MTF aliasing behaviour

See RADIANT_Spatial_Complete.md and Holst, "Electro-Optical Imaging System
Performance", Chapter 7.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.performance.folded_mtf import FoldedMTFResult, compute_folded_mtf

# Reference system constants
PIXEL_PITCH_M = 18e-6
F_NYQUIST = 1.0 / (2.0 * PIXEL_PITCH_M)  # ~27778 cycles/m


def _gaussian_mtf(freq: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian MTF: exp(-2*pi^2*sigma^2*f^2)."""
    return np.exp(-2.0 * np.pi**2 * sigma**2 * freq**2)


def _gaussian_folded_analytical(
    freq: np.ndarray, sigma: float, f_ny: float, n_folds: int
) -> np.ndarray:
    """Analytical folded Gaussian MTF by direct summation.

    MTF_folded(f) = Σ_{k=-N}^{N} exp(-2*pi^2*sigma^2*(f+k*f_ny)^2)
    """
    result = np.zeros_like(freq)
    for k in range(-n_folds, n_folds + 1):
        result += _gaussian_mtf(np.abs(freq + k * f_ny), sigma)
    return result


class TestGaussianMTFAnalytical:
    """Truth anchor 1: Gaussian MTF has analytically known folded sum.

    The input MTF curve must extend to at least (n_folds+1)*f_Nyquist
    so the interpolation can look up values at shifted frequencies.
    """

    @pytest.mark.level0
    def test_gaussian_folded_matches_analytical(self) -> None:
        """Numerical folded MTF matches direct Gaussian sum."""
        sigma = 1.0 / (2.0 * np.pi * F_NYQUIST * 0.8)  # FWHM ~ 0.8 * f_Nyq
        # Provide MTF data out to 4*f_Ny for 3-fold lookup.
        freq = np.linspace(0, 4 * F_NYQUIST, 800)
        mtf_optical = _gaussian_mtf(freq, sigma)

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)
        expected = _gaussian_folded_analytical(freq, sigma, F_NYQUIST, n_folds=3)

        # Compare only in baseband [0, f_Ny].
        baseband = freq <= F_NYQUIST
        np.testing.assert_allclose(result.mtf_folded[baseband], expected[baseband], rtol=1e-3)

    @pytest.mark.level0
    def test_gaussian_5_frequencies(self) -> None:
        """Verify at 5 specific frequencies with < 0.1% tolerance."""
        sigma = 1.0 / (2.0 * np.pi * F_NYQUIST * 0.6)
        freq = np.linspace(0, 4 * F_NYQUIST, 2000)
        mtf_optical = _gaussian_mtf(freq, sigma)

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)
        expected = _gaussian_folded_analytical(freq, sigma, F_NYQUIST, n_folds=3)

        # 5 representative baseband frequencies.
        baseband_idx = np.where(freq <= F_NYQUIST)[0]
        test_indices = np.linspace(0, len(baseband_idx) - 1, 5, dtype=int)
        for idx in test_indices:
            assert result.mtf_folded[idx] == pytest.approx(expected[idx], rel=1e-3), (
                f"Mismatch at freq index {idx}"
            )


class TestWellSampledLimit:
    """Truth anchor 2: Q >> 1 → folded MTF equals optical MTF."""

    @pytest.mark.level1
    def test_oversampled_folded_equals_optical(self) -> None:
        """When optical MTF is zero well before f_Nyquist, folded ≈ optical
        in the region where the MTF is significant."""
        # Narrow Gaussian: drops to ~0 well before f_Ny.
        sigma = 10.0 / (2.0 * np.pi * F_NYQUIST)
        freq = np.linspace(0, 4 * F_NYQUIST, 800)
        mtf_optical = _gaussian_mtf(freq, sigma)

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        # Compare where optical MTF is significant (> 1e-3).
        significant = (freq <= F_NYQUIST) & (mtf_optical > 1e-3)
        np.testing.assert_allclose(
            result.mtf_folded[significant],
            mtf_optical[significant],
            atol=1e-6,
        )

    @pytest.mark.level1
    def test_oversampled_alias_fraction_zero(self) -> None:
        """Well-sampled system: alias fraction ≈ 0 where MTF is significant."""
        sigma = 10.0 / (2.0 * np.pi * F_NYQUIST)
        freq = np.linspace(0, 4 * F_NYQUIST, 800)
        mtf_optical = _gaussian_mtf(freq, sigma)

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        # Check alias fraction where optical MTF is significant.
        significant = (freq <= F_NYQUIST) & (mtf_optical > 1e-3)
        np.testing.assert_allclose(result.alias_fraction[significant], 0.0, atol=1e-5)


class TestUndersampledBehaviour:
    """Undersampled (Q < 1): folded MTF > optical MTF."""

    @pytest.mark.level1
    def test_folded_ge_optical(self) -> None:
        """Folded MTF >= optical MTF at all frequencies."""
        sigma = 0.3 / (2.0 * np.pi * F_NYQUIST)  # broad — extends beyond f_Ny
        freq = np.linspace(0, F_NYQUIST, 200)
        mtf_optical = _gaussian_mtf(freq, sigma)

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        assert np.all(result.mtf_folded >= mtf_optical - 1e-15)

    @pytest.mark.level1
    def test_alias_fraction_positive(self) -> None:
        """Undersampled: alias fraction > 0 in the passband."""
        sigma = 0.3 / (2.0 * np.pi * F_NYQUIST)
        freq = np.linspace(0, F_NYQUIST, 200)
        mtf_optical = _gaussian_mtf(freq, sigma)

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        # At least some frequencies should have non-zero alias fraction.
        assert np.any(result.alias_fraction > 0.01)

    @pytest.mark.level1
    def test_folded_at_zero_freq_equals_optical(self) -> None:
        """At f=0, aliased copies contribute at ±f_Ny, ±2*f_Ny, etc.
        For broad MTF, these are non-zero, so folded(0) > optical(0)."""
        sigma = 0.3 / (2.0 * np.pi * F_NYQUIST)
        freq = np.linspace(0, F_NYQUIST, 200)
        mtf_optical = _gaussian_mtf(freq, sigma)

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        # For very broad MTF, folded(0) > optical(0) = 1.0
        assert result.mtf_folded[0] >= mtf_optical[0]


class TestNFoldsZero:
    """n_folds=0 returns optical MTF unchanged."""

    @pytest.mark.level0
    def test_no_folding(self) -> None:
        freq = np.linspace(0, F_NYQUIST, 100)
        mtf_optical = _gaussian_mtf(freq, 1.0 / (2.0 * np.pi * F_NYQUIST))

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=0)

        np.testing.assert_allclose(result.mtf_folded, mtf_optical, atol=1e-15)
        np.testing.assert_allclose(result.alias_fraction, 0.0, atol=1e-15)
        assert result.n_folds == 0


class TestEdgeCases:
    """Edge cases and error handling."""

    @pytest.mark.level1
    def test_empty_frequency_array(self) -> None:
        freq = np.array([], dtype=np.float64)
        mtf = np.array([], dtype=np.float64)

        result = compute_folded_mtf(freq, mtf, F_NYQUIST)

        assert len(result.freq) == 0
        assert len(result.mtf_folded) == 0
        assert len(result.alias_fraction) == 0

    @pytest.mark.level1
    def test_f_nyquist_zero_raises(self) -> None:
        freq = np.linspace(0, 1000, 100)
        mtf = np.ones(100)
        with pytest.raises(ValueError, match="positive"):
            compute_folded_mtf(freq, mtf, 0.0)

    @pytest.mark.level1
    def test_f_nyquist_negative_raises(self) -> None:
        freq = np.linspace(0, 1000, 100)
        mtf = np.ones(100)
        with pytest.raises(ValueError, match="positive"):
            compute_folded_mtf(freq, mtf, -100.0)

    @pytest.mark.level1
    def test_negative_mtf_raises(self) -> None:
        freq = np.linspace(0, F_NYQUIST, 100)
        mtf = np.ones(100)
        mtf[50] = -0.01
        with pytest.raises(ValueError, match="non-negative"):
            compute_folded_mtf(freq, mtf, F_NYQUIST)

    @pytest.mark.level1
    def test_result_is_frozen(self) -> None:
        freq = np.linspace(0, F_NYQUIST, 50)
        mtf = np.ones(50) * 0.5
        result = compute_folded_mtf(freq, mtf, F_NYQUIST)
        assert isinstance(result, FoldedMTFResult)


class TestAliasFraction:
    """Alias fraction properties."""

    @pytest.mark.level1
    def test_alias_fraction_bounded(self) -> None:
        """Alias fraction should be in [0, 1]."""
        sigma = 0.3 / (2.0 * np.pi * F_NYQUIST)
        freq = np.linspace(0, F_NYQUIST, 200)
        mtf_optical = _gaussian_mtf(freq, sigma)

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        assert np.all(result.alias_fraction >= 0.0)
        assert np.all(result.alias_fraction <= 1.0)

    @pytest.mark.level1
    def test_alias_fraction_zero_at_dc_when_wellsampled(self) -> None:
        """For well-sampled systems, alias fraction is 0 at DC."""
        sigma = 10.0 / (2.0 * np.pi * F_NYQUIST)
        freq = np.linspace(0, 4 * F_NYQUIST, 800)
        mtf_optical = _gaussian_mtf(freq, sigma)

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        assert result.alias_fraction[0] == pytest.approx(0.0, abs=1e-6)
