"""Level 0 tests for the étendue acceptance cone (Gap 128).

Truth anchors are hand calculations of ``Ω = 2π(1 − cos θ)``,
``θ = arctan(1/(2N))`` [rad], evaluated independently of the implementation.
"""

from __future__ import annotations

import math

import pytest

from radiant.optics.errors import OpticsValidationError
from radiant.optics.etendue_cone import etendue_cone_solid_angle_sr


class TestExactForm:
    """The exact solid angle, and how far the paraxial form is from it."""

    @pytest.mark.level0
    def test_f6_hand_calc(self) -> None:
        """f/6: θ = arctan(1/12) rad ⇒ Ω = 0.0217031... sr (plan §4 anchor 1)."""
        assert etendue_cone_solid_angle_sr(6.0) == pytest.approx(0.0217036, abs=1e-7)

    @pytest.mark.level0
    def test_f2_hand_calc(self) -> None:
        """f/2: θ = arctan(0.25) rad ⇒ Ω = 2π(1 − cos θ) = 0.1876002... sr."""
        expected = 2.0 * math.pi * (1.0 - math.cos(math.atan(0.25)))
        assert etendue_cone_solid_angle_sr(2.0) == pytest.approx(expected, rel=1e-12)
        assert etendue_cone_solid_angle_sr(2.0) == pytest.approx(0.1876002, abs=1e-7)

    @pytest.mark.level0
    def test_paraxial_delta_f6(self) -> None:
        """At f/6 the paraxial π/(4N²) over-states the cone by 0.52 %."""
        exact = etendue_cone_solid_angle_sr(6.0)
        paraxial = math.pi / (4.0 * 6.0**2)
        assert paraxial == pytest.approx(0.0218166, abs=1e-7)
        assert (paraxial - exact) / exact == pytest.approx(0.005205, abs=1e-5)

    @pytest.mark.level0
    def test_paraxial_delta_f2(self) -> None:
        """At f/2 the paraxial form over-states the cone by 4.7 % — fast optics."""
        exact = etendue_cone_solid_angle_sr(2.0)
        paraxial = math.pi / (4.0 * 2.0**2)
        assert (paraxial - exact) / exact == pytest.approx(0.046638, abs=1e-5)

    @pytest.mark.level1
    def test_monotonic_in_f_number(self) -> None:
        """A faster system accepts a larger cone."""
        values = [etendue_cone_solid_angle_sr(n) for n in (0.5, 1.0, 2.0, 6.0, 20.0, 100.0)]
        assert values == sorted(values, reverse=True)

    @pytest.mark.level1
    def test_never_exceeds_hemisphere(self) -> None:
        """Ω < 2π sr for every positive f/# — unlike the paraxial form."""
        for n in (0.05, 0.3, 1.0, 200.0):
            assert 0.0 < etendue_cone_solid_angle_sr(n) < 2.0 * math.pi
        # The paraxial form does not respect the bound: π/(4·0.05²) = 314 sr.
        assert math.pi / (4.0 * 0.05**2) > 2.0 * math.pi


class TestFailureModes:
    """Edge-of-domain and invalid inputs."""

    @pytest.mark.level1
    @pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
    def test_invalid_f_number_raises(self, bad: float) -> None:
        with pytest.raises(OpticsValidationError, match="f_number"):
            etendue_cone_solid_angle_sr(bad)

    @pytest.mark.level1
    def test_very_slow_system_underflows_to_small_not_zero(self) -> None:
        """f/1000 gives a tiny but strictly positive cone (no underflow to 0)."""
        omega = etendue_cone_solid_angle_sr(1000.0)
        assert 0.0 < omega < 1e-5
