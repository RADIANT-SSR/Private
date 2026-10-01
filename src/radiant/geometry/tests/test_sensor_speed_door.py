"""Level-0 tests for the sensor-velocity door on the LOS rate (CU-391).

Before this door, the sensor endpoint's velocity in ``ω = |v_rel,⊥| / R`` was
always ``geometry.ground_speed_m_s`` — the **sub-satellite ground-track** speed
``v·R_E/a`` when V6 ``circular_orbit`` derives it.  That is the right quantity
for an Earth-fixed target seen from a nadir-stabilised platform (the
off-boresight angle then changes at ``v_g/h``), and the wrong one for a target
that is not Earth-fixed, where the sensor's **inertial** speed belongs.
``geometry.sensor_speed_m_s`` is that second expression of the same platform
velocity, provenance-detected and rule-2 agreement-checked against the
circular-orbit derivation exactly as K1/K2 are against each other.

Truth anchors are analytic and independent of the implementation:

* **A — LEO→GEO radial pair.**  Two co-planar, co-rotating circular orbits on
  one radial line: each inertial velocity is purely tangential, hence exactly
  perpendicular to the radial LOS, so ``ω = |v_LEO − v_GEO| / (h_GEO − h_LEO)``.
  Both speeds come from ``v = sqrt(μ/a)`` written out here from
  ``core.constants`` — not from ``core.orbit`` — so the anchor does not inherit
  any RADIANT helper's convention.
* **B — round-number hand calculation.**  Cross-track sensor at 1000 m/s,
  cross-track target at 400 m/s, 100 km apart: ``ω = 600/1e5 = 6.0e-3 rad/s``.
* **C — co-moving limit.**  Equal cross-track speeds give identically zero
  relative velocity and therefore ω = 0 at every θ_o, for any speed.

The zero-drift claim (an unset door reproduces the ground-track behaviour
bit-for-bit) is pinned here at the stage level and in
``tests/integration/test_los_rate_zero_drift.py``.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.constants import R_EARTH_M, mu_earth_m3_s2
from radiant.core.orbit import ground_track_speed_m_s, orbital_velocity_m_s
from radiant.core.parameters import ParameterSet
from radiant.geometry._schema import ALL_PARAMETERS
from radiant.geometry.errors import GeometrySpecificationError
from radiant.geometry.los_rate import relative_los_angular_rate_rad_s
from radiant.geometry.modes import resolve_kinematics, resolve_los_rate, resolve_viewing
from radiant.geometry.stage import GeometryStage

#: Scenario 10.4's two altitudes [m] — a 500 km circular LEO looking straight
#: up at the geostationary belt.
H_LEO_M = 500_000.0
H_GEO_M = 35_786_000.0


def _inertial_speed_m_s(altitude_m: float) -> float:
    """v = sqrt(μ / (R_E + h)) [m/s], written out from the raw constants."""
    return math.sqrt(mu_earth_m3_s2 / (R_EARTH_M + altitude_m))


#: Truth anchor A, hand-derived: |v_LEO − v_GEO| / (h_GEO − h_LEO) [rad/s].
OMEGA_LEO_GEO_RAD_S = abs(_inertial_speed_m_s(H_LEO_M) - _inertial_speed_m_s(H_GEO_M)) / (
    H_GEO_M - H_LEO_M
)


def make_params(h_sensor: float = H_LEO_M, **inputs: object) -> ParameterSet:
    ps = ParameterSet(list(ALL_PARAMETERS))
    ps.set("geometry.sensor_altitude_m", h_sensor)
    for name, value in inputs.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


def run_stage(params: ParameterSet) -> dict[str, object]:
    state = ChainState(wavelength_um=np.linspace(3.0, 5.0, 8))
    return dict(GeometryStage().run(state, params).stage_outputs["geometry"])


def leo_to_geo_params(**inputs: object) -> ParameterSet:
    """Scenario 10.4's geometry: GEO target at the LEO sensor's zenith."""
    return make_params(
        geometry__target_altitude_m=H_GEO_M,
        geometry__path_zenith_rad=0.0,  # at the LOWER endpoint = the sensor
        **inputs,
    )


# ---------------------------------------------------------------------------
# Truth anchor A — the LEO→GEO radial relative rate
# ---------------------------------------------------------------------------


class TestLeoToGeoAnchor:
    def test_hand_derived_anchor_is_128_7_urad_s(self) -> None:
        """The hand derivation itself, stated to five figures (no RADIANT code)."""
        assert pytest.approx(1.28709e-4, rel=1e-5) == OMEGA_LEO_GEO_RAD_S

    def test_kernel_reproduces_the_anchor(self) -> None:
        """ω = |v_rel,⊥| / R with both endpoints' inertial velocities cross-track.

        θ_o = π is the radial LOS (target straight above the sensor); heading
        π/2 puts the target's tangential velocity along the same ê_⊥ the
        sensor's is modelled on — the co-planar co-rotating case.
        """
        omega = relative_los_angular_rate_rad_s(
            slant_range_m=H_GEO_M - H_LEO_M,
            theta_o_rad=math.pi,
            sensor_speed_m_s=_inertial_speed_m_s(H_LEO_M),
            target_speed_m_s=_inertial_speed_m_s(H_GEO_M),
            target_heading_rad=math.pi / 2.0,
            target_climb_rad=0.0,
        )
        assert omega == pytest.approx(OMEGA_LEO_GEO_RAD_S, rel=1e-12)

    def test_stage_publishes_the_anchor_through_the_doors(self) -> None:
        """CU-391 acceptance: circular_orbit + the sensor door + K2 ⇒ 128.7 µrad/s.

        Pre-fix, this same scene published 200.1 µrad/s because the sensor
        endpoint carried the ground-track speed (7062.3 m/s) instead of the
        inertial 7616.6 m/s, and that is +55.5 %.
        """
        out = run_stage(
            leo_to_geo_params(
                geometry__circular_orbit=True,
                geometry__sensor_speed_m_s=orbital_velocity_m_s(H_LEO_M),
                geometry__target_speed_m_s=orbital_velocity_m_s(H_GEO_M),
                geometry__target_heading_rad=math.pi / 2.0,
                geometry__target_climb_rad=0.0,
            )
        )
        assert out["los_angular_rate_rad_s"] == pytest.approx(OMEGA_LEO_GEO_RAD_S, rel=1e-9)
        assert out["los_rate_mode"] == "relative velocity (K2)"
        # The ground-track speed is untouched — it still drives access rate.
        assert out["ground_speed_m_s"] == pytest.approx(ground_track_speed_m_s(H_LEO_M), rel=1e-12)
        assert out["sensor_speed_m_s"] == pytest.approx(orbital_velocity_m_s(H_LEO_M), rel=1e-12)

    def test_ground_track_default_reproduces_the_defect_value(self) -> None:
        """Without the door the published rate is still v_g / R — the old number.

        Pinned deliberately: the door is opt-in, so every pre-CU-391 config
        keeps its exact value, and the 200.1 µrad/s this scene produces is the
        documented limitation the door exists to escape.
        """
        with pytest.warns(UserWarning, match="sub-satellite ground-track speed"):
            out = run_stage(leo_to_geo_params(geometry__circular_orbit=True))
        v_g = ground_track_speed_m_s(H_LEO_M)
        assert out["los_angular_rate_rad_s"] == pytest.approx(v_g / (H_GEO_M - H_LEO_M), rel=1e-12)
        assert out["los_angular_rate_rad_s"] == pytest.approx(2.0014e-4, rel=1e-3)


# ---------------------------------------------------------------------------
# Truth anchor B — round-number hand calculation
# ---------------------------------------------------------------------------


class TestHandCalculation:
    def test_opposed_cross_track_speeds(self) -> None:
        """1000 m/s sensor, 400 m/s target, both cross-track, 100 km apart."""
        omega = relative_los_angular_rate_rad_s(
            slant_range_m=1.0e5,
            theta_o_rad=math.pi / 2.0,
            sensor_speed_m_s=1000.0,
            target_speed_m_s=400.0,
            target_heading_rad=math.pi / 2.0,
        )
        assert omega == pytest.approx(6.0e-3, rel=1e-15)

    def test_sensor_only_is_v_over_r(self) -> None:
        """The door alone, no target motion: ω = v_sensor / R exactly."""
        omega = relative_los_angular_rate_rad_s(
            slant_range_m=2.0e5,
            theta_o_rad=0.4,
            sensor_speed_m_s=7500.0,
        )
        assert omega == pytest.approx(7500.0 / 2.0e5, rel=1e-15)


# ---------------------------------------------------------------------------
# Truth anchor C — the co-moving limit
# ---------------------------------------------------------------------------


class TestCoMovingLimit:
    @pytest.mark.parametrize("theta_o", [0.0, 0.5, math.pi / 2.0, 2.4, math.pi])
    @pytest.mark.parametrize("speed", [1.0, 250.0, 7616.56])
    def test_equal_cross_track_speeds_give_zero(self, theta_o: float, speed: float) -> None:
        omega = relative_los_angular_rate_rad_s(
            slant_range_m=1.0e6,
            theta_o_rad=theta_o,
            sensor_speed_m_s=speed,
            target_speed_m_s=speed,
            target_heading_rad=math.pi / 2.0,
        )
        assert omega == pytest.approx(0.0, abs=1e-18)

    def test_both_endpoints_static_give_exactly_zero(self) -> None:
        assert (
            relative_los_angular_rate_rad_s(
                slant_range_m=1.0e6, theta_o_rad=1.0, sensor_speed_m_s=0.0
            )
            == 0.0
        )


# ---------------------------------------------------------------------------
# Door resolution — provenance, rule-2 agreement, mode labels
# ---------------------------------------------------------------------------


class TestDoorResolution:
    def test_unset_door_falls_back_to_the_ground_track_speed(self) -> None:
        ps = make_params(geometry__ground_speed_m_s=6900.0)
        kin = resolve_kinematics(ps)
        assert kin.sensor_speed_m_s == 6900.0
        assert kin.sensor_speed_mode == "geometry.ground_speed_m_s (ground track)"

    def test_unset_door_under_circular_orbit_keeps_the_ground_track_speed(self) -> None:
        """Zero drift: V6 does NOT silently switch the LOS-rate sensor velocity."""
        ps = make_params(geometry__circular_orbit=True)
        kin = resolve_kinematics(ps)
        assert kin.sensor_speed_m_s == pytest.approx(ground_track_speed_m_s(H_LEO_M), rel=1e-15)
        assert kin.sensor_speed_m_s == kin.ground_speed_m_s

    def test_door_overrides_the_ground_track_speed(self) -> None:
        ps = make_params(geometry__ground_speed_m_s=6900.0, geometry__sensor_speed_m_s=7616.56)
        kin = resolve_kinematics(ps)
        assert kin.ground_speed_m_s == 6900.0  # untouched
        assert kin.sensor_speed_m_s == 7616.56
        assert kin.sensor_speed_mode == "geometry.sensor_speed_m_s"

    def test_door_agreeing_with_the_orbit_derivation_is_accepted(self) -> None:
        """Rule 2: the circular orbit's inertial speed is a redundant entry."""
        ps = make_params(
            geometry__circular_orbit=True,
            geometry__sensor_speed_m_s=orbital_velocity_m_s(H_LEO_M),
        )
        kin = resolve_kinematics(ps)
        assert kin.sensor_speed_m_s == pytest.approx(orbital_velocity_m_s(H_LEO_M), rel=1e-15)
        assert "consistent" in kin.sensor_speed_mode

    def test_door_disagreeing_with_the_orbit_derivation_raises(self) -> None:
        ps = make_params(geometry__circular_orbit=True, geometry__sensor_speed_m_s=3000.0)
        with pytest.raises(GeometrySpecificationError) as excinfo:
            resolve_kinematics(ps)
        message = str(excinfo.value)
        assert "geometry.sensor_speed_m_s" in message
        assert "inertial" in message
        assert excinfo.value.context["derived_inertial_m_s"] == pytest.approx(
            orbital_velocity_m_s(H_LEO_M), rel=1e-12
        )

    def test_mode_label_names_the_sensor_door_alone(self) -> None:
        ps = make_params(geometry__sensor_speed_m_s=7616.56, geometry__path_zenith_rad=0.3)
        viewing = resolve_viewing(ps)
        kin = resolve_kinematics(ps)
        assert resolve_los_rate(ps, viewing, kin).mode == "relative velocity (K2)"

    def test_target_only_label_is_unchanged(self) -> None:
        """Zero drift on the published string every pre-CU-391 K2 scene carries."""
        ps = make_params(geometry__target_speed_m_s=250.0, geometry__path_zenith_rad=0.3)
        viewing = resolve_viewing(ps)
        kin = resolve_kinematics(ps)
        assert resolve_los_rate(ps, viewing, kin).mode == "target velocity (K2)"

    def test_k1_still_wins_its_own_agreement_check(self) -> None:
        """K1 + the sensor door disagreeing by more than 1 % raises (rule 2)."""
        ps = leo_to_geo_params(
            geometry__sensor_speed_m_s=7616.56,
            geometry__los_angular_rate_rad_s=1.0e-3,
        )
        viewing = resolve_viewing(ps)
        kin = resolve_kinematics(ps)
        with pytest.raises(GeometrySpecificationError, match="LOS-rate"):
            resolve_los_rate(ps, viewing, kin)


# ---------------------------------------------------------------------------
# The advisory: ground-track speed against a target that is not Earth-fixed
# ---------------------------------------------------------------------------


class TestGroundTrackAdvisory:
    def test_space_target_without_the_door_warns(self) -> None:
        with pytest.warns(UserWarning, match=r"geometry\.sensor_speed_m_s"):
            run_stage(leo_to_geo_params(geometry__ground_speed_m_s=7000.0))

    def test_warning_names_the_inertial_speed_to_enter(self) -> None:
        with pytest.warns(UserWarning) as record:
            run_stage(leo_to_geo_params(geometry__circular_orbit=True))
        assert any("7616" in str(w.message) for w in record)

    def test_ground_target_never_warns(self) -> None:
        """The ground-track speed IS the right quantity for an Earth-fixed target."""
        import warnings as _warnings

        with _warnings.catch_warnings():
            _warnings.simplefilter("error")
            run_stage(make_params(geometry__circular_orbit=True, geometry__path_zenith_rad=0.3))

    def test_space_target_with_the_door_never_warns(self) -> None:
        import warnings as _warnings

        with _warnings.catch_warnings():
            _warnings.simplefilter("error")
            run_stage(
                leo_to_geo_params(
                    geometry__circular_orbit=True,
                    geometry__sensor_speed_m_s=orbital_velocity_m_s(H_LEO_M),
                )
            )

    def test_static_platform_space_target_never_warns(self) -> None:
        """Nothing to mis-attribute when the platform is not moving."""
        import warnings as _warnings

        with _warnings.catch_warnings():
            _warnings.simplefilter("error")
            run_stage(leo_to_geo_params())

    def test_direct_rate_door_never_warns(self) -> None:
        """K1 bypasses the velocity model entirely, so the frame question is moot."""
        import warnings as _warnings

        with _warnings.catch_warnings():
            _warnings.simplefilter("error")
            run_stage(
                leo_to_geo_params(
                    geometry__circular_orbit=True,
                    geometry__los_angular_rate_rad_s=OMEGA_LEO_GEO_RAD_S,
                )
            )


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


class TestFailureModes:
    def test_negative_door_value_is_rejected_by_the_schema(self) -> None:
        from radiant.core.parameters import ParameterBoundsError

        ps = ParameterSet(list(ALL_PARAMETERS))
        ps.set("geometry.sensor_altitude_m", H_LEO_M)
        ps.set("geometry.sensor_speed_m_s", -1.0)
        with pytest.raises(ParameterBoundsError, match=r"out of bounds"):
            ps.resolve()

    def test_negative_speed_is_rejected_by_the_kernel(self) -> None:
        with pytest.raises(GeometrySpecificationError, match="negative"):
            relative_los_angular_rate_rad_s(
                slant_range_m=1.0, theta_o_rad=0.5, sensor_speed_m_s=-3.0
            )

    def test_non_finite_speed_is_rejected(self) -> None:
        with pytest.raises(GeometrySpecificationError, match="not finite"):
            relative_los_angular_rate_rad_s(
                slant_range_m=1.0, theta_o_rad=0.5, sensor_speed_m_s=float("nan")
            )

    def test_zero_door_value_is_inert(self) -> None:
        """0.0 is the schema default; setting it explicitly still opens the door.

        Provenance, not value, decides (ADR-0006 rule 1), so an explicit 0 m/s
        is a declaration that the sensor is stationary for rate purposes —
        which is exactly what it computes.
        """
        ps = make_params(
            geometry__ground_speed_m_s=6900.0,
            geometry__sensor_speed_m_s=0.0,
            geometry__path_zenith_rad=0.3,
        )
        viewing = resolve_viewing(ps)
        kin = resolve_kinematics(ps)
        assert kin.sensor_speed_m_s == 0.0
        assert resolve_los_rate(ps, viewing, kin).los_angular_rate_rad_s == 0.0

    def test_coincident_endpoints_with_the_door_raise_actionably(self) -> None:
        ps = make_params(
            h_sensor=0.0,
            geometry__target_altitude_m=0.0,
            geometry__sensor_speed_m_s=10.0,
        )
        viewing = resolve_viewing(ps)
        kin = resolve_kinematics(ps)
        with pytest.raises(GeometrySpecificationError, match="no line of sight"):
            resolve_los_rate(ps, viewing, kin)
