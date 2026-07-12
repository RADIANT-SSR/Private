"""Level 0 tests for radiant.core.orbit (scenario 3.1).

Truth anchors are hand calculations / published values from circular
two-body orbital mechanics (Rule 18), not values from other RADIANT code:

- μ = 3.986e14 m³/s², R_E = 6.371e6 m (mean).
- 500 km orbit: a = 6.871e6 m → v = √(μ/a) = 7.616 km/s,
  T = 2π a / v = 5668 s = 94.5 min. (Standard LEO figure.)
- ISS ~420 km: a = 6.791e6 m → v ≈ 7.66 km/s, T ≈ 5570 s ≈ 92.8 min
  (published ISS period is ~92–93 min).
- Ground-track speed at 500 km: v_g = v · R_E/a = 7616 · 6371/6871
  = 7062 m/s (slower than the inertial speed).
"""

from __future__ import annotations

import math

import pytest

from radiant.core.orbit import (
    OrbitError,
    ground_track_speed_m_s,
    orbital_period_s,
    orbital_velocity_m_s,
)


class TestOrbitalVelocity:
    def test_500km_velocity(self) -> None:
        # v = √(μ/a), a = 6371+500 km → 7.616 km/s
        assert orbital_velocity_m_s(500e3) == pytest.approx(7616.0, rel=1e-3)

    def test_iss_velocity(self) -> None:
        assert orbital_velocity_m_s(420e3) == pytest.approx(7660.0, rel=2e-3)

    def test_velocity_decreases_with_altitude(self) -> None:
        assert orbital_velocity_m_s(400e3) > orbital_velocity_m_s(800e3)


class TestOrbitalPeriod:
    def test_500km_period(self) -> None:
        # T = 2π √(a³/μ) → 5668 s (94.5 min)
        assert orbital_period_s(500e3) == pytest.approx(5668.0, rel=2e-3)

    def test_iss_period_minutes(self) -> None:
        # Published ISS period ~92–93 min.
        assert orbital_period_s(420e3) / 60.0 == pytest.approx(92.8, abs=0.5)

    def test_period_matches_2pi_a_over_v(self) -> None:
        """Identity: T = 2π a / v with a = R_E + h."""
        from radiant.core.constants import R_EARTH_M

        alt = 650e3
        a = R_EARTH_M + alt
        expected = 2.0 * math.pi * a / orbital_velocity_m_s(alt)
        assert orbital_period_s(alt) == pytest.approx(expected, rel=1e-12)


class TestGroundTrackSpeed:
    def test_500km_ground_speed(self) -> None:
        assert ground_track_speed_m_s(500e3) == pytest.approx(7062.0, rel=2e-3)

    def test_ground_speed_below_orbital_speed(self) -> None:
        """v_g = v · R_E/a < v always (a > R_E)."""
        assert ground_track_speed_m_s(500e3) < orbital_velocity_m_s(500e3)


class TestValidation:
    def test_zero_altitude_raises(self) -> None:
        with pytest.raises(OrbitError, match="altitude_m"):
            orbital_period_s(0.0)

    def test_negative_altitude_raises(self) -> None:
        with pytest.raises(OrbitError, match="altitude_m"):
            orbital_velocity_m_s(-100e3)
