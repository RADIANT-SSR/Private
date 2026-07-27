"""Level-0 tests for the Rule-B LOS-termination classifier.

``classify_los_termination`` answers one question — what does the line of
sight run into *after* the target — and Rule B (Use-Case Matrix §3.2.5) turns
that answer into a background descriptor.  The invariants below are the ones
that selection depends on.
"""

from __future__ import annotations

import math
import warnings

import pytest

from radiant.core.constants import R_EARTH_M
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.los_termination import classify_los_termination
from radiant.core.parameters import ParameterBoundsError

H_ATM_TOP_M = 1.0e5


def _los(theta_o: float, h_tgt: float, h_sensor: float | None = None) -> LineOfSightGeometry:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return LineOfSightGeometry(
            h_tgt=h_tgt, h_sensor=h_sensor, theta_o=theta_o, h_atm_top=H_ATM_TOP_M
        )


class TestContinuationGeometry:
    @pytest.mark.level0
    def test_continuation_zenith_is_the_supplement_of_theta_o(self) -> None:
        """ζ_c = π − θ_o exactly — the ray reversed at the target [rad]."""
        # θ_o just above π/2 admits no up-looking triangle for a ground sensor
        # (the ray bottoms out above it), so the up-looking samples are the
        # steeper ones the geometry actually permits.
        for theta_o_deg in (0.0, 17.0, 89.0, 135.0, 179.0, 180.0):
            theta_o = math.radians(theta_o_deg)
            los = _los(theta_o, 10_000.0, 0.0 if theta_o > math.pi / 2 else 500_000.0)
            t = classify_los_termination(los)
            assert t.continuation_zeta_rad == pytest.approx(math.pi - theta_o, abs=1e-15)

    @pytest.mark.level0
    def test_perigee_radius_is_r_t_sin_theta_o(self) -> None:
        """r_p = r_t·sin(ζ_c) = r_t·sin(θ_o) [m] — one definition, both branches."""
        h_tgt = 20_000.0
        for theta_o_deg in (10.0, 60.0, 89.0, 120.0, 179.0):
            theta_o = math.radians(theta_o_deg)
            los = _los(theta_o, h_tgt, 0.0 if theta_o > math.pi / 2 else 800_000.0)
            t = classify_los_termination(los)
            expected = (R_EARTH_M + h_tgt) * math.sin(theta_o)
            assert t.tangent_radius_m == pytest.approx(expected, rel=1e-14)
            assert t.tangent_depression_m == pytest.approx(h_tgt - (expected - R_EARTH_M), rel=1e-9)


class TestTerminusClassification:
    @pytest.mark.level0
    def test_down_looking_nadir_hits_earth(self) -> None:
        """The v1 baseline: sensor above, LOS continues down into the ground."""
        t = classify_los_termination(_los(0.0, 0.0, 800_000.0))
        assert t.terminus == "earth"
        assert not t.ascends

    @pytest.mark.level0
    def test_down_looking_off_nadir_surface_target_hits_earth(self) -> None:
        """Every surface-target down-looking scene terminates on the Earth."""
        for theta_o_deg in (0.0, 20.0, 45.0, 70.0, 88.0):
            t = classify_los_termination(_los(math.radians(theta_o_deg), 0.0, 800_000.0))
            assert t.terminus == "earth", theta_o_deg

    @pytest.mark.level0
    def test_up_looking_ascends_to_space(self) -> None:
        """Ground sensor, airborne target: the continuation leaves the atmosphere."""
        t = classify_los_termination(_los(math.pi, 10_000.0, 0.0))
        assert t.terminus == "space"
        assert t.ascends
        assert t.continuation_zeta_rad == pytest.approx(0.0, abs=1e-15)

    @pytest.mark.level0
    def test_level_path_ascends_to_space(self) -> None:
        """A level LOS leaves the target at ζ_c = π/2 − φ/2 — just above the
        horizontal, so it rises and never comes back."""
        phi = 150_000.0 / R_EARTH_M
        theta_o = math.pi / 2.0 + phi / 2.0
        t = classify_los_termination(_los(theta_o, 10_000.0, 10_000.0))
        assert t.terminus == "space"
        assert t.continuation_zeta_rad < math.pi / 2.0
        assert t.continuation_zeta_rad == pytest.approx(math.pi / 2.0 - phi / 2.0, abs=1e-15)

    @pytest.mark.level0
    def test_high_target_grazing_down_look_is_a_limb(self) -> None:
        """A high target viewed near the horizon: the continuation misses the
        Earth entirely — matrix B4, declined for v1.x."""
        h_tgt = 200_000.0
        # sin(theta_o) > R_E / (R_E + h_tgt) ⇒ perigee above the surface.
        theta_o = math.asin(R_EARTH_M / (R_EARTH_M + h_tgt)) + math.radians(0.5)
        t = classify_los_termination(_los(theta_o, h_tgt, 800_000.0))
        assert t.terminus == "limb"
        assert t.tangent_altitude_m > 0.0
        assert t.tangent_depression_m > 0.0

    @pytest.mark.level0
    def test_earth_limb_boundary_is_continuous(self) -> None:
        """Exactly tangent to the surface counts as an Earth intercept."""
        h_tgt = 200_000.0
        theta_o = math.asin(R_EARTH_M / (R_EARTH_M + h_tgt))
        t = classify_los_termination(_los(theta_o, h_tgt, 800_000.0))
        assert t.terminus == "earth"
        assert t.tangent_altitude_m == pytest.approx(0.0, abs=1e-6)


class TestValidation:
    @pytest.mark.level0
    def test_hand_built_payload_with_bad_theta_o_raises(self) -> None:
        """Defensive Rule-16 re-check for a caller that bypassed the dataclass."""

        class _Fake:
            h_tgt = 0.0
            theta_o = 4.0

        with pytest.raises(ParameterBoundsError, match=r"outside \[0, π\]"):
            classify_los_termination(_Fake())  # type: ignore[arg-type]

    @pytest.mark.level0
    def test_negative_h_tgt_raises(self) -> None:
        class _Fake:
            h_tgt = -1.0
            theta_o = 0.0

        with pytest.raises(ParameterBoundsError, match="finite altitude"):
            classify_los_termination(_Fake())  # type: ignore[arg-type]
