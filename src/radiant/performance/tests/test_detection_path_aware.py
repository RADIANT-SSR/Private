"""Level 0 tests for the path-aware detection-range solver (finding GF-15).

Truth anchors:

1. **Vacuum** — with no extinction the criterion is pure inverse-square and the
   closed form ``R = R_ref √(S_ref/S*)`` is exact, with ``S*`` the signal the
   shot-consistent threshold demands (CU-263; the pre-2026-08-01 frozen-noise
   form was ``R_ref √(SNR_ref/threshold)``).
2. **Level arm** — the path-aware solve reproduces the constant-α Beer-Lambert
   solver to the bisection tolerance, because a constant-altitude arm *is* a
   constant-extinction path.
3. **Up-looking through the vacuum tail** — bounded strictly between the
   constant-α answer (an under-estimate: it keeps attenuating past the column)
   and the vacuum answer (an over-estimate: it never attenuates at all), and
   monotone decreasing in the extinction of the measured leg.
4. **Down-looking through the vacuum tail** — the same shape mirrored: a
   space-based sensor is above ``h_atm_top``, so its receding leg is vacuum.

Every ``(signal, noise)`` pair below is *consistent*: σ_ref = √(S_ref + N₀²) for
the stated target-free floor, which is what the solvers decompose.
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
FLOOR_E = 100.0
NOISE_E = math.sqrt(SIGNAL_E + FLOOR_E * FLOOR_E)  # 141.42136 e- RMS
THRESHOLD = 5.0


def _total_noise_e(signal_e: float, floor_e: float = FLOOR_E) -> float:
    """σ_ref = √(S_ref + N₀²) — the consistent pair the solvers require."""
    return math.sqrt(signal_e + floor_e * floor_e)


def _vacuum_profile(ref_range_m: float) -> PathOpticalDepthProfile:
    return PathOpticalDepthProfile(
        ref_range_m=ref_range_m,
        ref_optical_depth=0.0,
        extinction_per_m=0.0,
        column_exit_range_m=ref_range_m,
        max_valid_range_m=math.inf,
        topology="vacuum",
    )


def _vacuum_range_m(
    ref_range_m: float, signal_e: float, threshold: float, floor_e: float = FLOOR_E
) -> float:
    """Closed form: S ∝ 1/R² ⇒ R = R_ref √(S_ref/S*), S* by the quadratic formula."""
    t2 = threshold * threshold
    signal_at_threshold = 0.5 * (t2 + math.sqrt(t2 * t2 + 4.0 * t2 * floor_e * floor_e))
    return ref_range_m * math.sqrt(signal_e / signal_at_threshold)


class TestVacuumClosedForm:
    @pytest.mark.level0
    def test_matches_the_inverse_square_closed_form(self) -> None:
        """Anchor 1: SNR_ref = 100, threshold = 5 ⇒ R = R_ref √20."""
        ref = 1.0e5
        result = detection_range_path_aware(
            SIGNAL_E, NOISE_E, _vacuum_profile(ref), snr_threshold=THRESHOLD
        )
        assert result.ok
        expected = _vacuum_range_m(ref, SIGNAL_E, THRESHOLD)
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
            4.0 * SIGNAL_E,
            _total_noise_e(4.0 * SIGNAL_E),
            _vacuum_profile(ref),
            snr_threshold=THRESHOLD,
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
        path = detection_range_path_aware(SIGNAL_E, NOISE_E, profile, snr_threshold=THRESHOLD)
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
            1.0e12, _total_noise_e(1.0e12), profile, snr_threshold=THRESHOLD
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
        expected = _vacuum_range_m(ref, SIGNAL_E, THRESHOLD)
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
        expected = _vacuum_range_m(ref, SIGNAL_E, THRESHOLD)
        assert result.range_m == pytest.approx(expected, rel=1e-6)

    @pytest.mark.level0
    def test_attenuating_path_stays_strictly_inside_the_bound(self) -> None:
        los = LineOfSightGeometry(h_tgt=1.0e4, h_sensor=1.0e4, theta_o=math.pi / 2.0)
        profile = resolve_path_optical_depth(los, 1.0e4, 0.5).profile
        assert profile is not None
        result = detection_range_path_aware(SIGNAL_E, NOISE_E, profile, snr_threshold=THRESHOLD)
        assert result.ok
        vacuum_bound = _vacuum_range_m(1.0e4, SIGNAL_E, THRESHOLD)
        assert result.range_m < vacuum_bound

    @pytest.mark.level0
    def test_target_detectable_beyond_the_search_bound(self) -> None:
        result = detection_range_path_aware(
            1.0e12,
            _total_noise_e(1.0e12),
            _vacuum_profile(1.0e5),
            snr_threshold=THRESHOLD,
            max_range_m=2.0e5,
        )
        assert not result.ok
        assert result.range_m == pytest.approx(2.0e5, rel=1e-12)


class TestDownLookingVacuumTail:
    """Anchor 4: the down-looking arm, routed here by CU-263 (ex-CU-236).

    A space-based sensor is above ``h_atm_top`` by construction, so the leg it
    recedes along is vacuum and the optical depth freezes at the reference
    value — the same shape as the up-looking SST/LEO→GEO case, mirrored.
    """

    @staticmethod
    def _space_los() -> LineOfSightGeometry:
        """700 km sensor, ground target, 0.3 rad target-side zenith."""
        return LineOfSightGeometry(h_tgt=0.0, h_sensor=7.0e5, theta_o=0.3)

    @pytest.mark.level0
    def test_profile_is_a_down_looking_vacuum_tail(self) -> None:
        profile = resolve_path_optical_depth(self._space_los(), 7.3e5, 0.5).profile
        assert profile is not None
        assert profile.topology == "down_vacuum_tail"
        assert profile.extinction_per_m == 0.0
        assert profile.transmittance_ratio(1.0e7) == pytest.approx(1.0, rel=1e-12)

    @pytest.mark.level0
    def test_answer_is_the_vacuum_closed_form(self) -> None:
        ref = 7.3e5
        profile = resolve_path_optical_depth(self._space_los(), ref, 0.5).profile
        assert profile is not None
        result = detection_range_path_aware(
            SIGNAL_E, NOISE_E, profile, snr_threshold=THRESHOLD, tol_m=0.01
        )
        assert result.ok, result.failure_reason
        assert result.range_m == pytest.approx(_vacuum_range_m(ref, SIGNAL_E, THRESHOLD), abs=0.05)

    @pytest.mark.level0
    def test_exceeds_the_constant_alpha_answer_it_replaces(self) -> None:
        """Ex-CU-236's direction: constant-α over-attenuates a receding sensor."""
        ref, od = 7.3e5, 0.5
        profile = resolve_path_optical_depth(self._space_los(), ref, od).profile
        assert profile is not None
        path = detection_range_path_aware(SIGNAL_E, NOISE_E, profile, snr_threshold=THRESHOLD)
        constant_alpha = detection_range_beer_lambert(
            SIGNAL_E, NOISE_E, ref, extinction_coeff=od / ref, snr_threshold=THRESHOLD
        )
        assert path.ok and constant_alpha.ok
        assert constant_alpha.range_m < path.range_m

    @pytest.mark.level0
    def test_airborne_sensor_inside_the_column_is_refused(self) -> None:
        """Rule 17: no altitude-resolved extinction above the aircraft ⇒ no answer."""
        los = LineOfSightGeometry(h_tgt=0.0, h_sensor=1.0e4, theta_o=0.2)
        resolution = resolve_path_optical_depth(los, 1.02e4, 0.5)
        assert resolution.profile is None
        assert resolution.failure_reason is not None
        assert "down-looking" in resolution.failure_reason
        assert "h_atm_top" in resolution.failure_reason

    @pytest.mark.level0
    def test_transparent_down_path_is_the_vacuum_profile(self) -> None:
        resolution = resolve_path_optical_depth(self._space_los(), 7.3e5, 0.0)
        assert resolution.profile is not None
        assert resolution.profile.topology == "vacuum"


class TestReferenceRangeInvariance:
    """CU-263 acceptance criterion, on the path-aware solver's level topology.

    One physical level arm — global law ``S(R) = C·exp(−αR)/R²`` at a fixed
    target-free floor — resolved and solved from several reference ranges.  A
    level profile's optical depth is ``α·R_ref`` by construction, so each solve
    sees the same physics from a different starting point and must return the
    same range.
    """

    ALPHA_PER_M = 2.0e-5
    THRESHOLD = 5.0
    C = 1.0e5 * (2.0e4**2) * math.exp(2.0e-5 * 2.0e4)  # S(20 km) = 1e5 e-

    def _solve_from(self, ref_range_m: float) -> float:
        los = LineOfSightGeometry(h_tgt=1.0e4, h_sensor=1.0e4, theta_o=math.pi / 2.0)
        profile = resolve_path_optical_depth(
            los, ref_range_m, self.ALPHA_PER_M * ref_range_m
        ).profile
        assert profile is not None
        signal_e = self.C * math.exp(-self.ALPHA_PER_M * ref_range_m) / ref_range_m**2
        result = detection_range_path_aware(
            signal_e,
            _total_noise_e(signal_e),
            profile,
            snr_threshold=self.THRESHOLD,
            tol_m=0.01,
        )
        assert result.ok, result.failure_reason
        return result.range_m

    @pytest.mark.level0
    @pytest.mark.parametrize("ref_km", [20.0, 30.0, 40.0, 50.0])
    def test_invariant_across_a_reference_range_ladder(self, ref_km: float) -> None:
        assert self._solve_from(ref_km * 1.0e3) == pytest.approx(self._solve_from(25.0e3), abs=0.05)

    @pytest.mark.level0
    def test_the_arm_is_genuinely_attenuating(self) -> None:
        """Guard: the invariance above is not the trivial vacuum case."""
        ref = 25.0e3
        signal_e = self.C * math.exp(-self.ALPHA_PER_M * ref) / ref**2
        assert self._solve_from(ref) < 0.9 * _vacuum_range_m(ref, signal_e, self.THRESHOLD)


class TestTraceability:
    @pytest.mark.level0
    def test_same_inputs_give_identical_outputs(self) -> None:
        profile = _vacuum_profile(1.0e5)
        first = detection_range_path_aware(SIGNAL_E, NOISE_E, profile)
        second = detection_range_path_aware(SIGNAL_E, NOISE_E, profile)
        assert first.range_m == second.range_m
        assert first.iterations == second.iterations
