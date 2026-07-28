"""Level 0 tests for the path-aware detection-range solver (finding GF-15).

Truth anchors:

1. **Vacuum** — with no extinction the criterion is pure inverse-square and the
   closed form ``R = R_ref sqrt(SNR_ref / threshold)`` is exact.
2. **Level arm** — the path-aware solve reproduces the constant-α Beer-Lambert
   solver to the bisection tolerance, because a constant-altitude arm *is* a
   constant-extinction path.
3. **Up-looking through the vacuum tail** — bounded strictly between the
   constant-α answer (an under-estimate: it keeps attenuating past the column)
   and the vacuum answer (an over-estimate: it never attenuates at all), and
   monotone decreasing in the extinction of the measured leg.
"""

from __future__ import annotations

import math

import pytest

from radiant.core.los_geometry import LineOfSightGeometry
from radiant.performance.detection_beer_lambert import detection_range_beer_lambert
from radiant.performance.detection_path_aware import detection_range_path_aware
from radiant.performance.path_optical_depth import (
    LEVEL_ARM_MAX_RANGE_M,
    PathOpticalDepthProfile,
    resolve_path_optical_depth,
)

SIGNAL_E = 1.0e4
NOISE_E = 100.0
THRESHOLD = 5.0


def _vacuum_profile(ref_range_m: float) -> PathOpticalDepthProfile:
    return PathOpticalDepthProfile(
        ref_range_m=ref_range_m,
        ref_optical_depth=0.0,
        extinction_per_m=0.0,
        column_exit_range_m=ref_range_m,
        max_valid_range_m=math.inf,
        topology="vacuum",
    )


def _inverse_square_range(ref_range_m: float, snr_ref: float, threshold: float) -> float:
    """Closed form: S ∝ 1/R² ⇒ R = R_ref √(SNR_ref / threshold)."""
    return ref_range_m * math.sqrt(snr_ref / threshold)


class TestVacuumClosedForm:
    @pytest.mark.level0
    def test_matches_the_inverse_square_closed_form(self) -> None:
        """Anchor 1: SNR_ref = 100, threshold = 5 ⇒ R = R_ref √20."""
        ref = 1.0e5
        result = detection_range_path_aware(
            SIGNAL_E, NOISE_E, _vacuum_profile(ref), snr_threshold=THRESHOLD
        )
        assert result.ok
        expected = _inverse_square_range(ref, SIGNAL_E / NOISE_E, THRESHOLD)
        assert result.range_m == pytest.approx(expected, abs=1.0)
        # Bisection stops at tol_m = 1 m out of ~447 km, i.e. ~1e-6 in range
        # and ~2e-6 in SNR (the inverse-square amplification factor of 2).
        assert result.snr_at_range == pytest.approx(THRESHOLD, rel=1e-5)

    @pytest.mark.level0
    def test_agrees_with_the_zero_extinction_beer_lambert_solver(self) -> None:
        ref = 2.5e5
        path = detection_range_path_aware(
            SIGNAL_E, NOISE_E, _vacuum_profile(ref), snr_threshold=THRESHOLD
        )
        beer = detection_range_beer_lambert(
            SIGNAL_E, NOISE_E, ref, extinction_coeff=0.0, snr_threshold=THRESHOLD
        )
        assert path.range_m == pytest.approx(beer.range_m, abs=2.0)

    @pytest.mark.level0
    def test_scales_as_the_square_root_of_signal(self) -> None:
        ref = 1.0e5
        a = detection_range_path_aware(
            SIGNAL_E, NOISE_E, _vacuum_profile(ref), snr_threshold=THRESHOLD
        )
        b = detection_range_path_aware(
            4.0 * SIGNAL_E, NOISE_E, _vacuum_profile(ref), snr_threshold=THRESHOLD
        )
        assert b.range_m == pytest.approx(2.0 * a.range_m, rel=1e-4)


class TestLevelArmReducesToBeerLambert:
    @pytest.mark.level0
    def test_level_profile_matches_the_constant_alpha_solver(self) -> None:
        """Anchor 2: the level arm is genuinely constant-extinction."""
        los = LineOfSightGeometry(h_tgt=1.0e4, h_sensor=1.0e4, theta_o=math.pi / 2.0)
        ref, od = 5.0e4, 0.25
        profile = resolve_path_optical_depth(los, ref, od).profile
        assert profile is not None
        path = detection_range_path_aware(
            SIGNAL_E, NOISE_E, profile, snr_threshold=THRESHOLD
        )
        beer = detection_range_beer_lambert(
            SIGNAL_E,
            NOISE_E,
            ref,
            extinction_coeff=od / ref,
            snr_threshold=THRESHOLD,
        )
        assert path.ok and beer.ok
        assert path.range_m == pytest.approx(beer.range_m, abs=2.0)

    @pytest.mark.level0
    def test_search_never_exceeds_the_level_validity_bound(self) -> None:
        """A bright level target reports a bounded failure, not a limb path."""
        los = LineOfSightGeometry(h_tgt=5.0e3, h_sensor=5.0e3, theta_o=math.pi / 2.0)
        profile = resolve_path_optical_depth(los, 1.0e4, 0.0).profile
        assert profile is not None
        result = detection_range_path_aware(
            1.0e12, NOISE_E, profile, snr_threshold=THRESHOLD
        )
        assert result.range_m <= LEVEL_ARM_MAX_RANGE_M
        assert not result.ok
        assert result.failure_reason is not None


class TestUpLookingVacuumTailBounds:
    """Anchor 3: bracketed by the constant-α under-estimate and the vacuum range."""

    @staticmethod
    def _profile(od: float) -> PathOpticalDepthProfile:
        los = LineOfSightGeometry(h_tgt=5.0e5, h_sensor=0.0, theta_o=math.pi)
        resolution = resolve_path_optical_depth(los, 5.0e5, od)
        assert resolution.profile is not None
        return resolution.profile

    @pytest.mark.level0
    def test_bracketed_between_constant_alpha_and_vacuum(self) -> None:
        ref, od = 5.0e5, 0.35
        path = detection_range_path_aware(
            SIGNAL_E, NOISE_E, self._profile(od), snr_threshold=THRESHOLD
        )
        constant_alpha = detection_range_beer_lambert(
            SIGNAL_E,
            NOISE_E,
            ref,
            extinction_coeff=od / ref,
            snr_threshold=THRESHOLD,
        )
        vacuum = detection_range_path_aware(
            SIGNAL_E, NOISE_E, _vacuum_profile(ref), snr_threshold=THRESHOLD
        )
        assert path.ok and constant_alpha.ok and vacuum.ok
        assert constant_alpha.range_m < path.range_m
        assert path.range_m <= vacuum.range_m + 1.0

    @pytest.mark.level0
    def test_equals_the_vacuum_range_because_the_tail_is_vacuum(self) -> None:
        """Past the column the τ ratio is 1, so the answer is inverse-square."""
        ref = 5.0e5
        path = detection_range_path_aware(
            SIGNAL_E, NOISE_E, self._profile(0.35), snr_threshold=THRESHOLD
        )
        expected = _inverse_square_range(ref, SIGNAL_E / NOISE_E, THRESHOLD)
        assert path.range_m == pytest.approx(expected, abs=1.0)

    @pytest.mark.level0
    @pytest.mark.parametrize("od", [0.0, 0.2, 0.5, 1.0, 2.0])
    def test_monotone_non_increasing_in_extinction(self, od: float) -> None:
        """More extinction on the measured leg never lengthens the answer.

        The reference *signal* is what the chain measured through that
        extinction, so the profile's own tail is vacuum; the constant-α
        comparison below is what must shorten monotonically.
        """
        ref = 5.0e5
        constant_alpha = detection_range_beer_lambert(
            SIGNAL_E,
            NOISE_E,
            ref,
            extinction_coeff=od / ref,
            snr_threshold=THRESHOLD,
        )
        path = detection_range_path_aware(
            SIGNAL_E, NOISE_E, self._profile(od), snr_threshold=THRESHOLD
        )
        assert constant_alpha.range_m <= path.range_m + 1.0

    @pytest.mark.level0
    def test_constant_alpha_underestimate_grows_with_extinction(self) -> None:
        ref = 5.0e5
        ranges = [
            detection_range_beer_lambert(
                SIGNAL_E, NOISE_E, ref, extinction_coeff=od / ref, snr_threshold=THRESHOLD
            ).range_m
            for od in (0.1, 0.5, 1.0, 2.0)
        ]
        assert ranges == sorted(ranges, reverse=True)


class TestFailureModes:
    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [0.0, -1.0, float("nan")])
    def test_non_positive_signal_is_a_result_typed_failure(self, bad: float) -> None:
        result = detection_range_path_aware(bad, NOISE_E, _vacuum_profile(1.0e5))
        assert not result.ok
        assert result.failure_reason is not None
        assert math.isnan(result.range_m)

    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [0.0, -1.0, float("nan")])
    def test_non_positive_noise_is_a_result_typed_failure(self, bad: float) -> None:
        result = detection_range_path_aware(SIGNAL_E, bad, _vacuum_profile(1.0e5))
        assert not result.ok
        assert result.failure_reason is not None

    @pytest.mark.level0
    def test_below_threshold_at_the_reference_range(self) -> None:
        result = detection_range_path_aware(
            1.0, NOISE_E, _vacuum_profile(1.0e5), snr_threshold=THRESHOLD
        )
        assert not result.ok
        assert result.failure_reason is not None
        assert "not detectable" in result.failure_reason

    @pytest.mark.level0
    def test_empty_search_interval_is_named(self) -> None:
        profile = _vacuum_profile(1.0e6)
        result = detection_range_path_aware(
            SIGNAL_E, NOISE_E, profile, snr_threshold=THRESHOLD, max_range_m=1.0e5
        )
        assert not result.ok
        assert result.failure_reason is not None
        assert "no interval to search" in result.failure_reason

    @pytest.mark.level0
    def test_zero_threshold_is_a_result_typed_failure(self) -> None:
        result = detection_range_path_aware(
            SIGNAL_E, NOISE_E, _vacuum_profile(1.0e5), snr_threshold=0.0
        )
        assert not result.ok
        assert result.failure_reason is not None
        assert "threshold" in result.failure_reason


class TestAnalyticSearchBound:
    """The default upper bound is the exact vacuum solution, not a magic number."""

    @pytest.mark.level0
    def test_far_reference_range_is_not_truncated(self) -> None:
        """A GEO-scale reference range used to fall outside a fixed 1e7 m ceiling."""
        ref = 3.5286e7
        result = detection_range_path_aware(
            SIGNAL_E, NOISE_E, _vacuum_profile(ref), snr_threshold=THRESHOLD
        )
        assert result.ok
        expected = _inverse_square_range(ref, SIGNAL_E / NOISE_E, THRESHOLD)
        assert result.range_m == pytest.approx(expected, rel=1e-6)

    @pytest.mark.level0
    def test_attenuating_path_stays_strictly_inside_the_bound(self) -> None:
        los = LineOfSightGeometry(h_tgt=1.0e4, h_sensor=1.0e4, theta_o=math.pi / 2.0)
        profile = resolve_path_optical_depth(los, 1.0e4, 0.5).profile
        assert profile is not None
        result = detection_range_path_aware(
            SIGNAL_E, NOISE_E, profile, snr_threshold=THRESHOLD
        )
        assert result.ok
        vacuum_bound = _inverse_square_range(1.0e4, SIGNAL_E / NOISE_E, THRESHOLD)
        assert result.range_m < vacuum_bound

    @pytest.mark.level0
    def test_target_detectable_beyond_the_search_bound(self) -> None:
        result = detection_range_path_aware(
            1.0e12,
            NOISE_E,
            _vacuum_profile(1.0e5),
            snr_threshold=THRESHOLD,
            max_range_m=2.0e5,
        )
        assert not result.ok
        assert result.range_m == pytest.approx(2.0e5, rel=1e-12)


class TestTraceability:
    @pytest.mark.level0
    def test_same_inputs_give_identical_outputs(self) -> None:
        profile = _vacuum_profile(1.0e5)
        first = detection_range_path_aware(SIGNAL_E, NOISE_E, profile)
        second = detection_range_path_aware(SIGNAL_E, NOISE_E, profile)
        assert first.range_m == second.range_m
        assert first.iterations == second.iterations
