"""Tests for radiant.detector.shot_noise."""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.detector.shot_noise import (
    combine_in_quadrature,
    shot_noise_e,
    shot_noise_e_array,
)

# ---------------------------------------------------------------------------
# Scalar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "n,expected",
    [
        (0.0, 0.0),
        (1.0, 1.0),
        (4.0, 2.0),
        (100.0, 10.0),
        (1e6, 1000.0),
    ],
)
def test_shot_noise_scalar_truth_anchor(n: float, expected: float) -> None:
    # Poisson variance = mean → σ = √N.
    assert shot_noise_e(n) == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("bad", [-1.0, -1e-9, math.inf, -math.inf, math.nan])
def test_shot_noise_scalar_rejects_invalid(bad: float) -> None:
    with pytest.raises(ValueError):
        shot_noise_e(bad)


# ---------------------------------------------------------------------------
# Array
# ---------------------------------------------------------------------------


def test_shot_noise_array_matches_sqrt() -> None:
    arr = np.array([0.0, 1.0, 4.0, 9.0, 16.0, 100.0])
    out = shot_noise_e_array(arr)
    assert np.allclose(out, np.sqrt(arr), rtol=1e-12)


def test_shot_noise_array_2d_preserves_shape() -> None:
    arr = np.array([[1.0, 4.0], [9.0, 16.0]])
    out = shot_noise_e_array(arr)
    assert out.shape == arr.shape
    assert np.allclose(out, np.array([[1.0, 2.0], [3.0, 4.0]]), rtol=1e-12)


def test_shot_noise_array_rejects_negatives() -> None:
    with pytest.raises(ValueError, match="negative"):
        shot_noise_e_array(np.array([1.0, -0.1, 4.0]))


def test_shot_noise_array_rejects_nonfinite() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        shot_noise_e_array(np.array([1.0, np.nan, 4.0]))
    with pytest.raises(ValueError, match="non-finite"):
        shot_noise_e_array(np.array([1.0, np.inf, 4.0]))


# ---------------------------------------------------------------------------
# Quadrature combination
# ---------------------------------------------------------------------------


def test_quadrature_trivial_cases() -> None:
    assert combine_in_quadrature() == 0.0
    assert combine_in_quadrature(3.0) == pytest.approx(3.0, rel=1e-12)


def test_quadrature_pythagorean_truth_anchor() -> None:
    # 3-4-5 triangle.
    assert combine_in_quadrature(3.0, 4.0) == pytest.approx(5.0, rel=1e-12)


def test_quadrature_multiple_terms() -> None:
    # √(1+4+4+16) = √25 = 5.
    assert combine_in_quadrature(1.0, 2.0, 2.0, 4.0) == pytest.approx(5.0, rel=1e-12)


def test_quadrature_rejects_invalid_terms() -> None:
    with pytest.raises(ValueError, match="term"):
        combine_in_quadrature(3.0, -1.0)
    with pytest.raises(ValueError, match="term"):
        combine_in_quadrature(3.0, math.nan)
    with pytest.raises(ValueError, match="term"):
        combine_in_quadrature(3.0, math.inf)
