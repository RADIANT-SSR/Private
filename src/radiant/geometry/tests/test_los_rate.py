"""Level-0 tests for the relative LOS angular rate (Gap 111).

Truth anchors are analytic and independent of RADIANT:

* a **crossing** target (velocity exactly perpendicular to the LOS) at range
  ``R`` turns the LOS at exactly ``v / R``;
* a **receding / approaching** target (velocity exactly along the LOS) turns it
  at exactly zero, however fast it moves;
* a target flying **parallel to the platform at the same speed** has zero
  relative velocity, hence zero rate;
* a LEO platform's nadir rate equals the independent orbital identity
  ``omega_orbit * R_E / h`` from ``core.orbit``.

The zero-drift reduction against ``platform/smear.py``'s implied rate is proved
in ``tests/integration/test_los_rate_zero_drift.py`` — it lives there because a
cross-stage import inside a stage package would breach the import contract.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.constants import R_EARTH_M
from radiant.core.orbit import ground_track_speed_m_s, orbital_velocity_m_s
from radiant.core.parameters import ParameterSet
from radiant.geometry._schema import ALL_PARAMETERS
from radiant.geometry.errors import GeometrySpecificationError
from radiant.geometry.los_rate import (
    relative_los_angular_rate_rad_s,
    relative_velocity_m_s,
)
from radiant.geometry.stage import GeometryStage


def make_params(h_sensor: float, **inputs: object) -> ParameterSet:
    ps = ParameterSet(list(ALL_PARAMETERS))
    ps.set("geometry.sensor_altitude_m", h_sensor)
    for name, value in inputs.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


def run_stage(params: ParameterSet) -> dict[str, object]:
    state = ChainState(wavelength_um=np.linspace(3.0, 5.0, 8))
    return dict(GeometryStage().run(state, params).stage_outputs["geometry"])


# ---------------------------------------------------------------------------
# Truth anchor 1 — crossing target: omega = v / R exactly
# ---------------------------------------------------------------------------


class TestCrossingTarget:
    def test_platform_only_crossing_is_exact(self) -> None:
        """The platform track is cross-track by convention, so v_g is fully perpendicular."""
        omega = relative_los_angular_rate_rad_s(
            slant_range_m=1_000.0,
            theta_o_rad=0.7,
            sensor_ground_speed_m_s=100.0,
        )
        assert omega == 0.1  # exactly v / R, no rounding

    @pytest.mark.parametrize("theta_o", [0.0, 0.3, 1.0, math.pi / 2 + 0.3, math.pi])
    def test_platform_only_is_v_over_r_at_every_zenith(self, theta_o: float) -> None:
        """A cross-track velocity is perpendicular to the LOS for any theta_o."""
        omega = relative_los_angular_rate_rad_s(
            slant_range_m=2_500.0,
            theta_o_rad=theta_o,
            sensor_ground_speed_m_s=250.0,
        )
        assert omega == pytest.approx(0.1, rel=1e-15)

    def test_target_crossing_is_v_over_r(self) -> None:
        """Target moving at heading +90 deg (cross-track), level, static sensor."""
        omega = relative_los_angular_rate_rad_s(
            slant_range_m=5_000.0,
            theta_o_rad=0.9,
            target_speed_m_s=300.0,
            target_heading_rad=math.pi / 2.0,
        )
        assert omega == pytest.approx(300.0 / 5_000.0, rel=1e-15)

    def test_hand_computed_oblique_crossing(self) -> None:
        """theta_o = 60 deg, target level toward the sensor ground point.

        The velocity then makes 30 deg with the LOS, so
        |v x u| = 100 * sin(30 deg) = 50 m/s and omega = 50 / 1000 = 0.05 rad/s.
        """
        omega = relative_los_angular_rate_rad_s(
            slant_range_m=1_000.0,
            theta_o_rad=math.radians(60.0),
            target_speed_m_s=100.0,
            target_heading_rad=0.0,
        )
        assert omega == pytest.approx(0.05, rel=1e-12)


# ---------------------------------------------------------------------------
# Truth anchor 2 — radial motion: omega = 0 exactly
# ---------------------------------------------------------------------------


class TestRadialMotion:
    @pytest.mark.parametrize("theta_o", [0.2, 0.8, 1.2, math.pi / 2 + 0.4, 3.0])
    def test_receding_along_the_los_gives_zero(self, theta_o: float) -> None:
        """Heading 0 with climb = 90 deg - theta_o puts v exactly along the LOS."""
        omega = relative_los_angular_rate_rad_s(
            slant_range_m=1_000.0,
            theta_o_rad=theta_o,
            target_speed_m_s=800.0,
            target_heading_rad=0.0,
            target_climb_rad=math.pi / 2.0 - theta_o,
        )
        assert omega == pytest.approx(0.0, abs=1e-15)

    def test_approaching_along_the_los_gives_zero(self) -> None:
        """The reversed direction (heading pi, descending) is equally radial."""
        theta_o = 0.6
        omega = relative_los_angular_rate_rad_s(
            slant_range_m=1_000.0,
            theta_o_rad=theta_o,
            target_speed_m_s=800.0,
            target_heading_rad=math.pi,
            target_climb_rad=-(math.pi / 2.0 - theta_o),
        )
        assert omega == pytest.approx(0.0, abs=1e-15)

    def test_vertical_climb_under_a_nadir_sensor_gives_zero(self) -> None:
        """theta_o = 0: the LOS is vertical, so a vertical climb is purely radial."""
        omega = relative_los_angular_rate_rad_s(
            slant_range_m=10_000.0,
            theta_o_rad=0.0,
            target_speed_m_s=500.0,
            target_climb_rad=math.pi / 2.0,
        )
        assert omega == pytest.approx(0.0, abs=1e-15)

    def test_target_parallel_to_the_platform_track_cancels(self) -> None:
        """Same speed, same direction as the platform: zero relative velocity."""
        speed = 220.0
        v_par, v_perp, v_up = relative_velocity_m_s(
            sensor_ground_speed_m_s=speed,
            target_speed_m_s=speed,
            target_heading_rad=math.pi / 2.0,
        )
        assert v_perp == 0.0  # exactly: sin(pi/2) = 1.0
        assert v_up == 0.0
        assert v_par == pytest.approx(0.0, abs=1e-13)
        omega = relative_los_angular_rate_rad_s(
            slant_range_m=1_000.0,
            theta_o_rad=0.4,
            sensor_ground_speed_m_s=speed,
            target_speed_m_s=speed,
            target_heading_rad=math.pi / 2.0,
        )
        assert omega == pytest.approx(0.0, abs=1e-15)


# ---------------------------------------------------------------------------
# Truth anchor 3 — LEO sanity against the orbit machinery and the smear arm
# ---------------------------------------------------------------------------


class TestLeoSanity:
    H = 600_000.0

    def test_nadir_rate_matches_the_orbital_identity(self) -> None:
        """omega = v_g / h = (v / a) * R_E / h — the nadir-stabilised image-motion rate."""
        v_g = ground_track_speed_m_s(self.H)
        omega = relative_los_angular_rate_rad_s(
            slant_range_m=self.H,
            theta_o_rad=0.0,
            sensor_ground_speed_m_s=v_g,
        )
        a = R_EARTH_M + self.H
        omega_orbit = orbital_velocity_m_s(self.H) / a  # rad/s about the Earth centre
        assert omega == pytest.approx(omega_orbit * R_EARTH_M / self.H, rel=1e-12)
        # Order-of-magnitude sanity: a LEO nadir track slews at ~0.6-0.7 deg/s.
        assert 0.5 < math.degrees(omega) < 0.8


# ---------------------------------------------------------------------------
# Failure modes (Rule 15/17: actionable, never a silent inf/NaN)
# ---------------------------------------------------------------------------


class TestFailureModes:
    def test_zero_range_raises_rather_than_returning_inf(self) -> None:
        with pytest.raises(GeometrySpecificationError, match="coincident"):
            relative_los_angular_rate_rad_s(
                slant_range_m=0.0, theta_o_rad=0.5, target_speed_m_s=10.0
            )

    def test_negative_range_raises(self) -> None:
        with pytest.raises(GeometrySpecificationError, match="not\n?.*positive"):
            relative_los_angular_rate_rad_s(slant_range_m=-1.0, theta_o_rad=0.5)

    def test_theta_o_outside_closed_domain_raises(self) -> None:
        for theta_o in (-0.1, math.pi + 0.1):
            with pytest.raises(GeometrySpecificationError, match=r"outside \[0"):
                relative_los_angular_rate_rad_s(slant_range_m=1.0, theta_o_rad=theta_o)

    def test_negative_speed_raises(self) -> None:
        with pytest.raises(GeometrySpecificationError, match="negative"):
            relative_los_angular_rate_rad_s(
                slant_range_m=1.0, theta_o_rad=0.5, target_speed_m_s=-3.0
            )
        with pytest.raises(GeometrySpecificationError, match="negative"):
            relative_los_angular_rate_rad_s(
                slant_range_m=1.0, theta_o_rad=0.5, sensor_ground_speed_m_s=-3.0
            )

    def test_climb_outside_half_pi_raises(self) -> None:
        with pytest.raises(GeometrySpecificationError, match="climb"):
            relative_los_angular_rate_rad_s(
                slant_range_m=1.0,
                theta_o_rad=0.5,
                target_speed_m_s=1.0,
                target_climb_rad=2.0,
            )

    def test_non_finite_input_raises(self) -> None:
        for kwargs in (
            {"slant_range_m": math.nan, "theta_o_rad": 0.5},
            {"slant_range_m": 1.0, "theta_o_rad": math.inf},
            {"slant_range_m": 1.0, "theta_o_rad": 0.5, "target_speed_m_s": math.nan},
        ):
            with pytest.raises(GeometrySpecificationError, match="not finite"):
                relative_los_angular_rate_rad_s(**kwargs)  # type: ignore[arg-type]

    def test_no_motion_is_exactly_zero_not_nan(self) -> None:
        assert relative_los_angular_rate_rad_s(slant_range_m=1e6, theta_o_rad=0.5) == 0.0


# ---------------------------------------------------------------------------
# Stage-level resolution (K0 / K1 / K2, agreement, degenerate scenes)
# ---------------------------------------------------------------------------


class TestStageResolution:
    def test_default_publishes_platform_only_rate(self) -> None:
        out = run_stage(make_params(600_000.0, geometry__ground_speed_m_s=6_900.0))
        assert out["los_rate_mode"] == "platform-only (derived)"
        assert out["los_angular_rate_rad_s"] == pytest.approx(6_900.0 / 600_000.0, rel=1e-15)

    def test_no_kinematics_at_all_is_zero(self) -> None:
        """Every pre-Gap-111 config: no ground speed, no target motion, rate 0."""
        out = run_stage(make_params(600_000.0))
        assert out["los_angular_rate_rad_s"] == 0.0
        assert out["kinematics_mode"] == "direct"  # unchanged, pre-existing label

    def test_circular_orbit_feeds_the_rate(self) -> None:
        out = run_stage(make_params(600_000.0, geometry__circular_orbit=True))
        expected = ground_track_speed_m_s(600_000.0) / 600_000.0
        assert out["los_angular_rate_rad_s"] == pytest.approx(expected, rel=1e-15)

    def test_direct_door_wins_when_alone(self) -> None:
        out = run_stage(make_params(600_000.0, geometry__los_angular_rate_rad_s=0.02))
        assert out["los_rate_mode"] == "geometry.los_angular_rate_rad_s"
        assert out["los_angular_rate_rad_s"] == pytest.approx(0.02, rel=1e-15)

    def test_target_velocity_door(self) -> None:
        """Ground sensor, crossing aircraft 10 km up at 250 m/s: omega = v / R."""
        params = make_params(
            0.0,
            geometry__target_altitude_m=10_000.0,
            geometry__path_zenith_rad=0.0,
            geometry__target_speed_m_s=250.0,
            geometry__target_heading_rad=math.pi / 2.0,
        )
        out = run_stage(params)
        slant = float(out["slant_range_m"])  # type: ignore[arg-type]
        assert out["los_rate_mode"] == "target velocity (K2)"
        assert out["los_angular_rate_rad_s"] == pytest.approx(250.0 / slant, rel=1e-12)

    def test_both_doors_agreeing_is_accepted(self) -> None:
        params = make_params(
            0.0,
            geometry__target_altitude_m=10_000.0,
            geometry__path_zenith_rad=0.0,
            geometry__target_speed_m_s=250.0,
            geometry__target_heading_rad=math.pi / 2.0,
            geometry__los_angular_rate_rad_s=0.025,
        )
        out = run_stage(params)
        assert "consistent" in str(out["los_rate_mode"])

    def test_both_doors_disagreeing_raises(self) -> None:
        params = make_params(
            0.0,
            geometry__target_altitude_m=10_000.0,
            geometry__path_zenith_rad=0.0,
            geometry__target_speed_m_s=250.0,
            geometry__target_heading_rad=math.pi / 2.0,
            geometry__los_angular_rate_rad_s=0.5,
        )
        with pytest.raises(GeometrySpecificationError, match="LOS-rate"):
            run_stage(params)

    def test_heading_without_speed_warns_and_falls_back(self) -> None:
        params = make_params(
            0.0,
            geometry__target_altitude_m=10_000.0,
            geometry__path_zenith_rad=0.0,
            geometry__target_heading_rad=1.0,
        )
        with pytest.warns(UserWarning, match="target_speed_m_s is 0"):
            out = run_stage(params)
        assert out["los_angular_rate_rad_s"] == 0.0

    def test_coincident_endpoints_publish_none_not_a_raise(self) -> None:
        """Zero drift: an existing collocated scene keeps working (rate is None)."""
        out = run_stage(make_params(0.0, geometry__ground_speed_m_s=10.0))
        assert out["slant_range_m"] is None
        assert out["los_angular_rate_rad_s"] is None
        assert "coincident" in str(out["los_rate_mode"])

    def test_coincident_endpoints_with_a_target_velocity_raise(self) -> None:
        params = make_params(0.0, geometry__target_speed_m_s=10.0)
        with pytest.raises(GeometrySpecificationError, match="coincident"):
            run_stage(params)

    def test_direct_door_still_works_without_a_path(self) -> None:
        """K1 needs no range, so it survives the coincident-endpoint case."""
        out = run_stage(make_params(0.0, geometry__los_angular_rate_rad_s=0.3))
        assert out["los_angular_rate_rad_s"] == pytest.approx(0.3, rel=1e-15)

    def test_uplooking_scene_resolves(self) -> None:
        out = run_stage(
            make_params(
                0.0,
                geometry__target_altitude_m=10_000.0,
                geometry__path_zenith_rad=0.3,
                geometry__ground_speed_m_s=50.0,
            )
        )
        assert out["los_direction"] == "up"
        slant = float(out["slant_range_m"])  # type: ignore[arg-type]
        assert out["los_angular_rate_rad_s"] == pytest.approx(50.0 / slant, rel=1e-15)
