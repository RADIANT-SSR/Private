"""Level-0 tests for the CU-181 altitude-dependent downwelling model.

Every expectation is hand-computed from the model's stated equation
(``ln L`` piecewise linear in altitude), never from RADIANT output.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from scripts.downwelling_altitude import (
    ATMOSPHERE_TOP_KM,
    RADIANCE_FLOOR,
    downwelling_at_altitude,
)

# A two-wavelength ladder with a decade of decay per 10 km on channel 0 and a
# deliberately NON-monotonic channel 1 (the real MWIR stratospheric rise).
_ALT_KM = np.array([0.0, 10.0, 20.0, 30.0])
_L = np.array(
    [
        [1.0e0, 1.0e0],
        [1.0e-1, 1.0e-2],
        [1.0e-2, 1.0e-1],
        [1.0e-3, 1.0e-3],
    ]
)


@pytest.mark.level0
def test_node_altitudes_return_the_measured_value_exactly() -> None:
    for i, h in enumerate(_ALT_KM):
        got = downwelling_at_altitude(_ALT_KM, _L, float(h))
        np.testing.assert_allclose(got, _L[i], rtol=1e-12)


@pytest.mark.level0
def test_midpoint_is_the_geometric_mean_of_the_bracketing_rungs() -> None:
    """Linear in ln L ⇒ the altitude midpoint is the geometric mean."""
    got = downwelling_at_altitude(_ALT_KM, _L, 5.0)
    expected = np.sqrt(_L[0] * _L[1])  # sqrt(1 * 0.1), sqrt(1 * 0.01)
    np.testing.assert_allclose(got, expected, rtol=1e-12)
    assert got[0] == pytest.approx(math.sqrt(0.1), rel=1e-12)


@pytest.mark.level0
def test_a_non_monotonic_channel_is_interpolated_not_smoothed() -> None:
    """Channel 1 rises 10 km → 20 km; the model must follow it upward."""
    got = downwelling_at_altitude(_ALT_KM, _L, 15.0)
    assert got[1] == pytest.approx(math.sqrt(1.0e-2 * 1.0e-1), rel=1e-12)
    assert got[1] > _L[1, 1]  # brighter than the 10 km rung, as measured


@pytest.mark.level0
def test_above_the_top_rung_extrapolates_on_the_top_two_rung_slope() -> None:
    """40 km, one 10 km span past the top rung: continue the 20→30 km slope."""
    got = downwelling_at_altitude(_ALT_KM, _L, 40.0)
    # channel 0: 1e-2 → 1e-3 over 10 km ⇒ ×0.1 per 10 km ⇒ 1e-4 at 40 km.
    assert got[0] == pytest.approx(1.0e-4, rel=1e-12)
    # channel 1: 1e-1 → 1e-3 over 10 km ⇒ ×0.01 per 10 km ⇒ 1e-5 at 40 km.
    assert got[1] == pytest.approx(1.0e-5, rel=1e-12)


@pytest.mark.level0
def test_a_rising_top_pair_is_held_flat_above_the_span_not_grown() -> None:
    """No residual column can *gain* emitters with altitude (slope clamp)."""
    alt = np.array([0.0, 10.0, 20.0])
    values = np.array([[1.0], [1.0e-3], [1.0e-2]])  # rises 10 → 20 km
    held = downwelling_at_altitude(alt, values, 60.0)
    assert held[0] == pytest.approx(1.0e-2, rel=1e-12)  # flat, not 1e10
    # Inside the span the rise is still followed exactly.
    assert downwelling_at_altitude(alt, values, 15.0)[0] == pytest.approx(
        math.sqrt(1.0e-3 * 1.0e-2), rel=1e-12
    )


@pytest.mark.level0
def test_the_atmosphere_top_is_the_exact_vacuum_identity() -> None:
    """No sky above the top of the modelled atmosphere — exactly zero."""
    got = downwelling_at_altitude(_ALT_KM, _L, ATMOSPHERE_TOP_KM)
    assert np.all(got == 0.0)
    assert np.all(downwelling_at_altitude(_ALT_KM, _L, 250.0) == 0.0)


@pytest.mark.level0
def test_an_identically_zero_bin_stays_exactly_zero() -> None:
    values = np.zeros_like(_L)
    got = downwelling_at_altitude(_ALT_KM, values, 7.0)
    assert np.all(got == 0.0)
    assert np.all(np.isfinite(got))


@pytest.mark.level0
def test_a_bin_that_is_zero_at_one_rung_underflows_to_zero_not_to_nan() -> None:
    values = _L.copy()
    values[2, 0] = 0.0
    got = downwelling_at_altitude(_ALT_KM, values, 20.0)
    assert np.all(np.isfinite(got))
    assert got[0] == 0.0
    assert got[1] == pytest.approx(_L[2, 1], rel=1e-12)
    # And a query just below it interpolates toward the floor, never below zero.
    near = downwelling_at_altitude(_ALT_KM, values, 19.0)
    assert near[0] >= 0.0
    assert near[0] < _L[1, 0]


@pytest.mark.level0
@pytest.mark.parametrize(
    ("alt", "vals", "match"),
    [
        (np.array([0.0]), np.ones((1, 2)), "at least 2 rung altitudes"),
        (np.array([0.0, 10.0]), np.ones((3, 2)), "does not match"),
        (np.array([10.0, 0.0]), np.ones((2, 2)), "strictly ascend"),
        (np.array([0.0, 10.0]), -np.ones((2, 2)), "negative downwelling"),
    ],
)
def test_malformed_ladders_are_refused(alt: np.ndarray, vals: np.ndarray, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        downwelling_at_altitude(alt, vals, 5.0)


@pytest.mark.level0
def test_a_query_below_the_bottom_rung_is_refused() -> None:
    with pytest.raises(ValueError, match="below the bottom rung"):
        downwelling_at_altitude(_ALT_KM, _L, -1.0)


@pytest.mark.level0
def test_output_is_never_negative_and_never_non_finite() -> None:
    for h in (0.0, 0.3, 9.9, 25.0, 30.0, 55.0, 99.9, 100.0):
        got = downwelling_at_altitude(_ALT_KM, _L, h)
        assert np.all(got >= 0.0), h
        assert np.all(np.isfinite(got)), h
    assert RADIANCE_FLOOR > 0.0
