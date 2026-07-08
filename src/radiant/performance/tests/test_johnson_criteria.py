"""Level 0 tests for radiant.performance.johnson_criteria (scenario 4.2).

Truth anchors are hand calculations from the Johnson-criteria definitions
(Rule 18), not values from other RADIANT code:

- N_cycles(R) = critical_dimension / (2 · IFOV · R);
  R_task = critical_dimension / (2 · IFOV · N50).
- Anchor A: critical dim 3 m, IFOV 50 µrad, detection N50 = 1.0 →
  R = 3 / (2 · 50e-6 · 1.0) = 30 000 m.
- Anchor B: same, recognition N50 = 4.0 → R = 7 500 m.
- Anchor C: same, identification N50 = 6.4 → R = 4 687.5 m.
- Round-trip: resolved_cycles at R_task returns N50.
"""

from __future__ import annotations

import pytest

from radiant.performance.johnson_criteria import (
    JOHNSON_N50,
    JohnsonCriteriaError,
    johnson_range_m,
    resolved_cycles,
)


class TestJohnsonRange:
    def test_detection_range_anchor(self) -> None:
        assert johnson_range_m(3.0, 50e-6, JOHNSON_N50["detection"]) == pytest.approx(
            30_000.0, rel=1e-9
        )

    def test_recognition_range_anchor(self) -> None:
        assert johnson_range_m(3.0, 50e-6, JOHNSON_N50["recognition"]) == pytest.approx(
            7_500.0, rel=1e-9
        )

    def test_identification_range_anchor(self) -> None:
        assert johnson_range_m(3.0, 50e-6, JOHNSON_N50["identification"]) == pytest.approx(
            4_687.5, rel=1e-9
        )

    def test_range_ordering(self) -> None:
        """Detection range > recognition > identification (harder = closer)."""
        d = johnson_range_m(10.0, 30e-6, JOHNSON_N50["detection"])
        r = johnson_range_m(10.0, 30e-6, JOHNSON_N50["recognition"])
        i = johnson_range_m(10.0, 30e-6, JOHNSON_N50["identification"])
        assert d > r > i

    def test_larger_target_farther(self) -> None:
        small = johnson_range_m(3.0, 40e-6, 4.0)
        large = johnson_range_m(30.0, 40e-6, 4.0)
        assert large == pytest.approx(10.0 * small, rel=1e-9)


class TestResolvedCycles:
    def test_roundtrip_at_task_range(self) -> None:
        """resolved_cycles at R_task equals the task N50."""
        r = johnson_range_m(3.0, 50e-6, 4.0)
        assert resolved_cycles(3.0, 50e-6, r) == pytest.approx(4.0, rel=1e-9)

    def test_cycles_fall_with_range(self) -> None:
        near = resolved_cycles(5.0, 25e-6, 5_000.0)
        far = resolved_cycles(5.0, 25e-6, 20_000.0)
        assert near == pytest.approx(4.0 * far, rel=1e-9)


class TestValidation:
    def test_zero_dimension_raises(self) -> None:
        with pytest.raises(JohnsonCriteriaError, match="critical_dimension_m"):
            johnson_range_m(0.0, 50e-6, 1.0)

    def test_zero_ifov_raises(self) -> None:
        with pytest.raises(JohnsonCriteriaError, match="ifov_rad"):
            johnson_range_m(3.0, 0.0, 1.0)

    def test_zero_n50_raises(self) -> None:
        with pytest.raises(JohnsonCriteriaError, match="n50_cycles"):
            johnson_range_m(3.0, 50e-6, 0.0)

    def test_zero_range_raises(self) -> None:
        with pytest.raises(JohnsonCriteriaError, match="range_m"):
            resolved_cycles(3.0, 50e-6, 0.0)
