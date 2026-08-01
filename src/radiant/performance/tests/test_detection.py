"""Tests for point-source detection range solvers (generic + Beer-Lambert).

Re-anchored 2026-08-01 (CU-263).  The solvers used to freeze the *total* noise at
the reference range, so their closed form was ``R = R_ref √(SNR_ref/T)``.  They
now solve the shot-consistent criterion ``S(R)/√(S(R) + N₀²) = T``, whose closed
form in vacuum is ``R = R_ref √(S_ref/S*)`` with

    S* = ½(T² + √(T⁴ + 4T²N₀²)),    N₀² = σ_ref² − S_ref.

Every expected value below is that analytic expression written out by hand — not
a call into the module under test (Rule 18).
"""

from __future__ import annotations

import math

import pytest

from radiant.performance.detection_beer_lambert import detection_range_beer_lambert
from radiant.performance.detection_generic import detection_range_generic


def _threshold_signal(threshold: float, floor_e: float) -> float:
    """S* by the quadratic formula, written out independently of the source."""
    t2 = threshold * threshold
    return 0.5 * (t2 + math.sqrt(t2 * t2 + 4.0 * t2 * floor_e * floor_e))


def _vacuum_range_m(ref_range_m: float, signal_e: float, threshold: float, floor_e: float) -> float:
    """R = R_ref √(S_ref/S*) — exact when the path adds no extinction."""
    return ref_range_m * math.sqrt(signal_e / _threshold_signal(threshold, floor_e))


def _total_noise_e(signal_e: float, floor_e: float) -> float:
    """σ_ref = √(S_ref + N₀²) — the pair the solvers require to be consistent."""
    return math.sqrt(signal_e + floor_e * floor_e)


class TestBeerLambertDetection:
    """Beer-Lambert atmosphere: S(R) = S_ref·(R_ref/R)²·exp(-α·ΔR)."""

    @pytest.mark.level0
    def test_no_atmosphere_inverse_square(self) -> None:
        """No extinction: detection range follows the shot-consistent closed form.

        S_ref = 10000 e- at R_ref = 1000 m over a 100 e- RMS target-free floor
        (σ_ref = √(10000 + 10000) = 141.42 e- RMS).  T = 5 ⇒
        S* = ½(25 + √(625 + 100·10000)) = ½(25 + 1000.31) = 512.66 e- ⇒
        R = 1000·√(10000/512.66) = 4417.0 m.
        """
        floor_e = 100.0
        result = detection_range_beer_lambert(
            signal_e_at_ref=10000.0,
            noise_e=_total_noise_e(10000.0, floor_e),
            ref_range_m=1000.0,
            extinction_coeff=0.0,
            snr_threshold=5.0,
        )
        assert result.ok is True
        expected = _vacuum_range_m(1000.0, 10000.0, 5.0, floor_e)
        assert expected == pytest.approx(4417.0, rel=1e-3)  # hand value above
        assert result.range_m == pytest.approx(expected, rel=1e-3)

    @pytest.mark.level0
    def test_shot_limited_floor_is_the_signal_ratio(self) -> None:
        """N₀ = 0 ⇒ S* = T² and R = R_ref·√(S_ref)/T = 1000·100/5 = 20 000 m."""
        result = detection_range_beer_lambert(
            signal_e_at_ref=10000.0,
            noise_e=100.0,  # σ² = S exactly: a purely shot-limited chain
            ref_range_m=1000.0,
            extinction_coeff=0.0,
            snr_threshold=5.0,
        )
        assert result.ok is True
        assert result.range_m == pytest.approx(20000.0, rel=1e-4)

    @pytest.mark.level1
    def test_with_extinction(self) -> None:
        """Extinction reduces detection range below inverse-square prediction."""
        noise_e = _total_noise_e(10000.0, 100.0)
        no_atm = detection_range_beer_lambert(
            signal_e_at_ref=10000.0,
            noise_e=noise_e,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
            snr_threshold=5.0,
        )
        with_atm = detection_range_beer_lambert(
            signal_e_at_ref=10000.0,
            noise_e=noise_e,
            ref_range_m=1000.0,
            extinction_coeff=1e-4,
            snr_threshold=5.0,
        )
        assert with_atm.ok is True
        assert with_atm.range_m < no_atm.range_m

    @pytest.mark.level0
    def test_convergence(self) -> None:
        """Result converges to within tolerance."""
        result = detection_range_beer_lambert(
            signal_e_at_ref=10000.0,
            noise_e=_total_noise_e(10000.0, 100.0),
            ref_range_m=1000.0,
            extinction_coeff=0.0,
            snr_threshold=5.0,
            tol_m=0.1,
        )
        assert result.ok is True
        # SNR at result should be close to threshold
        assert result.snr_at_range == pytest.approx(5.0, rel=0.01)

    @pytest.mark.level1
    def test_undetectable_at_ref(self) -> None:
        """Signal too weak even at reference range."""
        result = detection_range_beer_lambert(
            signal_e_at_ref=1.0,
            noise_e=100.0,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
            snr_threshold=5.0,
        )
        assert not result.ok
        assert "not detectable" in result.failure_reason

    @pytest.mark.level1
    def test_zero_signal_fails(self) -> None:
        result = detection_range_beer_lambert(
            signal_e_at_ref=0.0,
            noise_e=100.0,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
        )
        assert not result.ok

    @pytest.mark.level1
    def test_zero_noise_fails(self) -> None:
        result = detection_range_beer_lambert(
            signal_e_at_ref=10000.0,
            noise_e=0.0,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
        )
        assert not result.ok

    @pytest.mark.level1
    def test_signal_above_the_noise_variance_is_a_named_failure(self) -> None:
        """σ² < S has no target-free floor — an inconsistent pair, named not clamped."""
        result = detection_range_beer_lambert(
            signal_e_at_ref=1.0e6,
            noise_e=100.0,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
        )
        assert not result.ok
        assert "exceeds the total noise variance" in result.failure_reason

    @pytest.mark.level1
    def test_exceeds_max_range(self) -> None:
        """Very bright source detectable beyond max_range."""
        result = detection_range_beer_lambert(
            signal_e_at_ref=1e12,
            noise_e=_total_noise_e(1e12, 1.0),
            ref_range_m=1000.0,
            extinction_coeff=0.0,
            snr_threshold=5.0,
            max_range_m=100000.0,
        )
        assert result.range_m == 100000.0
        assert result.failure_reason is not None
        assert "exceeds" in result.failure_reason

    @pytest.mark.level1
    def test_threshold_sensitivity(self) -> None:
        """Higher threshold → shorter detection range."""
        noise_e = _total_noise_e(10000.0, 100.0)
        r5 = detection_range_beer_lambert(
            signal_e_at_ref=10000.0,
            noise_e=noise_e,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
            snr_threshold=5.0,
        )
        r10 = detection_range_beer_lambert(
            signal_e_at_ref=10000.0,
            noise_e=noise_e,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
            snr_threshold=10.0,
        )
        assert r10.range_m < r5.range_m


class TestReferenceRangeInvariance:
    """CU-263 acceptance criterion: the answer must not depend on where it is solved.

    One physical scene — a fixed source seen through a fixed constant-extinction
    atmosphere against a fixed target-free floor — evaluated from two different
    reference ranges.  The global signal law is ``S(R) = C·exp(−αR)/R²``, which
    reproduces the solver's ``S_ref·(R_ref/R)²·exp(−α(R−R_ref))`` from *any*
    reference point, so the two solves describe the same target and must return
    the same detection range.

    Under the shipped frozen-noise criterion they did not: the CU measured
    123.4 km referenced at 25 km against 182.5 km referenced at 100 km for one
    unchanged air-to-air configuration (1.48×).
    """

    ALPHA_PER_M = 1.0e-5
    FLOOR_E = 300.0
    THRESHOLD = 5.0
    C = 1.0e5 * (25.0e3**2) * math.exp(1.0e-5 * 25.0e3)  # S(25 km) = 1e5 e-

    def _signal_e(self, range_m: float) -> float:
        return self.C * math.exp(-self.ALPHA_PER_M * range_m) / (range_m * range_m)

    def _solve_from(self, ref_range_m: float) -> float:
        signal_e = self._signal_e(ref_range_m)
        result = detection_range_beer_lambert(
            signal_e_at_ref=signal_e,
            noise_e=_total_noise_e(signal_e, self.FLOOR_E),
            ref_range_m=ref_range_m,
            extinction_coeff=self.ALPHA_PER_M,
            snr_threshold=self.THRESHOLD,
            tol_m=0.01,
        )
        assert result.ok, result.failure_reason
        return result.range_m

    @pytest.mark.level0
    def test_two_reference_ranges_give_the_same_answer(self) -> None:
        near = self._solve_from(25.0e3)
        far = self._solve_from(100.0e3)
        assert near == pytest.approx(far, abs=0.05)  # 2× the 0.01 m bisection tol

    @pytest.mark.level0
    @pytest.mark.parametrize("ref_km", [25.0, 40.0, 60.0, 80.0, 100.0])
    def test_invariant_across_a_reference_range_ladder(self, ref_km: float) -> None:
        assert self._solve_from(ref_km * 1.0e3) == pytest.approx(self._solve_from(50.0e3), abs=0.05)

    @pytest.mark.level0
    def test_the_scene_is_genuinely_attenuating(self) -> None:
        """Guard: the invariance above is not the trivial vacuum case."""
        attenuated = self._solve_from(50.0e3)
        signal_e = self._signal_e(50.0e3)
        vacuum = _vacuum_range_m(50.0e3, signal_e, self.THRESHOLD, self.FLOOR_E)
        assert attenuated < 0.9 * vacuum


class TestVacuumClosedForm:
    @pytest.mark.level0
    @pytest.mark.parametrize("floor_e", [0.0, 1.0, 33.587211, 300.0, 1.0e4])
    def test_matches_the_analytic_vacuum_identity(self, floor_e: float) -> None:
        """R = R_ref √(S_ref/S*) with S* the quadratic-formula threshold signal."""
        ref_range_m, signal_e, threshold = 3.5286e7, 1.0e6, 5.0
        result = detection_range_beer_lambert(
            signal_e_at_ref=signal_e,
            noise_e=_total_noise_e(signal_e, floor_e),
            ref_range_m=ref_range_m,
            extinction_coeff=0.0,
            snr_threshold=threshold,
            max_range_m=1.0e12,
            tol_m=0.01,
        )
        assert result.ok, result.failure_reason
        expected = _vacuum_range_m(ref_range_m, signal_e, threshold, floor_e)
        assert result.range_m == pytest.approx(expected, abs=0.05)  # bisection tol

    @pytest.mark.level0
    def test_cu_263_leo_to_geo_anchor(self) -> None:
        """CU-263's shipped-10.4 numbers, solved as a bare vacuum problem.

        R_ref = 35 286.000 km, S_ref = 1 177.25 e-, σ_ref = 48.0140 e- RMS ⇒
        N₀ = 33.5872 e- RMS, S* = 180.901 e-, R = 90 015.3 km.
        """
        result = detection_range_beer_lambert(
            signal_e_at_ref=1177.2469,
            noise_e=48.01404,
            ref_range_m=3.5286e7,
            extinction_coeff=0.0,
            snr_threshold=5.0,
            max_range_m=1.0e9,
        )
        assert result.ok, result.failure_reason
        assert result.range_m / 1.0e3 == pytest.approx(90015.3, rel=1e-5)


class TestFrozenNoiseLimit:
    """As N₀² ≫ S_ref the correction vanishes: the old answer was right there."""

    @staticmethod
    def _frozen_noise_range_m(
        ref_range_m: float, signal_e: float, total_noise_e: float, threshold: float
    ) -> float:
        """The superseded closed form: R = R_ref √(SNR_ref/T), noise held fixed."""
        return ref_range_m * math.sqrt(signal_e / (threshold * total_noise_e))

    @pytest.mark.level0
    @pytest.mark.parametrize(
        ("signal_e", "floor_e", "tolerance"),
        [
            (1.0e6, 1.0e4, 3.0e-3),  # N₀²/S = 100    → measured 0.2365 % apart
            (1.0e7, 1.0e5, 3.0e-4),  # N₀²/S = 1000   → measured 0.0237 % apart
            (1.0e8, 1.0e6, 3.0e-5),  # N₀²/S = 10000  → measured 0.00237 % apart
        ],
    )
    def test_converges_to_the_frozen_noise_answer(
        self, signal_e: float, floor_e: float, tolerance: float
    ) -> None:
        ref_range_m, threshold = 1.0e4, 5.0
        total_noise_e = _total_noise_e(signal_e, floor_e)
        result = detection_range_beer_lambert(
            signal_e_at_ref=signal_e,
            noise_e=total_noise_e,
            ref_range_m=ref_range_m,
            extinction_coeff=0.0,
            snr_threshold=threshold,
            max_range_m=1.0e9,
            tol_m=0.001,
        )
        assert result.ok, result.failure_reason
        frozen = self._frozen_noise_range_m(ref_range_m, signal_e, total_noise_e, threshold)
        assert result.range_m == pytest.approx(frozen, rel=tolerance)
        # ... and never shorter: the correction only ever lengthens the range.
        assert result.range_m >= frozen


class TestGenericDetection:
    """Generic detection range with a user-supplied signal-vs-range function."""

    @pytest.mark.level0
    def test_simple_inverse_square(self) -> None:
        """S(R) = 1e6·(100/R)² against a 100 e- RMS floor, T = 5.

        S* = ½(25 + √(625 + 100·10⁴)) = 512.66 e- ⇒ R = 100·√(1e6/512.66)
        = 4417.0 m.
        """
        signal_ref, r_ref, floor_e = 1.0e6, 100.0, 100.0

        def signal_fn(r: float) -> float:
            return signal_ref * (r_ref / r) ** 2

        result = detection_range_generic(
            signal_at_range_fn=signal_fn,
            noise_floor_e=floor_e,
            snr_threshold=5.0,
            r_min_m=100.0,
            r_max_m=1e6,
            tol_m=0.1,
        )
        assert result.ok is True
        expected = _vacuum_range_m(r_ref, signal_ref, 5.0, floor_e)
        assert expected == pytest.approx(4417.0, rel=1e-3)
        assert result.range_m == pytest.approx(expected, rel=1e-3)

    @pytest.mark.level0
    def test_reference_range_invariance(self) -> None:
        """The same signal law solved from two search floors gives one answer."""
        signal_ref, r_ref, floor_e = 1.0e6, 100.0, 100.0

        def signal_fn(r: float) -> float:
            return signal_ref * (r_ref / r) ** 2

        a = detection_range_generic(signal_fn, floor_e, 5.0, r_min_m=100.0, tol_m=0.01)
        b = detection_range_generic(signal_fn, floor_e, 5.0, r_min_m=2000.0, tol_m=0.01)
        assert a.ok and b.ok
        assert a.range_m == pytest.approx(b.range_m, abs=0.05)

    @pytest.mark.level1
    def test_undetectable(self) -> None:
        def signal_fn(r: float) -> float:
            return 1.0  # Always below threshold against a 100 e- RMS floor

        result = detection_range_generic(signal_fn, 100.0, snr_threshold=5.0, r_min_m=100.0)
        assert not result.ok

    @pytest.mark.level1
    @pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
    def test_non_physical_floor_is_a_named_failure(self, bad: float) -> None:
        result = detection_range_generic(lambda r: 1.0e6 / r, bad, snr_threshold=5.0)
        assert not result.ok
        assert "noise floor" in result.failure_reason
