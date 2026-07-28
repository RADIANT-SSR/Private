"""Level-0 tests for the user-tabulated Cn²(h) profile (Gap 110).

Validates the interpolation convention (log-linear where both endpoints are
positive, linear across a zero, zero outside the table) and every input
validation the class promises.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere.cn2_tabulated import TabulatedCn2Profile
from radiant.core.parameters import ParameterBoundsError


def _simple() -> TabulatedCn2Profile:
    return TabulatedCn2Profile(
        altitude_m=np.array([0.0, 1000.0, 2000.0]),
        cn2_m23=np.array([1.0e-14, 1.0e-16, 1.0e-18]),
    )


class TestInterpolation:
    @pytest.mark.level0
    def test_nodes_are_reproduced_exactly(self) -> None:
        prof = _simple()
        np.testing.assert_allclose(prof.cn2(prof.altitude_m), prof.cn2_m23, rtol=1e-14, atol=0.0)

    @pytest.mark.level0
    def test_log_linear_midpoint(self) -> None:
        """Halfway between 1e-14 and 1e-16 is the geometric mean 1e-15."""
        assert float(_simple().cn2(np.array([500.0]))[0]) == pytest.approx(1e-15, rel=1e-12)

    @pytest.mark.level0
    def test_log_linear_general_point(self) -> None:
        """exp(ln c0 + t (ln c1 − ln c0)) at t = 0.25 over a two-decade step."""
        expected = math.exp(math.log(1e-14) + 0.25 * (math.log(1e-16) - math.log(1e-14)))
        assert float(_simple().cn2(np.array([250.0]))[0]) == pytest.approx(expected, rel=1e-12)

    @pytest.mark.level0
    def test_zero_endpoint_falls_back_to_linear(self) -> None:
        prof = TabulatedCn2Profile(
            altitude_m=np.array([0.0, 100.0]), cn2_m23=np.array([1.0e-14, 0.0])
        )
        assert float(prof.cn2(np.array([50.0]))[0]) == pytest.approx(5.0e-15, rel=1e-12)
        assert float(prof.cn2(np.array([100.0]))[0]) == 0.0

    @pytest.mark.level0
    def test_outside_the_table_is_zero(self) -> None:
        prof = _simple()
        values = prof.cn2(np.array([-0.0, 2000.1, 1.0e5]))
        assert float(values[1]) == 0.0
        assert float(values[2]) == 0.0

    @pytest.mark.level0
    def test_continuous_across_a_zero_interval_boundary(self) -> None:
        """The log and linear branches agree at every node, so no jump appears."""
        prof = TabulatedCn2Profile(
            altitude_m=np.array([0.0, 100.0, 200.0]),
            cn2_m23=np.array([1.0e-14, 1.0e-15, 0.0]),
        )
        left = float(prof.cn2(np.array([100.0 - 1e-6]))[0])
        right = float(prof.cn2(np.array([100.0 + 1e-6]))[0])
        assert left == pytest.approx(right, rel=1e-6)

    @pytest.mark.level0
    def test_contract_metadata(self) -> None:
        prof = _simple()
        assert prof.coverage_m == (0.0, 2000.0)
        assert prof.breakpoints_m == (0.0, 1000.0, 2000.0)
        assert "3 samples" in prof.describe()


class TestValidation:
    @pytest.mark.level0
    def test_length_mismatch_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="entries"):
            TabulatedCn2Profile(
                altitude_m=np.array([0.0, 1.0, 2.0]), cn2_m23=np.array([1e-14, 1e-15])
            )

    @pytest.mark.level0
    def test_single_sample_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="sample"):
            TabulatedCn2Profile(altitude_m=np.array([0.0]), cn2_m23=np.array([1e-14]))

    @pytest.mark.level0
    def test_non_monotone_altitude_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="strictly increasing"):
            TabulatedCn2Profile(
                altitude_m=np.array([0.0, 200.0, 100.0]),
                cn2_m23=np.array([1e-14, 1e-15, 1e-16]),
            )

    @pytest.mark.level0
    def test_duplicate_altitude_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="strictly increasing"):
            TabulatedCn2Profile(
                altitude_m=np.array([0.0, 100.0, 100.0]),
                cn2_m23=np.array([1e-14, 1e-15, 1e-16]),
            )

    @pytest.mark.level0
    def test_negative_cn2_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="negative"):
            TabulatedCn2Profile(
                altitude_m=np.array([0.0, 100.0]), cn2_m23=np.array([1e-14, -1e-15])
            )

    @pytest.mark.level0
    def test_negative_altitude_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="negative"):
            TabulatedCn2Profile(
                altitude_m=np.array([-10.0, 100.0]), cn2_m23=np.array([1e-14, 1e-15])
            )

    @pytest.mark.level0
    def test_nonfinite_sample_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="non-finite"):
            TabulatedCn2Profile(
                altitude_m=np.array([0.0, 100.0]), cn2_m23=np.array([1e-14, float("nan")])
            )

    @pytest.mark.level0
    def test_two_dimensional_input_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="1-D"):
            TabulatedCn2Profile(altitude_m=np.zeros((2, 2)), cn2_m23=np.zeros((2, 2)))

    @pytest.mark.level0
    def test_nonfinite_query_altitude_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="non-finite"):
            _simple().cn2(np.array([float("inf")]))

    @pytest.mark.level0
    def test_zero_cn2_column_is_legal(self) -> None:
        prof = TabulatedCn2Profile(altitude_m=np.array([0.0, 100.0]), cn2_m23=np.array([0.0, 0.0]))
        assert float(prof.cn2(np.array([50.0]))[0]) == 0.0
