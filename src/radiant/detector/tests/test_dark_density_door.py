"""Dark current declared as a current density (Gap 135).

Every datasheet and every external radiometric model states dark current as a
**current density** — A/cm² or A/m² — while RADIANT's canonical input is a
per-pixel electron rate. Converting by hand needs the pixel area *and* the
electron charge, so it is two chances to slip, and the m²/cm² choice is a 10⁴
trap. The external review of 2026-09-30 named this the highest-value interop
addition for exactly that reason.

The conversion itself is not new: :func:`dark_rate_e_per_s_from_density` landed
with Gap 123's predictive laws, whose published form is a density. What was
missing was a *door* — a parameter the analyst can set. These tests pin that
door, in both units, against hand calculations rather than against RADIANT's
own output.
"""

from __future__ import annotations

import pytest

from radiant.core.constants import q
from radiant.detector.dark_current import dark_rate_e_per_s_from_density

# The external review's own worked example (2026-09-30 report, Finding 3):
#   1 A/m^2 * (20e-6 m)^2 / 1.602e-19 C = 2.50e9 e-/s
_PITCH_M = 20e-6
_AREA_M2 = _PITCH_M**2


class TestConversionAgainstHandCalculation:
    """Level 0: J * A_pixel / q, computed by hand, in both units."""

    @pytest.mark.level0
    def test_reviewers_worked_example_in_a_per_m2(self) -> None:
        """1 A/m^2 on a 20 um pixel -> 2.50e9 e-/s (the report's own number)."""
        expected = 1.0 * _AREA_M2 / q
        assert expected == pytest.approx(2.4969e9, rel=1e-3)
        # The helper takes A/cm^2, so 1 A/m^2 = 1e-4 A/cm^2.
        assert dark_rate_e_per_s_from_density(1.0e-4, _AREA_M2) == pytest.approx(
            expected, rel=1e-12
        )

    @pytest.mark.level0
    def test_the_same_density_in_a_per_cm2(self) -> None:
        """1 A/cm^2 is 1e4 A/m^2, so the rate must be 1e4x larger."""
        per_m2 = dark_rate_e_per_s_from_density(1.0e-4, _AREA_M2)
        per_cm2 = dark_rate_e_per_s_from_density(1.0, _AREA_M2)
        assert per_cm2 / per_m2 == pytest.approx(1.0e4, rel=1e-12)

    @pytest.mark.level0
    def test_rate_is_linear_in_area(self) -> None:
        """Dark generation scales with junction area, so doubling pitch quadruples it."""
        small = dark_rate_e_per_s_from_density(1.0, _AREA_M2)
        big = dark_rate_e_per_s_from_density(1.0, (2 * _PITCH_M) ** 2)
        assert big / small == pytest.approx(4.0, rel=1e-12)

    @pytest.mark.level0
    def test_dimensional_identity(self) -> None:
        """rate [e-/s] = J [A/m^2] * A [m^2] / q [C]: a hand-written identity."""
        j_a_per_m2 = 7.3
        expected = j_a_per_m2 * _AREA_M2 / q
        assert dark_rate_e_per_s_from_density(j_a_per_m2 * 1.0e-4, _AREA_M2) == pytest.approx(
            expected, rel=1e-12
        )


class TestUnitRegistry:
    """A/m2 must be an accepted spelling, converting to the canonical A/cm2."""

    @pytest.mark.level0
    def test_a_per_m2_converts_to_a_per_cm2(self) -> None:
        from radiant.core.units import convert

        assert convert(1.0, "A/m2", "A/cm2") == pytest.approx(1.0e-4, rel=1e-12)

    @pytest.mark.level0
    def test_a_per_cm2_is_its_own_canonical(self) -> None:
        from radiant.core.units import convert

        assert convert(2.5, "A/cm2", "A/cm2") == pytest.approx(2.5, rel=1e-12)

    @pytest.mark.level0
    def test_the_round_trip_is_exact_to_floating_point(self) -> None:
        """The 10^4 trap the review named: it must not drift."""
        from radiant.core.units import convert

        assert convert(convert(3.7, "A/m2", "A/cm2"), "A/cm2", "A/m2") == pytest.approx(
            3.7, rel=1e-12
        )
