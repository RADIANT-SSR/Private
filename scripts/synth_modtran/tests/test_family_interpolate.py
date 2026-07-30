"""Tests for the per-family MODTRAN interpolator.

Exercises ``scripts/synth_modtran/family_interpolate.py`` against the tape7
set — the staged real runs when they are present, the synthetic fallback
otherwise.

Deck-dependent tests SKIP when no deck is available (CU-272)
------------------------------------------------------------
The tape7 decks are generate-on-demand artifacts and are correctly gitignored
(Rule 26), so on a clean checkout they simply are not there. Until 2026-07-29
the three tests below that load one treated that absence as a **failure**, so
``pytest scripts/`` was red on every fresh tree — which meant a genuine
regression in this tooling would have been indistinguishable from the
environmental red, the same blind spot as CU-221 / CU-252 / CU-270 / CU-277 one
directory over.

They now skip, carrying the loader's own actionable message (which names the
generator). The registry and no-extrapolation tests do not touch a deck and
run everywhere, so the file is green-or-genuinely-broken either way.

Why skip rather than generate on demand: the generator is a committed script,
but it computes HITRAN line-by-line opacities through RADIS — an optional
heavy dependency, minutes of compute, and a network fetch on a cold cache.
That is not something a test fixture may do implicitly.
"""

from __future__ import annotations

import numpy as np
import pytest

from scripts.synth_modtran.family_interpolate import (
    FAMILIES,
    FamilyInterpolationError,
    interpolate_family,
    tape7_path,
)


def _require_family(family_name: str) -> None:
    """Skip unless every tape7 backing *family_name* is available.

    Run ids come from the registry rather than being hardcoded here, so a
    family that gains or loses a rung cannot leave this guard checking the
    wrong set. Path resolution is ``family_interpolate.tape7_path`` — the same
    one ``_load_tape7`` uses — so a staged real run set satisfies it exactly as
    a generated synthetic one does.
    """
    missing = [
        run_id for run_id in FAMILIES[family_name].run_ids if not tape7_path(run_id).exists()
    ]
    if missing:
        pytest.skip(
            f"tape7 deck(s) not available for {family_name}: {', '.join(missing)} "
            "— these are generate-on-demand artifacts (gitignored, Rule 26). "
            "Stage the real run set (modtran/real_runs/README.md) or generate the "
            "synthetic fallback: python scripts/generate_synthetic_tape7.py"
        )


class TestExactHit:
    def test_exact_axis_value_matches_source_run(self) -> None:
        _require_family("zenith_fan_us_standard")
        wl, trans, lp = interpolate_family("zenith_fan_us_standard", 30.0)
        assert trans.shape == wl.shape
        assert trans.min() >= 0.0 and trans.max() <= 1.0 + 1e-9


class TestInterpolation:
    def test_interpolated_point_is_monotonic_between_brackets(self) -> None:
        _require_family("zenith_fan_us_standard")
        _, trans_lo, _ = interpolate_family("zenith_fan_us_standard", 30.0)
        _, trans_mid, _ = interpolate_family("zenith_fan_us_standard", 37.5)
        _, trans_hi, _ = interpolate_family("zenith_fan_us_standard", 45.0)
        assert trans_lo.mean() > trans_mid.mean() > trans_hi.mean()

    def test_midpoint_matches_log_tau_average(self) -> None:
        """At the exact midpoint, log(trans) should be the arithmetic mean
        of the two bracketing log(trans) arrays (linear-in-log-space by
        construction)."""
        _require_family("altitude_ladder_stratospheric")
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
