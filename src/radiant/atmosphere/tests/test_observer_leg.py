"""Level-0 tests for the up/level observer-leg decomposition.

The bookkeeping this module owns is easy to get subtly wrong and impossible to
notice downstream — a flipped radiance direction or a missing azimuth reversal
changes the answer without changing its shape.  These tests pin all three
facts it produces: the segment, the direction, and the azimuth frame.
"""

from __future__ import annotations

import math
import warnings

import pytest

from radiant.atmosphere.observer_leg import observer_leg_from_los
from radiant.atmosphere.segments import ColumnSegmentSpec, LevelArmSpec
from radiant.core.constants import R_EARTH_M
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError
from radiant.core.viewing_triangle import slant_range_from_theta_o_m

H_ATM_TOP_M = 1.0e5


def _los(**kw: float | None) -> LineOfSightGeometry:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return LineOfSightGeometry(h_atm_top=H_ATM_TOP_M, **kw)  # type: ignore[arg-type]


class TestUpLookingColumn:
    @pytest.mark.level0
    def test_vertical_up_look_is_a_zero_zenith_column(self) -> None:
        """θ_o = π: the sensor looks straight up, ζ_low = 0 exactly [rad]."""
        leg = observer_leg_from_los(_los(h_tgt=10_000.0, h_sensor=0.0, theta_o=math.pi))
        assert isinstance(leg.spec, ColumnSegmentSpec)
        assert leg.spec.h_low_m == 0.0
        assert leg.spec.h_high_m == 10_000.0
        assert leg.zeta_low_rad == pytest.approx(0.0, abs=1e-15)
        assert leg.slant_range_m == pytest.approx(10_000.0, rel=1e-12)

    @pytest.mark.level0
    def test_sensor_is_the_lower_endpoint_and_reads_toward_lower(self) -> None:
        """ADR-0011 decision 3: the segment is keyed to the lower endpoint, so
        the light reaching an up-looking sensor emerges at the lower end."""
        leg = observer_leg_from_los(_los(h_tgt=10_000.0, h_sensor=2_000.0, theta_o=2.4))
        assert leg.toward_sensor == "toward_lower"
        assert isinstance(leg.spec, ColumnSegmentSpec)
        assert leg.spec.h_low_m == 2_000.0

    @pytest.mark.level0
    def test_azimuth_frame_reverses_for_the_up_looking_column(self) -> None:
        """The segment's lower→upper direction is sensor→target, the reverse of
        φ_o, so cos(Δφ_seg) = −cos(Δφ) exactly."""
        for delta_phi in (0.0, 0.7, -1.3, math.pi):
            leg = observer_leg_from_los(
                _los(h_tgt=10_000.0, h_sensor=0.0, theta_o=2.6, theta_s=0.4, delta_phi=delta_phi)
            )
            assert math.cos(leg.delta_phi_seg_rad) == pytest.approx(-math.cos(delta_phi), abs=1e-15)

    @pytest.mark.level0
    def test_zeta_low_is_the_supplement_of_the_interior_angle(self) -> None:
        """ζ_low = π − η, with η the obtuse interior angle at the sensor.

        Cross-checked against the law of sines directly: for the *level-ish*
        limit the sensor-side zenith must stay below π/2 (the column ascends).
        """
        for theta_o_deg in (100.0, 135.0, 170.0, 179.5):
            leg = observer_leg_from_los(
                _los(h_tgt=12_000.0, h_sensor=1_000.0, theta_o=math.radians(theta_o_deg))
            )
            assert 0.0 <= leg.zeta_low_rad < math.pi / 2.0
            # Law of sines closure: r_low sin(ζ_low) = r_high sin(π − θ_o).
            r_low = R_EARTH_M + 1_000.0
            r_high = R_EARTH_M + 12_000.0
            assert r_low * math.sin(leg.zeta_low_rad) == pytest.approx(
                r_high * math.sin(math.radians(theta_o_deg)), rel=1e-9
            )


class TestLevelArm:
    @pytest.mark.level0
    def test_level_path_becomes_a_constant_altitude_arm(self) -> None:
        phi = 150_000.0 / R_EARTH_M
        theta_o = math.pi / 2.0 + phi / 2.0
        leg = observer_leg_from_los(_los(h_tgt=10_000.0, h_sensor=10_000.0, theta_o=theta_o))
        assert isinstance(leg.spec, LevelArmSpec)
        assert leg.spec.altitude_m == 10_000.0
        assert leg.zeta_low_rad == pytest.approx(math.pi / 2.0, abs=1e-15)

    @pytest.mark.level0
    def test_arm_length_is_the_true_chord(self) -> None:
        """Not the ground arc and not Δh/cos θ — the spherical chord [m]."""
        phi = 150_000.0 / R_EARTH_M
        theta_o = math.pi / 2.0 + phi / 2.0
        leg = observer_leg_from_los(_los(h_tgt=10_000.0, h_sensor=10_000.0, theta_o=theta_o))
        expected = slant_range_from_theta_o_m(theta_o, 10_000.0, 10_000.0)
        assert isinstance(leg.spec, LevelArmSpec)
        assert leg.spec.length_m == pytest.approx(expected, rel=1e-12)
        # 2 r sin(φ/2) — the chord, slightly shorter than the arc.
        chord = 2.0 * (R_EARTH_M + 10_000.0) * math.sin(phi / 2.0)
        assert leg.spec.length_m == pytest.approx(chord, rel=1e-9)
        assert leg.spec.length_m < (R_EARTH_M + 10_000.0) * phi

    @pytest.mark.level0
    def test_level_arm_keeps_the_azimuth_frame_and_reads_toward_upper(self) -> None:
        phi = 100_000.0 / R_EARTH_M
        theta_o = math.pi / 2.0 + phi / 2.0
        leg = observer_leg_from_los(
            _los(
                h_tgt=8_000.0,
                h_sensor=8_000.0,
                theta_o=theta_o,
                theta_s=0.5,
                delta_phi=0.9,
            )
        )
        assert leg.toward_sensor == "toward_upper"
        assert leg.delta_phi_seg_rad == pytest.approx(0.9, abs=1e-15)


class TestFailureModes:
    @pytest.mark.level0
    def test_down_looking_raises(self) -> None:
        """Zero drift: the down-looking topology must not be rerouted here."""
        with pytest.raises(ParameterBoundsError, match="down-looking"):
            observer_leg_from_los(_los(h_tgt=0.0, h_sensor=800_000.0, theta_o=0.3))

    @pytest.mark.level0
    def test_missing_sensor_endpoint_raises_with_the_g2_reason(self) -> None:
        with pytest.raises(ParameterBoundsError) as exc:
            observer_leg_from_los(_los(h_tgt=10_000.0, theta_o=2.5))
        message = str(exc.value)
        assert "h_sensor is None" in message
        assert "G2" in message

    @pytest.mark.level0
    def test_delta_phi_none_defaults_to_zero(self) -> None:
        leg = observer_leg_from_los(_los(h_tgt=10_000.0, h_sensor=0.0, theta_o=math.pi))
        assert math.cos(leg.delta_phi_seg_rad) == pytest.approx(-1.0, abs=1e-15)
