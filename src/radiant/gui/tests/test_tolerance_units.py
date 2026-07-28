"""Level-0 tests for tolerance unit conversion (walkthrough item 2).

The values here are hand-calculated from the definitions of the units, not from
other RADIANT code (Rule 18). The affine (temperature) cases are the ones that
matter: they are where treating a standard deviation as an absolute value gives
an answer wrong by 273.15.
"""

from __future__ import annotations

import pytest

from radiant.gui.tolerance_units import (
    ABSOLUTE,
    DIFFERENCE,
    DIMENSIONLESS,
    convert_tolerance_value,
    field_kind,
    field_unit_label,
)


class TestFieldKinds:
    @pytest.mark.parametrize(
        ("field", "expected"),
        [
            ("std", DIFFERENCE),
            ("low", ABSOLUTE),
            ("high", ABSOLUTE),
            ("sigma", DIMENSIONLESS),
            ("std_fraction", DIMENSIONLESS),
        ],
    )
    def test_known_fields(self, field: str, expected: str) -> None:
        assert field_kind(field) == expected

    def test_unknown_field_is_dimensionless(self) -> None:
        """Conservative default: leave an unrecognised number alone."""
        assert field_kind("not_a_real_field") == DIMENSIONLESS


class TestMultiplicativeUnits:
    """A purely scaling dimension converts the same way for std and for bounds."""

    def test_std_km_to_m(self) -> None:
        assert convert_tolerance_value(1.0, "std", "km", "m", "m") == pytest.approx(
            1000.0, rel=1e-12
        )

    def test_low_km_to_m(self) -> None:
        assert convert_tolerance_value(1.5, "low", "km", "m", "m") == pytest.approx(
            1500.0, rel=1e-12
        )

    def test_round_trip(self) -> None:
        there = convert_tolerance_value(30_000.0, "high", "m", "km", "m")
        assert there == pytest.approx(30.0, rel=1e-12)
        back = convert_tolerance_value(there, "high", "km", "m", "m")
        assert back == pytest.approx(30_000.0, rel=1e-12)


class TestAffineUnitsDistinguishSpreadFromBound:
    """Temperature: the offset cancels for a spread and must not for a bound."""

    def test_one_degree_celsius_of_spread_is_one_kelvin(self) -> None:
        """A σ of 1 °C is a σ of 1 K — NOT 274.15 K."""
        assert convert_tolerance_value(1.0, "std", "degC", "K", "K") == pytest.approx(1.0, abs=1e-9)

    def test_twenty_celsius_bound_is_293_kelvin(self) -> None:
        """A uniform endpoint is absolute, so the offset applies."""
        assert convert_tolerance_value(20.0, "low", "degC", "K", "K") == pytest.approx(
            293.15, abs=1e-9
        )

    def test_fahrenheit_spread_is_five_ninths_kelvin(self) -> None:
        """1 °F of spread = 5/9 K of spread (scale only, hand-calculated)."""
        assert convert_tolerance_value(1.0, "std", "degF", "K", "K") == pytest.approx(
            5.0 / 9.0, abs=1e-9
        )

    def test_fahrenheit_bound_includes_offset(self) -> None:
        """32 °F = 273.15 K exactly (the ice point)."""
        assert convert_tolerance_value(32.0, "low", "degF", "K", "K") == pytest.approx(
            273.15, abs=1e-9
        )

    def test_spread_conversion_is_linear_through_zero(self) -> None:
        """Doubling a spread doubles it in any unit — the offset never enters."""
        one = convert_tolerance_value(1.0, "std", "degC", "degF", "K")
        two = convert_tolerance_value(2.0, "std", "degC", "degF", "K")
        assert two == pytest.approx(2.0 * one, rel=1e-12)


class TestDimensionlessFieldsAreNeverConverted:
    def test_sigma_untouched_across_units(self) -> None:
        """log-normal σ scales the nominal multiplicatively — it carries no unit."""
        assert convert_tolerance_value(0.25, "sigma", "km", "m", "m") == pytest.approx(
            0.25, rel=1e-12
        )

    def test_std_fraction_untouched(self) -> None:
        assert convert_tolerance_value(0.1, "std_fraction", "degC", "K", "K") == pytest.approx(
            0.1, rel=1e-12
        )


class TestNoOpCases:
    def test_same_unit_is_identity(self) -> None:
        assert convert_tolerance_value(7.0, "std", "m", "m", "m") == pytest.approx(7.0, rel=1e-12)

    def test_empty_unit_is_identity(self) -> None:
        """A dimensionless parameter has no unit to convert between."""
        assert convert_tolerance_value(7.0, "std", "", "", "") == pytest.approx(7.0, rel=1e-12)

    def test_unregistered_pair_raises(self) -> None:
        """Rule 2: no invented conversions — the registry's KeyError propagates."""
        with pytest.raises(KeyError):
            convert_tolerance_value(1.0, "std", "m", "kelvin_per_fortnight", "m")


class TestUnitLabels:
    def test_dimensional_field_shows_the_unit(self) -> None:
        assert field_unit_label("std", "km") == "km"
        assert field_unit_label("low", "K") == "K"

    def test_sigma_explains_itself_instead_of_showing_a_unit(self) -> None:
        """A bare number next to 'sigma' must not read as metres."""
        assert field_unit_label("sigma", "m") == "(shape, ×nominal)"

    def test_std_fraction_explains_itself(self) -> None:
        assert field_unit_label("std_fraction", "m") == "(fraction of nominal)"
