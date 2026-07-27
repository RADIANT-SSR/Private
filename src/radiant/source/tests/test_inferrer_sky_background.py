"""Rule-B background selection by LOS termination (matrix §3.2.5, Gap 108).

Before Geometry-Flexibility Phase 2 every expressible scene was down-looking,
so the LOS continuation always ran into the Earth and the ground default was
the only reachable answer.  Phase 1 made up-looking and level scenes legal;
their continuation ascends and exits the atmosphere, which selects
``SkyBackground`` (matrix ``B2``).

The zero-drift half of this is as important as the new behaviour: the
down-looking selector must be untouched, so a down-looking scene never sees
this code path at all.
"""

from __future__ import annotations

import math
import warnings

import pytest

from radiant.core.constants import R_EARTH_M
from radiant.core.descriptors import SkyBackground
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError
from radiant.source._inferrer import _select_los_termination_background

H_ATM_TOP_M = 1.0e5


def _los(**kw: float | None) -> LineOfSightGeometry:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return LineOfSightGeometry(h_atm_top=H_ATM_TOP_M, **kw)  # type: ignore[arg-type]


class TestZeroDriftForDownLooking:
    @pytest.mark.level0
    @pytest.mark.parametrize("theta_o_deg", [0.0, 25.0, 60.0, 88.0])
    def test_down_looking_selector_declines_to_choose(self, theta_o_deg: float) -> None:
        """``None`` means "not my branch" — the existing ground/at-aperture/
        cold-space defaults keep deciding, unchanged."""
        los = _los(h_tgt=0.0, h_sensor=800_000.0, theta_o=math.radians(theta_o_deg))
        assert _select_los_termination_background(los) is None

    @pytest.mark.level0
    def test_missing_los_declines(self) -> None:
        assert _select_los_termination_background(None) is None

    @pytest.mark.level0
    def test_down_looking_airborne_target_declines(self) -> None:
        """Space→air (matrix E8) keeps its GroundBackground default."""
        los = _los(h_tgt=20_000.0, h_sensor=800_000.0, theta_o=0.5)
        assert _select_los_termination_background(los) is None


class TestSkyDefault:
    @pytest.mark.level0
    def test_ground_to_air_selects_sky(self) -> None:
        """E2: the continuation past a 10 km aircraft leaves the atmosphere."""
        los = _los(h_tgt=10_000.0, h_sensor=0.0, theta_o=math.radians(150.0))
        assert isinstance(_select_los_termination_background(los), SkyBackground)

    @pytest.mark.level0
    def test_vertical_up_look_selects_sky(self) -> None:
        los = _los(h_tgt=10_000.0, h_sensor=0.0, theta_o=math.pi)
        assert isinstance(_select_los_termination_background(los), SkyBackground)

    @pytest.mark.level0
    def test_level_path_selects_sky(self) -> None:
        """E5/E1: a level continuation rises (ζ_c = π/2 − φ/2) and exits."""
        for arc_m in (8_000.0, 150_000.0):
            phi = arc_m / R_EARTH_M
            los = _los(h_tgt=10_000.0, h_sensor=10_000.0, theta_o=math.pi / 2.0 + phi / 2.0)
            assert isinstance(_select_los_termination_background(los), SkyBackground)

    @pytest.mark.level0
    def test_ground_to_space_selects_sky(self) -> None:
        """E3: the SST case — the continuation past the satellite is vacuum."""
        los = _los(h_tgt=8.0e5, h_sensor=0.0, theta_o=math.pi)
        assert isinstance(_select_los_termination_background(los), SkyBackground)

    @pytest.mark.level0
    def test_sky_background_carries_no_user_parameters(self) -> None:
        """The radiance is computed from the scene, not supplied (Gap 108)."""
        import dataclasses

        assert dataclasses.fields(SkyBackground()) == ()
        assert SkyBackground() == SkyBackground()


class TestLimbIsDeclined:
    @pytest.mark.level0
    def test_limb_continuation_raises_naming_b4(self) -> None:
        """ADR-0011 decision 5: a limb termination is guarded, not approximated.

        Unreachable through an up/level LOS (an ascending continuation cannot
        graze), so it is exercised on the classifier directly — the branch
        exists so that a future topology which *can* reach it fails loudly.
        """
        h_tgt = 200_000.0
        theta_o = math.asin(R_EARTH_M / (R_EARTH_M + h_tgt)) + math.radians(0.5)

        class _Level:
            """A LOS whose direction reads 'level' but whose θ_o grazes."""

            h_tgt = 200_000.0
            h_sensor = 200_000.0
            h_atm_top = H_ATM_TOP_M
            los_direction = "level"

        fake = _Level()
        fake.theta_o = theta_o  # type: ignore[attr-defined]
        with pytest.raises(ParameterBoundsError) as exc:
            _select_los_termination_background(fake)  # type: ignore[arg-type]
        message = str(exc.value)
        assert "limb" in message
        assert "B4" in message
        assert "tangent" in message
