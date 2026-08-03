"""Level 0 tests for folded (aliased) MTF computation.

Truth anchors:
1. Analytical Gaussian MTF: exp(-a*f^2) folded sum computable analytically
2. Well-sampled limit: Q >> 1 → folded = optical (alias fraction ≈ 0)
3. Holst Ch.7: sinc detector MTF aliasing behaviour
4. Analytic 1-D aperture (triangle) MTF, 1 - f/f_c: exact rational folded
   values at f = f_Nyquist for a band-limited (oversampled) and an
   above-Nyquist (undersampled) cutoff — CU-209.

Sampling replicates the pre-sampling spectrum at multiples of the **sampling**
frequency f_s = 1/pitch = 2*f_Nyquist, not at multiples of f_Nyquist (CU-209).

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
F_SAMPLE = 1.0 / PIXEL_PITCH_M  # = 2 * F_NYQUIST — the replication period


def _gaussian_mtf(freq: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian MTF: exp(-2*pi^2*sigma^2*f^2)."""
    return np.exp(-2.0 * np.pi**2 * sigma**2 * freq**2)


def _gaussian_folded_analytical(
    freq: np.ndarray, sigma: float, f_sample: float, n_folds: int
) -> np.ndarray:
    """Analytical folded Gaussian MTF by direct summation.

    MTF_folded(f) = Σ_{k=-N}^{N} exp(-2*pi^2*sigma^2*(f+k*f_sample)^2)
    """
    result = np.zeros_like(freq)
    for k in range(-n_folds, n_folds + 1):
        result += _gaussian_mtf(np.abs(freq + k * f_sample), sigma)
    return result


def _triangle_mtf(freq: np.ndarray, f_cutoff: float) -> np.ndarray:
    """Analytic 1-D (slit-aperture) diffraction MTF: max(1 - f/f_c, 0).

    Exactly reproduced by linear interpolation on any grid containing the
    kink at ``f_cutoff``, so the folded sums below are exact rationals.
    """
    return np.maximum(1.0 - freq / f_cutoff, 0.0)


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
        expected = _gaussian_folded_analytical(freq, sigma, F_SAMPLE, n_folds=3)

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
        expected = _gaussian_folded_analytical(freq, sigma, F_SAMPLE, n_folds=3)

        # 5 representative baseband frequencies.
        baseband_idx = np.where(freq <= F_NYQUIST)[0]
        test_indices = np.linspace(0, len(baseband_idx) - 1, 5, dtype=int)
        for idx in test_indices:
            assert result.mtf_folded[idx] == pytest.approx(expected[idx], rel=1e-3), (
                f"Mismatch at freq index {idx}"
            )


class TestReplicationAtNyquist:
    """Truth anchor 4 (CU-209): the replication period is f_s = 2*f_Nyquist.

    Both anchors use the analytic 1-D aperture MTF ``1 - f/f_c``, evaluated at
    ``f = f_Nyquist`` — the frequency at which ``mtf_folded_at_nyquist`` and
    ``alias_fraction_at_nyquist`` are sampled.  Shifting by ``k*f_Nyquist``
    instead puts the ``k = -1`` replica on DC, which contributes ``MTF(0) = 1``
    to every system; the expected values below are the hand-summed correct
    ones and are not reachable that way.
    """

    @pytest.mark.level0
    def test_oversampled_folded_is_zero_at_nyquist(self) -> None:
        """Band-limited optics (f_c = f_Ny/2): nothing to alias, folded = 0.

        Hand sum at ``f = f_Ny`` with replication at ``f_s = 2*f_Ny``:
          k =  0 → MTF(f_Ny)      = 0   (above cutoff)
          k = -1 → MTF(|f_Ny − 2 f_Ny|) = MTF(f_Ny) = 0
          k = ±2, ±3 → 3 f_Ny, 5 f_Ny, 7 f_Ny → 0
          total = 0 exactly.
        The absolute value is the anchor (per the CU-209 owner ruling); the
        alias fraction there is anchored separately by
        ``TestAliasFractionFloor`` (CU-315).
        """
        f_cutoff = 0.5 * F_NYQUIST
        freq = np.linspace(0.0, 6.0, 1201) * F_NYQUIST
        mtf_optical = _triangle_mtf(freq, f_cutoff)
        idx_ny = int(np.argmin(np.abs(freq - F_NYQUIST)))

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        assert result.mtf_folded[idx_ny] == pytest.approx(0.0, abs=1e-12)

    @pytest.mark.level0
    def test_undersampled_folded_at_nyquist_is_double_optical(self) -> None:
        """Cutoff at 3*f_Ny (Q = 2/3): folded = optical + the k = −1 replica.

        Hand sum at ``f = f_Ny`` with ``f_c = 3 f_Ny`` and ``f_s = 2 f_Ny``:
          k =  0 → MTF(f_Ny)            = 1 − 1/3 = 2/3
          k = -1 → MTF(|f_Ny − 2 f_Ny|) = MTF(f_Ny) = 2/3
          k = +1 → MTF(3 f_Ny)          = 0        (at cutoff)
          k = -2 → MTF(3 f_Ny)          = 0
          k = ±3, +2 → 5 f_Ny, 7 f_Ny   = 0
          total = 4/3;  alias fraction = (4/3 − 2/3)/(4/3) = 1/2 exactly.
        At Nyquist the −1 replica always lands back on ``f_Ny``, so the folded
        value there is exactly twice the optical MTF — the doubling the
        dual-band example shows (0.533365 = 2 × 0.266683).
        """
        f_cutoff = 3.0 * F_NYQUIST
        freq = np.linspace(0.0, 6.0, 1201) * F_NYQUIST
        mtf_optical = _triangle_mtf(freq, f_cutoff)
        idx_ny = int(np.argmin(np.abs(freq - F_NYQUIST)))

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        assert result.mtf_folded[idx_ny] == pytest.approx(4.0 / 3.0, rel=1e-12)
        assert result.mtf_folded[idx_ny] == pytest.approx(2.0 * mtf_optical[idx_ny], rel=1e-12)
        assert result.alias_fraction[idx_ny] == pytest.approx(0.5, rel=1e-12)

    @pytest.mark.level0
    def test_undersampled_folded_at_half_nyquist(self) -> None:
        """Off-Nyquist anchor pinning the replication period itself.

        ``f = 0.5 f_Ny``, ``f_c = 3 f_Ny``, ``f_s = 2 f_Ny``:
          k =  0 → MTF(0.5 f_Ny) = 1 − 1/6  = 5/6
          k = -1 → MTF(1.5 f_Ny) = 1 − 1/2  = 1/2
          k = +1 → MTF(2.5 f_Ny) = 1 − 5/6  = 1/6
          k = -2 → MTF(3.5 f_Ny) = 0;  higher orders 0
          total = 3/2 exactly.
        """
        f_cutoff = 3.0 * F_NYQUIST
        freq = np.linspace(0.0, 6.0, 1201) * F_NYQUIST
        mtf_optical = _triangle_mtf(freq, f_cutoff)
        idx_half = int(np.argmin(np.abs(freq - 0.5 * F_NYQUIST)))

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        assert result.mtf_folded[idx_half] == pytest.approx(1.5, rel=1e-12)


class TestAliasFractionFloor:
    """CU-315: an absolute floor on the folded MTF below which the alias
    fraction is reported as exactly zero.

    ``alias_fraction = (folded − optical)/folded`` is a ratio of two numbers
    that both vanish for optics cutting off below Nyquist, so without a floor
    it divides float noise by float noise.  The floor is
    ``ALIAS_FRACTION_MTF_FLOOR`` = 1e-9 of the DC response ``MTF(0) = 1``.
    """

    @pytest.mark.level0
    def test_oversampled_alias_fraction_is_exactly_zero_at_nyquist(self) -> None:
        """Band-limited optics (f_c = f_Ny/2): folded = 0 → alias fraction 0.

        Same hand-summed configuration as
        ``test_oversampled_folded_is_zero_at_nyquist``: every replica lands
        above the cutoff, so the folded response at ``f_Ny`` is zero and there
        is no aliased energy to report.
        """
        f_cutoff = 0.5 * F_NYQUIST
        freq = np.linspace(0.0, 6.0, 1201) * F_NYQUIST
        mtf_optical = _triangle_mtf(freq, f_cutoff)
        idx_ny = int(np.argmin(np.abs(freq - F_NYQUIST)))

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        assert result.alias_fraction[idx_ny] == 0.0

    @pytest.mark.level0
    def test_oversampled_with_roundoff_residue_reports_zero(self) -> None:
        """The dual-band LWIR condition: 0/0 at the 1e-16 level → 0.

        A pupil-autocorrelation MTF does not return *identically* zero above
        cutoff — it carries a ~1e-16 round-off residue, so both the optical
        and the folded value at ``f_Ny`` are float noise and their ratio is an
        arbitrary number in [0, 1] (0.944314 in the shipped dual-band example,
        ~0.83 on the deterministic residue used here).  With the floor the
        answer is the physical one: an oversampled design aliases nothing.
        """
        f_cutoff = 0.5 * F_NYQUIST
        freq = np.linspace(0.0, 6.0, 1201) * F_NYQUIST
        residue = 1.0e-16 * (1.0 + 0.5 * np.sin(freq / F_NYQUIST))
        mtf_optical = _triangle_mtf(freq, f_cutoff) + residue
        idx_ny = int(np.argmin(np.abs(freq - F_NYQUIST)))

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        assert result.mtf_folded[idx_ny] < 1e-14  # numerically nothing
        assert result.mtf_folded[idx_ny] > 0.0  # but not identically zero
        assert result.alias_fraction[idx_ny] == 0.0

    @pytest.mark.level0
    def test_floored_where_folded_below_epsilon(self) -> None:
        """A genuinely aliased shape scaled below the floor reports zero.

        The triangle with ``f_c = 3 f_Ny`` folds to ``4/3 × A`` at ``f_Ny``
        with an exact alias fraction of 1/2 at any amplitude ``A``.  Scaled to
        ``A = 0.375e-9`` the folded value is ``0.5e-9`` — below the 1e-9 floor
        — so the reported fraction is 0, not 1/2.
        """
        amplitude = 0.375e-9
        f_cutoff = 3.0 * F_NYQUIST
        freq = np.linspace(0.0, 6.0, 1201) * F_NYQUIST
        mtf_optical = amplitude * _triangle_mtf(freq, f_cutoff)
        idx_ny = int(np.argmin(np.abs(freq - F_NYQUIST)))

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        assert result.mtf_folded[idx_ny] == pytest.approx(0.5e-9, rel=1e-12)
        assert result.alias_fraction[idx_ny] == 0.0

    @pytest.mark.level0
    def test_marginal_case_just_above_epsilon_is_untouched(self) -> None:
        """The same shape at ``A = 1.5e-9`` (folded = 2e-9 > floor) keeps 1/2.

        The floor must not eat real fractions: one power of ten above the
        epsilon the exact 1/2 anchor still holds to full double precision.
        """
        amplitude = 1.5e-9
        f_cutoff = 3.0 * F_NYQUIST
        freq = np.linspace(0.0, 6.0, 1201) * F_NYQUIST
        mtf_optical = amplitude * _triangle_mtf(freq, f_cutoff)
        idx_ny = int(np.argmin(np.abs(freq - F_NYQUIST)))

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        assert result.mtf_folded[idx_ny] == pytest.approx(2.0e-9, rel=1e-12)
        assert result.alias_fraction[idx_ny] == pytest.approx(0.5, rel=1e-9)

    @pytest.mark.level0
    def test_undersampled_fractions_are_bit_identical(self) -> None:
        """Above the floor the array is bit-for-bit the unfloored ratio.

        Recomputes ``(folded − optical)/folded`` from the returned folded
        curve with the identical operations and asserts exact equality, so any
        rescaling, clipping, or reordering introduced by the floor would fail.
        """
        f_cutoff = 3.0 * F_NYQUIST
        freq = np.linspace(0.0, 6.0, 1201) * F_NYQUIST
        mtf_optical = _triangle_mtf(freq, f_cutoff)

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        above = result.mtf_folded > 1e-9
        expected = (result.mtf_folded[above] - mtf_optical[above]) / result.mtf_folded[above]
        assert np.array_equal(result.alias_fraction[above], expected)
        # And every sample of this undersampled case is above the floor
        # except where the folded response is identically zero.
        assert np.all(result.alias_fraction[~above] == 0.0)


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
    """Undersampled (Q < 1): folded MTF > optical MTF.

    The optical MTF must be supplied out past the first replica
    (``2 * f_Nyquist``) for there to be anything to alias — frequencies
    beyond the supplied grid interpolate to zero.  These grids run to
    ``4 * f_Nyquist`` and the assertions are restricted to the baseband.
    """

    @pytest.mark.level1
    def test_folded_ge_optical(self) -> None:
        """Folded MTF >= optical MTF at all frequencies."""
        sigma = 0.3 / (2.0 * np.pi * F_NYQUIST)  # broad — extends beyond f_Ny
        freq = np.linspace(0, 4 * F_NYQUIST, 800)
        mtf_optical = _gaussian_mtf(freq, sigma)

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        assert np.all(result.mtf_folded >= mtf_optical - 1e-15)

    @pytest.mark.level1
    def test_alias_fraction_positive(self) -> None:
        """Undersampled: alias fraction > 0 in the passband."""
        sigma = 0.3 / (2.0 * np.pi * F_NYQUIST)
        freq = np.linspace(0, 4 * F_NYQUIST, 800)
        mtf_optical = _gaussian_mtf(freq, sigma)

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        # At least some baseband frequencies should have non-zero alias fraction.
        baseband = freq <= F_NYQUIST
        assert np.any(result.alias_fraction[baseband] > 0.01)

    @pytest.mark.level1
    def test_folded_at_zero_freq_equals_optical(self) -> None:
        """At f=0, aliased copies contribute at ±2*f_Ny, ±4*f_Ny, etc.
        For broad MTF, these are non-zero, so folded(0) > optical(0)."""
        sigma = 0.3 / (2.0 * np.pi * F_NYQUIST)
        freq = np.linspace(0, 4 * F_NYQUIST, 800)
        mtf_optical = _gaussian_mtf(freq, sigma)

        result = compute_folded_mtf(freq, mtf_optical, F_NYQUIST, n_folds=3)

        # For very broad MTF, folded(0) > optical(0) = 1.0 (audit B1-8: was
        # >=, which a no-op folded==optical also passes; the aliased ±2*f_Ny
        # and ±4*f_Ny copies make this strict — here folded(0) ≈ 3.64;
        # the ±6*f_Ny copies fall outside the supplied grid and read zero).
        assert result.mtf_folded[0] > mtf_optical[0]


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
        freq = np.linspace(0, 4 * F_NYQUIST, 800)
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
