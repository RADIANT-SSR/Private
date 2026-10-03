"""Level 0: the detection-range bracket, inward and outward (Gap 136)."""

from __future__ import annotations

import math

import pytest

from radiant.performance.detection_bracket import vacuum_bracket
from radiant.performance.errors import PerformanceValidationError

_REF = 1.0e6  # 1000 km


class TestOutward:
    """Detectable where it is: the root is further away."""

    @pytest.mark.level0
    def test_the_vacuum_solution_is_the_upper_bound(self) -> None:
        """S_ref = 4 S* -> R_vac = 2 R_ref, by inverse square."""
        b = vacuum_bracket(signal_e_at_ref=400.0, signal_at_threshold_e=100.0, ref_range_m=_REF)
        assert b.inward is False
        assert b.r_min_m == pytest.approx(_REF, rel=1e-12)
        assert b.r_max_m == pytest.approx(2.0 * _REF, rel=1e-6)

    @pytest.mark.level0
    def test_the_bracket_strictly_encloses(self) -> None:
        b = vacuum_bracket(signal_e_at_ref=400.0, signal_at_threshold_e=100.0, ref_range_m=_REF)
        assert b.r_max_m > 2.0 * _REF  # margin pushes it just past the exact bound


class TestInward:
    """Below threshold where it is: the root is closer — the Gap 136 case."""

    @pytest.mark.level0
    def test_the_vacuum_solution_is_the_lower_bound(self) -> None:
        """S_ref = S*/4 -> R_vac = R_ref/2."""
        b = vacuum_bracket(signal_e_at_ref=100.0, signal_at_threshold_e=400.0, ref_range_m=_REF)
        assert b.inward is True
        assert b.r_min_m == pytest.approx(0.5 * _REF, rel=1e-6)
        assert b.r_max_m == pytest.approx(_REF, rel=1e-12)

    @pytest.mark.level0
    def test_the_bracket_strictly_encloses(self) -> None:
        b = vacuum_bracket(signal_e_at_ref=100.0, signal_at_threshold_e=400.0, ref_range_m=_REF)
        assert b.r_min_m < 0.5 * _REF

    @pytest.mark.level0
    def test_it_does_not_collapse_to_a_point(self) -> None:
        """The old failure: the interval became empty and the metric declined."""
        b = vacuum_bracket(signal_e_at_ref=1.0, signal_at_threshold_e=1.0e6, ref_range_m=_REF)
        assert b.r_max_m > b.r_min_m

    @pytest.mark.level0
    def test_a_severely_undetectable_target_still_brackets(self) -> None:
        """6 orders below threshold -> the root is 1000x closer, still finite."""
        b = vacuum_bracket(signal_e_at_ref=1.0, signal_at_threshold_e=1.0e6, ref_range_m=_REF)
        assert b.r_min_m == pytest.approx(_REF / 1000.0, rel=1e-6)


class TestTheBoundary:
    @pytest.mark.level0
    def test_exactly_at_threshold_points_outward_with_a_degenerate_bound(self) -> None:
        """S_ref == S*: the root IS the reference range."""
        b = vacuum_bracket(signal_e_at_ref=100.0, signal_at_threshold_e=100.0, ref_range_m=_REF)
        assert b.inward is False
        assert b.r_min_m == pytest.approx(_REF, rel=1e-12)
        assert b.r_max_m > _REF  # margin keeps it non-degenerate

    @pytest.mark.level0
    def test_the_factor_is_the_inverse_square_root_either_way(self) -> None:
        """One formula, both directions — that is why the mirror argument holds."""
        for s_ref, s_star in ((400.0, 100.0), (100.0, 400.0)):
            b = vacuum_bracket(
                signal_e_at_ref=s_ref, signal_at_threshold_e=s_star, ref_range_m=_REF
            )
            expected = _REF * math.sqrt(s_ref / s_star)
            bound = b.r_max_m if not b.inward else b.r_min_m
            assert bound == pytest.approx(expected, rel=1e-6)


class TestInvalidInput:
    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
    def test_bad_reference_signal_raises(self, bad: float) -> None:
        with pytest.raises(PerformanceValidationError, match="signal_e_at_ref"):
            vacuum_bracket(signal_e_at_ref=bad, signal_at_threshold_e=100.0, ref_range_m=_REF)

    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [0.0, -1.0, float("nan")])
    def test_bad_threshold_signal_raises(self, bad: float) -> None:
        with pytest.raises(PerformanceValidationError, match="signal_at_threshold_e"):
            vacuum_bracket(signal_e_at_ref=100.0, signal_at_threshold_e=bad, ref_range_m=_REF)

    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [0.0, -1.0, float("nan")])
    def test_bad_reference_range_raises(self, bad: float) -> None:
        with pytest.raises(PerformanceValidationError, match="ref_range_m"):
            vacuum_bracket(signal_e_at_ref=100.0, signal_at_threshold_e=100.0, ref_range_m=bad)
