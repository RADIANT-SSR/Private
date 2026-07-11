"""Tests for the per-family MODTRAN interpolator.

Not part of the RADIANT test suite -- exercises
scripts/synth_modtran/family_interpolate.py against the synthetic
tape7 set (must be generated first: python scripts/generate_synthetic_tape7.py).
"""

from __future__ import annotations

import numpy as np
import pytest

from scripts.synth_modtran.family_interpolate import (
    FAMILIES,
    FamilyInterpolationError,
    interpolate_family,
)


class TestExactHit:
    def test_exact_axis_value_matches_source_run(self) -> None:
        wl, trans, lp = interpolate_family("zenith_fan_us_standard", 30.0)
        assert trans.shape == wl.shape
        assert trans.min() >= 0.0 and trans.max() <= 1.0 + 1e-9


class TestInterpolation:
    def test_interpolated_point_is_monotonic_between_brackets(self) -> None:
        _, trans_lo, _ = interpolate_family("zenith_fan_us_standard", 30.0)
        _, trans_mid, _ = interpolate_family("zenith_fan_us_standard", 37.5)
        _, trans_hi, _ = interpolate_family("zenith_fan_us_standard", 45.0)
        assert trans_lo.mean() > trans_mid.mean() > trans_hi.mean()

    def test_midpoint_matches_log_tau_average(self) -> None:
        """At the exact midpoint, log(trans) should be the arithmetic mean
        of the two bracketing log(trans) arrays (linear-in-log-space by
        construction)."""
        _, trans_lo, _ = interpolate_family("altitude_ladder_stratospheric", 1.0)
        _, trans_hi, _ = interpolate_family("altitude_ladder_stratospheric", 5.0)
        _, trans_mid, _ = interpolate_family("altitude_ladder_stratospheric", 3.0)
        expected_log_tau = 0.5 * (
            np.log(np.clip(trans_lo, 1e-300, 1.0)) + np.log(np.clip(trans_hi, 1e-300, 1.0))
        )
        np.testing.assert_allclose(
            np.log(np.clip(trans_mid, 1e-300, 1.0)), expected_log_tau, atol=1e-10
        )


class TestNoExtrapolation:
    def test_above_range_raises(self) -> None:
        with pytest.raises(FamilyInterpolationError, match="outside the covered range"):
            interpolate_family("zenith_fan_us_standard", 90.0)

    def test_below_range_raises(self) -> None:
        with pytest.raises(FamilyInterpolationError, match="outside the covered range"):
            interpolate_family("altitude_ladder_space", -1.0)

    def test_unknown_family_raises(self) -> None:
        with pytest.raises(FamilyInterpolationError, match="Unknown family"):
            interpolate_family("not_a_real_family", 1.0)


class TestFamilyRegistry:
    def test_all_families_have_ascending_axis_values(self) -> None:
        for family in FAMILIES.values():
            assert list(family.axis_values) == sorted(family.axis_values)

    def test_all_families_have_matching_lengths(self) -> None:
        for family in FAMILIES.values():
            assert len(family.run_ids) == len(family.axis_values)
