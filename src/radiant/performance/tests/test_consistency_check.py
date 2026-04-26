"""Tests for dual-path MTF consistency check.

Validates that the check correctly identifies agreement or disagreement
between the PSF-path FFT and the MTF product path.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from radiant.performance.consistency_check import (
    check_dual_path_consistency,
)


@dataclass
class _FakeEPSF:
    """Minimal ePSF stub that returns pre-set MTF curves."""

    freq_m: np.ndarray
    mtf_x: np.ndarray
    mtf_y: np.ndarray

    def mtf_1d(self, axis: str = "x") -> tuple[np.ndarray, np.ndarray]:
        if axis == "x":
            return self.freq_m, self.mtf_x
        return self.freq_m, self.mtf_y


FOCAL_LENGTH_M = 1.0
PIXEL_PITCH_M = 15e-6


def _make_gaussian_mtf(freq_m: np.ndarray, sigma_m: float) -> np.ndarray:
    return np.exp(-2.0 * np.pi**2 * sigma_m**2 * freq_m**2)


class TestConsistentPaths:
    """When both paths agree, the check should pass."""

    @pytest.mark.level1
    def test_single_term_passes(self) -> None:
        freq_m = np.linspace(0, 1.0 / (2 * PIXEL_PITCH_M), 200)
        freq_mrad = freq_m * FOCAL_LENGTH_M * 1e3

        sigma = 3e-6
        mtf = _make_gaussian_mtf(freq_m, sigma)

        epsf = _FakeEPSF(freq_m=freq_m, mtf_x=mtf, mtf_y=mtf)
        terms = {"mtf_optics_x": mtf, "mtf_optics_y": mtf}

        result = check_dual_path_consistency(
            epsf, terms, freq_mrad, FOCAL_LENGTH_M
        )
        assert result.passed_x
        assert result.passed_y
        assert result.max_absolute_error_x < 1e-10

    @pytest.mark.level1
    def test_two_terms_product_passes(self) -> None:
        freq_m = np.linspace(0, 1.0 / (2 * PIXEL_PITCH_M), 200)
        freq_mrad = freq_m * FOCAL_LENGTH_M * 1e3

        mtf_a = _make_gaussian_mtf(freq_m, 3e-6)
        mtf_b = _make_gaussian_mtf(freq_m, 5e-6)
        combined = mtf_a * mtf_b

        epsf = _FakeEPSF(freq_m=freq_m, mtf_x=combined, mtf_y=combined)
        terms = {
            "mtf_optics_x": mtf_a, "mtf_optics_y": mtf_a,
            "mtf_jitter_x": mtf_b, "mtf_jitter_y": mtf_b,
        }

        result = check_dual_path_consistency(
            epsf, terms, freq_mrad, FOCAL_LENGTH_M
        )
        assert result.passed_x
        assert result.passed_y


class TestInconsistentPaths:
    """When paths disagree, the check should fail."""

    @pytest.mark.level1
    def test_missing_term_in_product_fails(self) -> None:
        """ePSF has two degradations but product only has one → FAIL."""
        freq_m = np.linspace(0, 1.0 / (2 * PIXEL_PITCH_M), 200)
        freq_mrad = freq_m * FOCAL_LENGTH_M * 1e3

        mtf_a = _make_gaussian_mtf(freq_m, 3e-6)
        mtf_b = _make_gaussian_mtf(freq_m, 8e-6)
        combined = mtf_a * mtf_b

        epsf = _FakeEPSF(freq_m=freq_m, mtf_x=combined, mtf_y=combined)
        # Only mtf_optics, missing mtf_jitter.
        terms = {"mtf_optics_x": mtf_a, "mtf_optics_y": mtf_a}

        result = check_dual_path_consistency(
            epsf, terms, freq_mrad, FOCAL_LENGTH_M
        )
        assert not result.passed_x
        assert not result.passed_y

    @pytest.mark.level1
    def test_extra_term_in_product_fails(self) -> None:
        """Product has extra term not in ePSF → FAIL."""
        freq_m = np.linspace(0, 1.0 / (2 * PIXEL_PITCH_M), 200)
        freq_mrad = freq_m * FOCAL_LENGTH_M * 1e3

        mtf_a = _make_gaussian_mtf(freq_m, 3e-6)
        mtf_b = _make_gaussian_mtf(freq_m, 8e-6)

        epsf = _FakeEPSF(freq_m=freq_m, mtf_x=mtf_a, mtf_y=mtf_a)
        terms = {
            "mtf_optics_x": mtf_a, "mtf_optics_y": mtf_a,
            "mtf_jitter_x": mtf_b, "mtf_jitter_y": mtf_b,
        }

        result = check_dual_path_consistency(
            epsf, terms, freq_mrad, FOCAL_LENGTH_M
        )
        assert not result.passed_x
        assert not result.passed_y


class TestExcludedTerms:
    """TDI terms are excluded from the comparison."""

    @pytest.mark.level1
    def test_tdi_excluded(self) -> None:
        """Adding a TDI term should NOT cause a mismatch."""
        freq_m = np.linspace(0, 1.0 / (2 * PIXEL_PITCH_M), 200)
        freq_mrad = freq_m * FOCAL_LENGTH_M * 1e3

        mtf = _make_gaussian_mtf(freq_m, 3e-6)
        mtf_tdi = _make_gaussian_mtf(freq_m, 2e-6)  # Would change product

        epsf = _FakeEPSF(freq_m=freq_m, mtf_x=mtf, mtf_y=mtf)
        terms = {
            "mtf_optics_x": mtf, "mtf_optics_y": mtf,
            "mtf_tdi_x": mtf_tdi, "mtf_tdi_y": mtf_tdi,
        }

        result = check_dual_path_consistency(
            epsf, terms, freq_mrad, FOCAL_LENGTH_M
        )
        assert result.passed_x
        assert result.passed_y


class TestAnisotropy:
    """Consistency check handles x ≠ y independently."""

    @pytest.mark.level1
    def test_x_fails_y_passes(self) -> None:
        freq_m = np.linspace(0, 1.0 / (2 * PIXEL_PITCH_M), 200)
        freq_mrad = freq_m * FOCAL_LENGTH_M * 1e3

        mtf_good = _make_gaussian_mtf(freq_m, 3e-6)
        mtf_bad = _make_gaussian_mtf(freq_m, 10e-6)

        # ePSF x has extra blur not in product; y is consistent.
        epsf = _FakeEPSF(
            freq_m=freq_m,
            mtf_x=mtf_good * mtf_bad,
            mtf_y=mtf_good,
        )
        terms = {"mtf_optics_x": mtf_good, "mtf_optics_y": mtf_good}

        result = check_dual_path_consistency(
            epsf, terms, freq_mrad, FOCAL_LENGTH_M
        )
        assert not result.passed_x
        assert result.passed_y
