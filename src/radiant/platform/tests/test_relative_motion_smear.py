"""Level-0 tests for the relative-motion smear extent (Gap 111).

The equation under test is ``s = ω_LOS · f · t_int`` — the focal-plane
translation of a target's image during one integration, given the rate at
which the sensor↔target line of sight rotates.

Truth anchors (hand calculations, stated in the task charter):

1. Crossing target, v = 200 m/s at R = 20 km, t_int = 10 ms →
   ω = 0.01 rad/s, angular smear ω·t_int = 1.0e-4 rad exactly.
2. No relative motion (ω = 0) → zero smear, exactly 0.0.
3. The velocity/range door already in ``smear.py`` is the ω = v/R special
   case of this function — bit-identical, not merely close.
"""

from __future__ import annotations

import math

import pytest

from radiant.core.exceptions import RadiantError
from radiant.platform.errors import PlatformValidationError
from radiant.platform.relative_motion_smear import smear_width_from_los_rate_m
from radiant.platform.smear import smear_width_m


class TestTruthAnchorCrossingTarget:
    """Anchor 1 — crossing target at 200 m/s, 20 km, 10 ms."""

    V_M_S = 200.0
    RANGE_M = 20_000.0
    T_INT_S = 0.010
    OMEGA_RAD_S = V_M_S / RANGE_M  # 1.0e-2 rad/s

    @pytest.mark.level0
    def test_angular_smear_is_1e_4_rad(self) -> None:
        """ω·t_int = 1.0e-4 rad — the focal-length-independent anchor."""
        f = 1.0  # unit focal length ⇒ the returned extent IS the angle [rad·m/m]
        angular_smear_rad = smear_width_from_los_rate_m(self.OMEGA_RAD_S, self.T_INT_S, f)
        assert angular_smear_rad == pytest.approx(1.0e-4, rel=1e-14)

    @pytest.mark.level0
    @pytest.mark.parametrize("focal_length_m", [0.05, 1.5, 5.0, 30.0])
    def test_focal_plane_extent_scales_with_focal_length(self, focal_length_m: float) -> None:
        s = smear_width_from_los_rate_m(self.OMEGA_RAD_S, self.T_INT_S, focal_length_m)
        assert s == pytest.approx(1.0e-4 * focal_length_m, rel=1e-14)

    @pytest.mark.level0
    def test_matches_velocity_range_door_bitwise(self) -> None:
        """Anchor 3 — same number as the pre-Gap-111 door, bit for bit."""
        f = 1.5
        legacy = smear_width_m(self.V_M_S, self.T_INT_S, f, self.RANGE_M)
        via_rate = smear_width_from_los_rate_m(self.OMEGA_RAD_S, self.T_INT_S, f)
        assert via_rate == legacy


class TestZeroCases:
    """Anchor 2 — no relative motion, no smear (exactly zero, not ~zero)."""

    @pytest.mark.level0
    def test_zero_rate_gives_exactly_zero(self) -> None:
        assert smear_width_from_los_rate_m(0.0, 0.010, 1.5) == 0.0

    @pytest.mark.level0
    def test_zero_integration_time_gives_exactly_zero(self) -> None:
        assert smear_width_from_los_rate_m(0.01, 0.0, 1.5) == 0.0

    @pytest.mark.level0
    def test_receding_target_rate_zero_gives_exactly_zero(self) -> None:
        """A purely radial relative velocity leaves ω = 0 upstream ⇒ s = 0.

        The projection that removes the radial component lives in
        ``geometry/los_rate.py``; what this module owes is that a zero rate
        propagates to an exactly-zero smear (no epsilon, no clamp).
        """
        assert smear_width_from_los_rate_m(0.0, 1.0, 100.0) == 0.0


class TestLinearity:
    """s is linear in each of the three factors — the equation, not a fit."""

    @pytest.mark.level0
    @pytest.mark.parametrize("k", [0.5, 2.0, 1e3])
    def test_linear_in_rate(self, k: float) -> None:
        base = smear_width_from_los_rate_m(1e-3, 0.02, 2.0)
        scaled = smear_width_from_los_rate_m(1e-3 * k, 0.02, 2.0)
        assert scaled == pytest.approx(k * base, rel=1e-13)

    @pytest.mark.level0
    @pytest.mark.parametrize("k", [0.5, 2.0, 1e3])
    def test_linear_in_integration_time(self, k: float) -> None:
        base = smear_width_from_los_rate_m(1e-3, 0.02, 2.0)
        scaled = smear_width_from_los_rate_m(1e-3, 0.02 * k, 2.0)
        assert scaled == pytest.approx(k * base, rel=1e-13)


class TestExtremeButValid:
    """Edge-of-domain values that are physical and must not blow up."""

    @pytest.mark.level0
    def test_tiny_rate_underflows_gracefully(self) -> None:
        s = smear_width_from_los_rate_m(1e-300, 1e-6, 1.0)
        assert s >= 0.0
        assert math.isfinite(s)

    @pytest.mark.level0
    def test_very_fast_slew_stays_finite(self) -> None:
        """1000 rad/s (a fast gimbal) × 1 s × 10 m — absurd but finite."""
        s = smear_width_from_los_rate_m(1000.0, 1.0, 10.0)
        assert s == pytest.approx(1.0e4, rel=1e-14)


class TestInvalidInputs:
    """Rule 15/16/17: every rejection is actionable and named."""

    @pytest.mark.level0
    def test_negative_rate_raises(self) -> None:
        with pytest.raises(PlatformValidationError, match="non-negative"):
            smear_width_from_los_rate_m(-1e-3, 0.01, 1.5)

    @pytest.mark.level0
    def test_negative_integration_time_raises(self) -> None:
        with pytest.raises(PlatformValidationError, match="t_int_s"):
            smear_width_from_los_rate_m(1e-3, -0.01, 1.5)

    @pytest.mark.level0
    @pytest.mark.parametrize("focal_length_m", [0.0, -1.5])
    def test_non_positive_focal_length_raises(self, focal_length_m: float) -> None:
        with pytest.raises(PlatformValidationError, match="focal_length_m"):
            smear_width_from_los_rate_m(1e-3, 0.01, focal_length_m)

    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [float("nan"), float("inf")])
    def test_non_finite_rate_raises(self, bad: float) -> None:
        with pytest.raises(PlatformValidationError, match="not finite"):
            smear_width_from_los_rate_m(bad, 0.01, 1.5)

    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [float("nan"), float("inf")])
    def test_non_finite_integration_time_raises(self, bad: float) -> None:
        with pytest.raises(PlatformValidationError, match="not finite"):
            smear_width_from_los_rate_m(1e-3, bad, 1.5)

    @pytest.mark.level0
    def test_error_is_a_radiant_error(self) -> None:
        with pytest.raises(RadiantError):
            smear_width_from_los_rate_m(-1.0, 0.01, 1.5)


class TestNoSilentNaN:
    """Rule 16: the physics layer never returns NaN/inf silently."""

    @pytest.mark.level0
    @pytest.mark.parametrize(
        ("omega", "t_int", "f"),
        [
            (0.0, 0.0, 1e-9),
            (1e-12, 1e-12, 1e-3),
            (1e3, 1e3, 1e3),
        ],
    )
    def test_finite_for_valid_inputs(self, omega: float, t_int: float, f: float) -> None:
        s = smear_width_from_los_rate_m(omega, t_int, f)
        assert math.isfinite(s)
        assert s >= 0.0
