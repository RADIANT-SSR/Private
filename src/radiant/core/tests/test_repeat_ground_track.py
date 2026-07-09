"""Level 0 tests for radiant.core.repeat_ground_track (Gap 51).

Truth anchors from standard orbital mechanics (Rule 18), not other RADIANT
code:

- Sun-synchronous inclination at 700 km is ~98.2° (well-known figure;
  sun-sync orbits sit near 98° across LEO).
- ISS (~400 km, i = 51.6°) nodal regression ≈ −5.0 °/day (published).
- Round-trip: Ω̇ at the sun-sync inclination = +0.9856 °/day (360°/year).
- Equatorial ground-track spacing at 500 km ≈ 2626 km
  (2π R_E · T_orbit / 86400 s, T_orbit ≈ 5668 s).
"""

from __future__ import annotations

import pytest

from radiant.core.repeat_ground_track import (
    RepeatGroundTrackError,
    equatorial_ground_track_spacing_m,
    nodal_regression_rate_deg_per_day,
    revisit_interval_days,
    sun_synchronous_inclination_deg,
)


class TestNodalRegression:
    def test_iss_regression(self) -> None:
        # ISS ~400 km, 51.6° → ~ −5.0 °/day (westward).
        rate = nodal_regression_rate_deg_per_day(400e3, 51.6)
        assert rate == pytest.approx(-5.0, abs=0.2)

    def test_prograde_is_negative_retrograde_positive(self) -> None:
        assert nodal_regression_rate_deg_per_day(700e3, 45.0) < 0.0
        assert nodal_regression_rate_deg_per_day(700e3, 135.0) > 0.0

    def test_polar_is_zero(self) -> None:
        assert nodal_regression_rate_deg_per_day(700e3, 90.0) == pytest.approx(0.0, abs=1e-9)


class TestSunSynchronous:
    def test_700km_inclination(self) -> None:
        assert sun_synchronous_inclination_deg(700e3) == pytest.approx(98.2, abs=0.3)

    def test_roundtrip_gives_sun_sync_rate(self) -> None:
        """Ω̇ at the solved inclination is the sun-sync rate (360°/yr)."""
        alt = 600e3
        i = sun_synchronous_inclination_deg(alt)
        assert nodal_regression_rate_deg_per_day(alt, i) == pytest.approx(
            360.0 / 365.2422, rel=1e-6
        )

    def test_inclination_is_retrograde(self) -> None:
        assert sun_synchronous_inclination_deg(800e3) > 90.0

    def test_too_high_altitude_raises(self) -> None:
        # Far above LEO the J2 torque cannot sustain sun-sync.
        with pytest.raises(RepeatGroundTrackError, match="sun-synchronous"):
            sun_synchronous_inclination_deg(60_000e3)


class TestGroundTrackSpacing:
    def test_500km_spacing(self) -> None:
        spacing_km = equatorial_ground_track_spacing_m(500e3) / 1e3
        assert spacing_km == pytest.approx(2626.0, rel=1e-2)

    def test_higher_orbit_wider_spacing(self) -> None:
        assert equatorial_ground_track_spacing_m(800e3) > equatorial_ground_track_spacing_m(400e3)


class TestRevisit:
    def test_wider_swath_shorter_revisit(self) -> None:
        narrow = revisit_interval_days(600e3, 50e3)
        wide = revisit_interval_days(600e3, 200e3)
        assert wide < narrow

    def test_higher_latitude_shorter_revisit(self) -> None:
        """Tracks converge toward the poles → shorter revisit."""
        equator = revisit_interval_days(600e3, 50e3, latitude_deg=0.0)
        high = revisit_interval_days(600e3, 50e3, latitude_deg=60.0)
        assert high < equator

    def test_zero_swath_raises(self) -> None:
        with pytest.raises(RepeatGroundTrackError, match="swath_width_m"):
            revisit_interval_days(600e3, 0.0)
