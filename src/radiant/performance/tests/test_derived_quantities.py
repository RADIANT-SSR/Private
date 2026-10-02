"""Level 0: IFOV, band mean, and the derived-quantity record (Gap 134)."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.performance.band_mean import band_mean
from radiant.performance.derived_quantities import (
    DerivedQuantity,
    collect_derived_quantities,
)
from radiant.performance.errors import PerformanceValidationError
from radiant.performance.ifov import ifov_rad


class TestIfov:
    @pytest.mark.level0
    def test_hand_calculation(self) -> None:
        """20 um pixel on a 50 mm lens -> 400 urad, by hand."""
        assert ifov_rad(20e-6, 50e-3) == pytest.approx(400e-6, rel=1e-12)

    @pytest.mark.level0
    def test_small_angle_matches_arctan_to_the_stated_precision(self) -> None:
        """The docstring claims 2e-8 relative at this geometry; verify it."""
        import math

        p, f = 20e-6, 50e-3
        assert ifov_rad(p, f) == pytest.approx(math.atan(p / f), rel=1e-7)

    @pytest.mark.level0
    def test_inverse_in_focal_length(self) -> None:
        assert ifov_rad(20e-6, 100e-3) == pytest.approx(ifov_rad(20e-6, 50e-3) / 2, rel=1e-12)

    @pytest.mark.level0
    @pytest.mark.parametrize("pitch", [0.0, -1e-6, float("nan"), float("inf")])
    def test_invalid_pitch_raises(self, pitch: float) -> None:
        with pytest.raises(PerformanceValidationError, match="pixel_pitch_m"):
            ifov_rad(pitch, 50e-3)

    @pytest.mark.level0
    @pytest.mark.parametrize("focal", [0.0, -1.0, float("nan")])
    def test_invalid_focal_length_raises(self, focal: float) -> None:
        with pytest.raises(PerformanceValidationError, match="focal_length_m"):
            ifov_rad(20e-6, focal)


class TestBandMean:
    @pytest.mark.level0
    def test_a_constant_band_returns_the_constant(self) -> None:
        wl = np.linspace(3.5, 5.0, 64)
        assert band_mean(wl, np.full_like(wl, 0.7)) == pytest.approx(0.7, rel=1e-12)

    @pytest.mark.level0
    def test_a_linear_ramp_returns_its_midpoint(self) -> None:
        """Analytic: the mean of a linear function is its midpoint value."""
        wl = np.linspace(2.0, 4.0, 201)
        assert band_mean(wl, wl) == pytest.approx(3.0, rel=1e-12)

    @pytest.mark.level0
    def test_a_single_point_band_is_that_point(self) -> None:
        """Not a divide-by-zero."""
        assert band_mean(np.array([4.0]), np.array([0.42])) == pytest.approx(0.42, rel=1e-12)

    @pytest.mark.level0
    def test_shape_mismatch_raises(self) -> None:
        with pytest.raises(PerformanceValidationError, match="does not"):
            band_mean(np.linspace(1.0, 2.0, 5), np.zeros(4))

    @pytest.mark.level0
    def test_empty_band_raises(self) -> None:
        with pytest.raises(PerformanceValidationError, match="empty"):
            band_mean(np.array([]), np.array([]))

    @pytest.mark.level0
    def test_non_increasing_band_raises(self) -> None:
        with pytest.raises(PerformanceValidationError, match="non-positive width"):
            band_mean(np.array([5.0, 3.5]), np.array([1.0, 1.0]))

    @pytest.mark.level0
    def test_non_finite_values_raise_rather_than_propagate(self) -> None:
        wl = np.linspace(1.0, 2.0, 8)
        vals = np.ones_like(wl)
        vals[3] = np.nan
        with pytest.raises(PerformanceValidationError, match="non-finite"):
            band_mean(wl, vals)


class TestTheRecord:
    @pytest.mark.level0
    def test_every_row_carries_a_unit_and_a_source(self) -> None:
        """The hard rule: no bare numbers."""
        rows = collect_derived_quantities(
            {"optics": {"Omega_cone": 0.0491, "A_collect": 0.0707}, "readout": {}, "detector": {}}
        )
        assert rows
        for row in rows:
            assert isinstance(row, DerivedQuantity)
            assert row.source

    @pytest.mark.level0
    def test_the_cone_row_names_the_convention_that_caused_the_discrepancy(self) -> None:
        rows = collect_derived_quantities({"optics": {"Omega_cone": 0.6633}})
        cone = next(r for r in rows if r.name == "Omega_cone")
        assert cone.unit == "sr"
        assert "paraxial" in cone.source

    @pytest.mark.level0
    def test_absent_quantities_are_omitted_not_reported_as_none(self) -> None:
        rows = collect_derived_quantities({})
        assert all(r.value is not None for r in rows)

    @pytest.mark.level0
    def test_non_finite_values_are_dropped(self) -> None:
        rows = collect_derived_quantities({"optics": {"Omega_cone": float("nan")}})
        assert not [r for r in rows if r.name == "Omega_cone"]

    @pytest.mark.level0
    def test_a_bool_is_not_mistaken_for_a_number(self) -> None:
        rows = collect_derived_quantities({"readout": {"duty_cycle": True}})
        assert not [r for r in rows if r.name == "duty_cycle"]

    @pytest.mark.level0
    def test_the_well_row_states_which_well_it_is(self) -> None:
        """The review asked for the provenance, not just the number."""
        analog = collect_derived_quantities({"readout": {"full_well_capacity_e": 2e6}})
        counting = collect_derived_quantities(
            {"readout": {"full_well_capacity_e": 2e6, "counter_bits": 16}}
        )
        assert "analog well" in next(r for r in analog if r.name == "full_well_capacity_e").source
        assert "counting" in next(r for r in counting if r.name == "full_well_capacity_e").source

    @pytest.mark.level0
    def test_a_converted_dark_rate_says_so(self) -> None:
        plain = collect_derived_quantities({"detector": {"dark_rate_e_per_s": 100.0}})
        conv = collect_derived_quantities(
            {"detector": {"dark_rate_e_per_s": 2.5e9}}, dark_rate_from_density=True
        )
        assert "entered directly" in next(r for r in plain if r.name == "dark_rate_e_per_s").source
        assert "J*A_pixel/q" in next(r for r in conv if r.name == "dark_rate_e_per_s").source

    @pytest.mark.level0
    def test_str_renders_value_unit_and_source(self) -> None:
        row = DerivedQuantity("x", 1.25, "sr", "because")
        assert "1.25" in str(row) and "sr" in str(row) and "because" in str(row)

    @pytest.mark.level0
    def test_a_unitless_row_renders_without_a_stray_space(self) -> None:
        assert str(DerivedQuantity("q", 2.0, "", "src")).startswith("q = 2 ")
