"""Tests for MTF budget computation.

Validates system MTF = product of all individual MTF terms,
dominant contributor identification, and anisotropy.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.performance.mtf_budget import compute_mtf_budget

PIXEL_PITCH_M = 15e-6
FOCAL_LENGTH_M = 1.0


@pytest.fixture()
def freq() -> np.ndarray:
    """Frequency grid [cycles/mrad] covering 0 to Nyquist."""
    f_ny_m = 1.0 / (2.0 * PIXEL_PITCH_M)
    freq_m = np.linspace(0, f_ny_m, 200)
    return freq_m * FOCAL_LENGTH_M * 1e3


def _make_gaussian_mtf(freq_mrad: np.ndarray, sigma_m: float) -> np.ndarray:
    """Gaussian MTF: exp(-2 pi^2 sigma^2 f^2), with freq in cycles/mrad.

    sigma_m is the blur sigma in focal-plane metres.
    """
    freq_m = freq_mrad / (FOCAL_LENGTH_M * 1e3)
    return np.exp(-2.0 * np.pi**2 * sigma_m**2 * freq_m**2)


class TestSystemMTFProduct:
    """System MTF = product of all terms per axis."""

    @pytest.mark.level1
    def test_product_x(self, freq: np.ndarray) -> None:
        # sigma values are focal-plane blur sizes in metres.
        mtf_a_x = _make_gaussian_mtf(freq, 3e-6)
        mtf_b_x = _make_gaussian_mtf(freq, 5e-6)
        mtf_a_y = _make_gaussian_mtf(freq, 4e-6)
        mtf_b_y = _make_gaussian_mtf(freq, 6e-6)

        terms = {
            "mtf_optics_x": mtf_a_x,
            "mtf_optics_y": mtf_a_y,
            "mtf_jitter_x": mtf_b_x,
            "mtf_jitter_y": mtf_b_y,
        }

        result = compute_mtf_budget(
            terms, freq, pixel_pitch_m=PIXEL_PITCH_M, focal_length_m=FOCAL_LENGTH_M
        )

        np.testing.assert_allclose(result.system_mtf_x, mtf_a_x * mtf_b_x, atol=1e-12)
        np.testing.assert_allclose(result.system_mtf_y, mtf_a_y * mtf_b_y, atol=1e-12)

    @pytest.mark.level1
    def test_three_contributors(self, freq: np.ndarray) -> None:
        """Three contributors multiply correctly for both axes."""
        a_x = _make_gaussian_mtf(freq, 3e-6)
        b_x = _make_gaussian_mtf(freq, 5e-6)
        freq_m = freq / (FOCAL_LENGTH_M * 1e3)
        c_x = np.abs(np.sinc(freq_m * PIXEL_PITCH_M))

        terms = {
            "mtf_optics_x": a_x,
            "mtf_optics_y": a_x,
            "mtf_jitter_x": b_x,
            "mtf_jitter_y": b_x,
            "mtf_pixel_x": c_x,
            "mtf_pixel_y": c_x,
        }

        result = compute_mtf_budget(
            terms, freq, pixel_pitch_m=PIXEL_PITCH_M, focal_length_m=FOCAL_LENGTH_M
        )

        np.testing.assert_allclose(
            result.system_mtf_x, a_x * b_x * c_x, atol=1e-12
        )


class TestDominantContributor:
    """Correctly identifies the worst contributor at Nyquist."""

    @pytest.mark.level1
    def test_jitter_worst_x(self, freq: np.ndarray) -> None:
        """Make jitter_x the worst contributor."""
        # Optics is mild, jitter is severe.
        terms = {
            "mtf_optics_x": _make_gaussian_mtf(freq, 1e-6),
            "mtf_optics_y": _make_gaussian_mtf(freq, 1e-6),
            "mtf_jitter_x": _make_gaussian_mtf(freq, 10e-6),
            "mtf_jitter_y": _make_gaussian_mtf(freq, 1e-6),
        }

        result = compute_mtf_budget(
            terms, freq, pixel_pitch_m=PIXEL_PITCH_M, focal_length_m=FOCAL_LENGTH_M
        )

        assert result.dominant_contributor_at_nyquist_x == "mtf_jitter_x"

    @pytest.mark.level1
    def test_optics_worst_y(self, freq: np.ndarray) -> None:
        terms = {
            "mtf_optics_x": _make_gaussian_mtf(freq, 1e-6),
            "mtf_optics_y": _make_gaussian_mtf(freq, 10e-6),
            "mtf_jitter_x": _make_gaussian_mtf(freq, 1e-6),
            "mtf_jitter_y": _make_gaussian_mtf(freq, 1e-6),
        }

        result = compute_mtf_budget(
            terms, freq, pixel_pitch_m=PIXEL_PITCH_M, focal_length_m=FOCAL_LENGTH_M
        )

        assert result.dominant_contributor_at_nyquist_y == "mtf_optics_y"


class TestAnisotropy:
    """System MTF at Nyquist differs for x and y when terms are anisotropic."""

    @pytest.mark.level1
    def test_anisotropic_system_mtf(self, freq: np.ndarray) -> None:
        terms = {
            "mtf_optics_x": _make_gaussian_mtf(freq, 3e-6),
            "mtf_optics_y": _make_gaussian_mtf(freq, 8e-6),
        }

        result = compute_mtf_budget(
            terms, freq, pixel_pitch_m=PIXEL_PITCH_M, focal_length_m=FOCAL_LENGTH_M
        )

        # x is less degraded → higher MTF at Nyquist.
        assert result.system_mtf_at_nyquist_x > result.system_mtf_at_nyquist_y


class TestPerTermAtNyquist:
    """per_term_at_nyquist values match direct interpolation."""

    @pytest.mark.level1
    def test_values_match(self, freq: np.ndarray) -> None:
        mtf_a = _make_gaussian_mtf(freq, 5e-6)
        terms = {"mtf_test_x": mtf_a, "mtf_test_y": mtf_a}

        result = compute_mtf_budget(
            terms, freq, pixel_pitch_m=PIXEL_PITCH_M, focal_length_m=FOCAL_LENGTH_M
        )

        f_ny = 1.0 / (2.0 * PIXEL_PITCH_M)
        freq_m = freq / (FOCAL_LENGTH_M * 1e3)
        expected = float(np.interp(f_ny, freq_m, mtf_a, right=0.0))

        assert result.per_term_at_nyquist["mtf_test_x"] == pytest.approx(
            expected, abs=1e-10
        )
