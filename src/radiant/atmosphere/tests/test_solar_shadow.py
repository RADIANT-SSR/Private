"""Level-0 tests for the per-altitude solar illumination test (GF-9).

Truth anchors for the shadow height, the two equivalent formulations, and the
Rule-16/17 failure modes.  The shadow height is a textbook quantity —
``h = R_E·(sec δ − 1)`` with ``δ`` the solar depression — so it is checkable
against published twilight-geometry numbers rather than against other RADIANT
code (Rule 18).
"""

from __future__ import annotations

import math

import pytest

from radiant.atmosphere.solar_shadow import (
    shadow_height_m,
    solar_tangent_radius_m,
    sunlit,
)
from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError


class TestAboveHorizon:
    @pytest.mark.level0
    def test_sun_above_horizontal_is_always_sunlit(self) -> None:
        """θ_s ≤ π/2 — every altitude, including the surface, is lit."""
        for theta_s_deg in (0.0, 30.0, 60.0, 89.9, 90.0):
            for h_m in (0.0, 1_000.0, 100_000.0, 1.0e7):
                assert sunlit(h_m, math.radians(theta_s_deg)) is True

    @pytest.mark.level0
    def test_no_shadow_above_the_horizontal(self) -> None:
        assert shadow_height_m(0.0) == 0.0
        assert shadow_height_m(math.pi / 2.0) == 0.0


class TestShadowHeight:
    @pytest.mark.level0
    @pytest.mark.parametrize(
        ("depression_deg", "expected_km"),
        [
            # h = R_E (sec δ − 1), R_E = 6371.0 km.  Hand calculation:
            (1.0, 6371.0 * (1.0 / math.cos(math.radians(1.0)) - 1.0)),
            (5.0, 6371.0 * (1.0 / math.cos(math.radians(5.0)) - 1.0)),
            (12.0, 6371.0 * (1.0 / math.cos(math.radians(12.0)) - 1.0)),
            (18.0, 6371.0 * (1.0 / math.cos(math.radians(18.0)) - 1.0)),
        ],
    )
    def test_matches_the_secant_formula(self, depression_deg: float, expected_km: float) -> None:
        """Truth anchor 1 — the closed-form shadow height [km]."""
        theta_s = math.pi / 2.0 + math.radians(depression_deg)
        assert shadow_height_m(theta_s) / 1000.0 == pytest.approx(expected_km, rel=1e-12)

    @pytest.mark.level0
    def test_known_twilight_values(self) -> None:
        """Truth anchor 2 — published twilight shadow heights.

        Civil twilight ends at 6° depression, nautical at 12°, astronomical at
        18°; the corresponding shadow heights are the standard ≈ 35 km,
        ≈ 142 km and ≈ 328 km quoted in twilight-geometry references.
        """
        assert shadow_height_m(math.pi / 2 + math.radians(6.0)) / 1000.0 == pytest.approx(
            35.1, rel=0.01
        )
        assert shadow_height_m(math.pi / 2 + math.radians(12.0)) / 1000.0 == pytest.approx(
            141.9, rel=0.01
        )
        assert shadow_height_m(math.pi / 2 + math.radians(18.0)) / 1000.0 == pytest.approx(
            328.4, rel=0.01
        )

    @pytest.mark.level0
    def test_sunlit_and_shadow_height_are_the_same_statement(self) -> None:
        """Truth anchor 3 — the tangent form and the secant form agree.

        ``(R_E + h) sin θ_s ≥ R_E``  ⟺  ``h ≥ R_E (sec δ − 1)``.
        """
        for depression_deg in (0.5, 2.0, 7.5, 15.0, 40.0):
            theta_s = math.pi / 2.0 + math.radians(depression_deg)
            h_shadow = shadow_height_m(theta_s)
            assert sunlit(h_shadow * (1.0 + 1e-9), theta_s) is True
            assert sunlit(h_shadow * (1.0 - 1e-9), theta_s) is False

    @pytest.mark.level0
    def test_antisolar_point_is_never_lit(self) -> None:
        assert shadow_height_m(math.pi) == math.inf
        assert sunlit(1.0e9, math.pi) is False


class TestSunlitCases:
    @pytest.mark.level0
    def test_sunlit_target_over_dark_ground(self) -> None:
        """The GF-9 headline case: 5° depression darkens the ground while a
        60 km booster is still in sunlight (shadow height ≈ 24.3 km)."""
        theta_s = math.pi / 2.0 + math.radians(5.0)
        assert sunlit(0.0, theta_s) is False
        assert sunlit(20_000.0, theta_s) is False
        assert sunlit(60_000.0, theta_s) is True

    @pytest.mark.level0
    def test_terminator_is_inclusive(self) -> None:
        """Exactly tangent counts as lit — a grazing ray is not blocked."""
        assert sunlit(0.0, math.pi / 2.0) is True


class TestTangentRadius:
    @pytest.mark.level0
    def test_above_horizon_returns_the_start_radius(self) -> None:
        """The traversed arc has no interior perigee when the sun is up."""
        assert solar_tangent_radius_m(5_000.0, 0.3) == pytest.approx(R_EARTH_M + 5_000.0, rel=1e-15)

    @pytest.mark.level0
    def test_below_horizon_tangent_matches_the_geometry(self) -> None:
        theta_s = math.pi / 2.0 + math.radians(3.0)
        h = 40_000.0
        expected = (R_EARTH_M + h) * math.sin(theta_s)
        assert solar_tangent_radius_m(h, theta_s) == pytest.approx(expected, rel=1e-15)
        assert expected > R_EARTH_M  # sunlit ⇒ tangent clears the surface

    @pytest.mark.level0
    def test_shadowed_point_raises_actionably(self) -> None:
        """Rule 17: no below-surface tangent radius is ever handed out."""
        theta_s = math.pi / 2.0 + math.radians(10.0)
        with pytest.raises(ParameterBoundsError) as exc:
            solar_tangent_radius_m(1_000.0, theta_s)
        message = str(exc.value)
        assert "shadow" in message
        assert "sunlit()" in message


class TestFailureModes:
    @pytest.mark.level0
    @pytest.mark.parametrize("theta_s", [-0.1, math.pi + 1e-6, float("nan"), float("inf")])
    def test_out_of_domain_solar_zenith_raises(self, theta_s: float) -> None:
        with pytest.raises(ParameterBoundsError):
            sunlit(0.0, theta_s)

    @pytest.mark.level0
    @pytest.mark.parametrize("h_m", [-1.0, float("nan"), float("-inf")])
    def test_bad_altitude_raises(self, h_m: float) -> None:
        with pytest.raises(ParameterBoundsError):
            sunlit(h_m, 0.5)

    @pytest.mark.level0
    def test_no_nan_or_inf_leaks_from_sunlit(self) -> None:
        """Rule 16: the answer is a hard bool for every legal input."""
        for h in (0.0, 1e3, 1e5, 1e8):
            for t in (0.0, 1.0, math.pi / 2, 2.0, math.pi):
                assert isinstance(sunlit(h, t), bool)
