"""Level 0 tests for radiant.core.solar_geometry (scenario 1.2).

Truth anchors are hand calculations from standard solar-geometry
identities (Rule 18), not values from other RADIANT code:

- Solar declination δ ≈ 23.44° at June solstice (day 172), 0° at the
  equinoxes (days 80, 266), −23.44° at December solstice (day 355).
- cos(θ_z) = sin φ sin δ + cos φ cos δ cos h, with hour angle
  h = 15°/hr · (LST − 12).
- Anchor A: equinox (δ=0), equator (φ=0), solar noon (h=0) → θ_z = 0.
- Anchor B: June solstice, φ = 23.44° (Tropic of Cancer), noon →
  δ = φ, h = 0 → cos θ_z = 1 → θ_z = 0 (sun overhead).
- Anchor C: equinox, equator, LST 10:30 (h = −22.5°) →
  cos θ_z = cos 22.5° → θ_z = 22.5°.
"""

from __future__ import annotations

import math

import pytest

from radiant.core.solar_geometry import (
    SolarGeometryError,
    solar_declination_deg,
    solar_zenith_angle_rad,
)


class TestDeclination:
    def test_equinox_zero(self) -> None:
        # Vernal (~day 80) and autumnal (~day 266) equinoxes: δ ≈ 0.
        assert solar_declination_deg(80) == pytest.approx(0.0, abs=0.5)
        assert solar_declination_deg(266) == pytest.approx(0.0, abs=1.0)

    def test_june_solstice_max(self) -> None:
        assert solar_declination_deg(172) == pytest.approx(23.44, abs=0.3)

    def test_december_solstice_min(self) -> None:
        assert solar_declination_deg(355) == pytest.approx(-23.44, abs=0.3)

    def test_out_of_range_raises(self) -> None:
        with pytest.raises(SolarGeometryError, match="day_of_year"):
            solar_declination_deg(0)
        with pytest.raises(SolarGeometryError, match="day_of_year"):
            solar_declination_deg(367)


class TestSolarZenith:
    def test_anchor_a_equinox_equator_noon(self) -> None:
        """δ=0, φ=0, noon → sun overhead (θ_z = 0)."""
        z = solar_zenith_angle_rad(latitude_deg=0.0, day_of_year=80, local_solar_time_hr=12.0)
        assert math.degrees(z) == pytest.approx(0.0, abs=0.6)

    def test_anchor_b_tropic_cancer_solstice_noon(self) -> None:
        """June solstice, φ = 23.44°, noon → sun overhead."""
        z = solar_zenith_angle_rad(latitude_deg=23.44, day_of_year=172, local_solar_time_hr=12.0)
        assert math.degrees(z) == pytest.approx(0.0, abs=0.5)

    def test_anchor_c_hour_angle_equals_zenith(self) -> None:
        """Equinox, equator: θ_z = |hour angle| = 22.5° at LST 10:30."""
        z = solar_zenith_angle_rad(latitude_deg=0.0, day_of_year=80, local_solar_time_hr=10.5)
        assert math.degrees(z) == pytest.approx(22.5, abs=0.6)

    def test_a4_anchor_35N_solstice_hourangle_15deg(self) -> None:
        """Track A4 §8d anchor: φ=35°N, solstice, H=15° → θ_z ≈ 17.42°.

        A4's idealized value uses δ=23.44° exactly and gives θ_z=17.425559°.
        RADIANT's Spencer-series declination at June solstice (day 172) is
        δ=23.452°, so RADIANT gives 17.417054° — the 0.0085° gap is purely the
        declination model, not the zenith formula. Verified: RADIANT matches
        the independent hand formula cos θ_z = sinφ sinδ + cosφ cosδ cos(15°)
        (with RADIANT's own δ) to machine precision, and lands within 0.02° of
        the A4 idealized anchor.
        """
        z_deg = math.degrees(solar_zenith_angle_rad(35.0, 172, 13.0))  # H = 15° (LST=13)
        delta = math.radians(solar_declination_deg(172))
        phi = math.radians(35.0)
        h = math.radians(15.0)
        hand = math.degrees(
            math.acos(math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.cos(h))
        )
        assert z_deg == pytest.approx(hand, rel=1e-12)  # formula composition
        assert z_deg == pytest.approx(17.425559, abs=0.02)  # A4 idealized-δ anchor

    def test_symmetry_about_noon(self) -> None:
        """θ_z(LST) = θ_z(24 − LST) — morning/afternoon symmetry."""
        z_morning = solar_zenith_angle_rad(40.0, 150, 9.0)
        z_afternoon = solar_zenith_angle_rad(40.0, 150, 15.0)
        assert z_morning == pytest.approx(z_afternoon, abs=1e-9)

    def test_high_latitude_winter_low_sun(self) -> None:
        """φ = 60°N, December solstice, noon → very low sun (large θ_z)."""
        z = solar_zenith_angle_rad(60.0, 355, 12.0)
        # cos θ_z = sin60 sin(-23.44) + cos60 cos(-23.44) = 0.0768 → 85.6°
        assert math.degrees(z) == pytest.approx(83.4, abs=1.0)

    def test_cos_zenith_matches_formula(self) -> None:
        """Direct check against sin φ sin δ + cos φ cos δ cos h."""
        lat, doy, lst = 35.0, 200, 14.0
        z = solar_zenith_angle_rad(lat, doy, lst)
        delta = math.radians(solar_declination_deg(doy))
        h = math.radians(15.0 * (lst - 12.0))
        phi = math.radians(lat)
        cos_expected = math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.cos(
            h
        )
        assert math.cos(z) == pytest.approx(cos_expected, rel=1e-12)

    def test_latitude_out_of_range_raises(self) -> None:
        with pytest.raises(SolarGeometryError, match="latitude"):
            solar_zenith_angle_rad(120.0, 100, 12.0)

    def test_local_solar_time_out_of_range_raises(self) -> None:
        with pytest.raises(SolarGeometryError, match="local_solar_time"):
            solar_zenith_angle_rad(30.0, 100, 25.0)
