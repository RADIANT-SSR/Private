"""Gap 111 end-to-end: the moving-target arm of the smear (Phase 3).

GeometryStage composes the platform and target velocities into ONE relative
line-of-sight angular rate; PlatformStage turns that one rate into ONE smear
extent, which feeds both Rule-4 spatial paths. This module pins the seam
between the two stages through the real session:

1. **Truth anchors** — the crossing-target hand calculation
   (200 m/s at 20 km for 10 ms ⇒ 1.0e-4 rad of angular smear), the radial
   (receding) target that adds nothing, and the platform-only configuration
   whose smear is bit-identical to the pre-Gap-111 velocity/range door.
2. **The mode-string contract** — the ``los_rate_mode`` values GeometryStage
   actually publishes are the ones PlatformStage's gate is written against.
   Unit tests on either side spell the strings out; only a full chain proves
   they are the same strings.
3. **Rule 4** — the dual-path consistency check stays green on an up-looking
   moving-target scene, i.e. the generalized rate reached the PSF kernel and
   the MTF product together.

Zero drift for existing scenes is proved twice over: exactly, over a grid, in
``src/radiant/platform/tests/test_stage_relative_motion_smear.py``, and by the
golden suite.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.core.parameters import ParameterSet
from radiant.platform.smear import smear_width_m
from radiant.platform.stage import PlatformStage

# --- Air-to-ground MWIR scene: sensor at 20 km, nadir, target on the ground ---
H_SENSOR_M = 20_000.0
SLANT_M = H_SENSOR_M  # θ_o = 0 ⇒ the slant range IS the altitude difference
FOCAL_LENGTH_M = 1.5
T_INT_S = 0.010
V_TARGET_M_S = 200.0
OMEGA_ANCHOR_RAD_S = V_TARGET_M_S / SLANT_M  # 1.0e-2 rad/s
MWIR_WL = np.linspace(3.8, 4.2, 16)

# --- Up-looking space-to-space scene (vacuum, Phase 1 quick win) ---
H_LEO_M = 500_000.0
H_GEO_M = 35_786_000.0
VIS_WL = np.linspace(0.45, 0.80, 71)


def _mwir_params(session: RadiantSession, **overrides: object) -> ParameterSet:
    p = session.default_params()
    p.set("source.target.temperature", 320.0)
    p.set("source.target.emissivity", 0.95)
    p.set("source.target.is_hot_target", True)
    p.set("optics.aperture_diameter_m", 0.3)
    p.set("optics.focal_length_m", FOCAL_LENGTH_M)
    p.set("optics.transmission_scalar", 0.9)
    p.set("detector.pixel_pitch_x_um", 15.0)
    p.set("detector.pixel_pitch_y_um", 15.0)
    p.set("detector.qe_value", 0.7)
    p.set("detector.dark_rate_e_per_s", 1000.0)
    p.set("geometry.sensor_altitude_m", H_SENSOR_M)
    p.set("spectral_integration.filter_min_um", 3.8)
    p.set("spectral_integration.filter_max_um", 4.2)
    p.set("spectral_integration.integration_time_s", T_INT_S)
    p.set("readout.read_noise_e_rms", 50.0)
    p.set("readout.gain_e_per_dn", 2.0)
    p.set("readout.adc_bits", 14)
    for name, value in overrides.items():
        p.set(name, value)
    p.resolve()
    return p


def _run_mwir(**overrides: object):  # type: ignore[no-untyped-def]
    session = RadiantSession(wavelength_um=MWIR_WL)
    params = _mwir_params(session, **overrides)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return session.run(params)


def _run_uplooking(**overrides: object):  # type: ignore[no-untyped-def]
    """LEO → GEO up-looking point source, vacuum path (``atmosphere.model='exo'``)."""
    session = RadiantSession(wavelength_um=VIS_WL)
    p = session.default_params()
    p.set("source.target.reflectance", 0.25)
    p.set("source.scene_type", "point_source")
    p.set("atmosphere.model", "exo")
    p.set("geometry.sensor_altitude_m", H_LEO_M)
    p.set("geometry.target_altitude_m", H_GEO_M)
    p.set("geometry.solar_illumination", "day")
    p.set("geometry.solar_zenith_rad", 0.6)
    p.set("geometry.target.projected_area_m2", 20.0)
    p.set("optics.aperture_diameter_m", 0.30)
    p.set("optics.focal_length_m", 3.0)
    p.set("optics.transmission_scalar", 0.60)
    p.set("detector.pixel_pitch_x_um", 10.0)
    p.set("detector.pixel_pitch_y_um", 10.0)
    p.set("detector.qe_value", 0.75)
    p.set("detector.dark_rate_e_per_s", 50.0)
    p.set("spectral_integration.filter_min_um", 0.45)
    p.set("spectral_integration.filter_max_um", 0.80)
    p.set("spectral_integration.integration_time_s", 0.10)
    p.set("readout.read_noise_e_rms", 5.0)
    p.set("readout.gain_e_per_dn", 2.0)
    p.set("readout.adc_bits", 14)
    # Ground-projected metrics are undefined for a space target (Gap 96).
    p.set("performance.metrics.sampling", False)
    p.set("performance.metrics.interpretability", False)
    for name, value in overrides.items():
        p.set(name, value)
    p.resolve()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return session.run(p)


# ---------------------------------------------------------------------------
# 1. Truth anchors
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestCrossingTargetAnchor:
    """Anchor 1 — 200 m/s crossing at 20 km for 10 ms ⇒ 1.0e-4 rad."""

    def test_geometry_publishes_the_hand_calculated_rate(self) -> None:
        result = _run_mwir(
            **{
                "geometry.target_speed_m_s": V_TARGET_M_S,
                "geometry.target_heading_rad": math.pi / 2.0,  # crossing
            }
        )
        geo = result.stage_outputs["geometry"]
        assert geo["slant_range_m"] == SLANT_M
        assert geo["los_angular_rate_rad_s"] == pytest.approx(OMEGA_ANCHOR_RAD_S, rel=1e-15)
        assert geo["los_rate_mode"] == "target velocity (K2)"

    def test_angular_smear_is_1e_4_rad(self) -> None:
        result = _run_mwir(
            **{
                "geometry.target_speed_m_s": V_TARGET_M_S,
                "geometry.target_heading_rad": math.pi / 2.0,
            }
        )
        smear_m = result.stage_outputs["platform"]["smear_width_m"]
        angular_smear_rad = smear_m / FOCAL_LENGTH_M
        assert angular_smear_rad == pytest.approx(1.0e-4, rel=1e-12)
        assert smear_m == pytest.approx(1.0e-4 * FOCAL_LENGTH_M, rel=1e-12)
        # Rule 4: the same rate reached the PSF kernel and the MTF product.
        consistency = result.stage_outputs["performance"]["dual_path_consistency"]
        assert consistency.passed_x and consistency.passed_y, consistency

    def test_smear_degrades_the_spatial_metrics(self) -> None:
        """The arm is wired to the metrics, not just to a stage output."""
        still = _run_mwir()
        moving = _run_mwir(
            **{
                "geometry.target_speed_m_s": V_TARGET_M_S,
                "geometry.target_heading_rad": math.pi / 2.0,
            }
        )
        assert still.stage_outputs["platform"]["smear_width_m"] == 0.0
        assert moving.stage_outputs["platform"]["smear_width_m"] > 0.0
        assert moving.metrics["rer"] < still.metrics["rer"]
        assert moving.metrics["mtf_system_at_nyquist_y"] < still.metrics["mtf_system_at_nyquist_y"]
        assert moving.metrics["mtf_system_at_nyquist_x"] == still.metrics["mtf_system_at_nyquist_x"]
        # Radiometry is untouched by smear: this is an extended scene, so
        # EE_box is 1.0 by Rule 9 and the smear is purely a spatial-quality term.
        assert moving.metrics["snr"] == still.metrics["snr"]
        assert moving.metrics["nedt_K"] == still.metrics["nedt_K"]


@pytest.mark.level2
class TestRecedingTargetAnchor:
    """Anchor 2 — motion along the LOS adds no smear."""

    def test_explicit_zero_rate_gives_exactly_zero_smear(self) -> None:
        """K1 door, ω = 0: exactly 0.0 — no epsilon, no clamp."""
        result = _run_mwir(**{"geometry.los_angular_rate_rad_s": 0.0})
        assert result.stage_outputs["geometry"]["los_rate_mode"] == (
            "geometry.los_angular_rate_rad_s"
        )
        assert result.stage_outputs["platform"]["smear_width_m"] == 0.0

    def test_vertically_climbing_target_under_nadir_view_adds_nothing(self) -> None:
        """A target climbing straight up a vertical LOS is purely radial.

        Algebraically the rate is exactly zero. In doubles the residual is the
        6.1e-17 of ``cos(π/2)``, so the assertion is "16 orders below the
        crossing case", not an epsilon chosen to fit.
        """
        result = _run_mwir(
            **{
                "geometry.target_speed_m_s": V_TARGET_M_S,
                "geometry.target_climb_rad": math.pi / 2.0,
            }
        )
        smear_m = result.stage_outputs["platform"]["smear_width_m"]
        crossing = 1.0e-4 * FOCAL_LENGTH_M
        assert smear_m < 1e-15 * crossing

    def test_receding_is_not_confused_with_crossing(self) -> None:
        """Same speed, two headings: the projection is doing real work."""
        crossing = _run_mwir(
            **{
                "geometry.target_speed_m_s": V_TARGET_M_S,
                "geometry.target_heading_rad": math.pi / 2.0,
            }
        ).stage_outputs["platform"]["smear_width_m"]
        radial = _run_mwir(
            **{
                "geometry.target_speed_m_s": V_TARGET_M_S,
                "geometry.target_climb_rad": -math.pi / 2.0,  # diving away
            }
        ).stage_outputs["platform"]["smear_width_m"]
        assert crossing > 0.0
        assert radial < 1e-15 * crossing


@pytest.mark.level2
class TestPlatformOnlyBitIdentical:
    """Anchor 3 — a configuration with no kinematics input does not move."""

    @pytest.mark.parametrize("theta_o", [0.0, 0.2, 0.5])
    def test_smear_equals_the_legacy_velocity_range_door(self, theta_o: float) -> None:
        v_g = 200.0  # m/s — an airborne platform at 20 km
        result = _run_mwir(
            **{
                "platform.ground_velocity_m_s": v_g,
                "geometry.path_zenith_rad": theta_o,
            }
        )
        slant = float(result.stage_outputs["geometry"]["slant_range_m"])
        expected = smear_width_m(v_g, T_INT_S, FOCAL_LENGTH_M, slant)
        assert result.stage_outputs["platform"]["smear_width_m"] == expected

    @pytest.mark.parametrize("theta_o", [0.0, 0.2, 0.5])
    def test_published_rate_reduces_to_the_platform_only_rate(self, theta_o: float) -> None:
        """The two arms compute the same platform rate — the gate is provenance.

        (The rate itself is checked here; that the *smear* takes the legacy
        branch is the test above.)
        """
        v_g = 200.0  # m/s
        result = _run_mwir(
            **{
                "platform.ground_velocity_m_s": v_g,
                "geometry.path_zenith_rad": theta_o,
            }
        )
        geo = result.stage_outputs["geometry"]
        slant = float(geo["slant_range_m"])
        legacy_rate = smear_width_m(v_g, T_INT_S, FOCAL_LENGTH_M, slant) / (
            FOCAL_LENGTH_M * T_INT_S
        )
        assert geo["los_angular_rate_rad_s"] == pytest.approx(legacy_rate, rel=1e-15)

    def test_a_stationary_scene_has_no_smear_at_all(self) -> None:
        result = _run_mwir()
        assert result.stage_outputs["platform"]["smear_width_m"] == 0.0
        assert result.stage_outputs["geometry"]["los_angular_rate_rad_s"] == 0.0


# ---------------------------------------------------------------------------
# 2. The cross-stage mode-string contract
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestModeStringContract:
    """PlatformStage gates on ``los_rate_mode``; these are the real strings."""

    def test_no_kinematics_is_platform_only(self) -> None:
        mode = _run_mwir().stage_outputs["geometry"]["los_rate_mode"]
        assert not PlatformStage._relative_los_rate_active(mode)

    def test_direct_rate_door_is_active(self) -> None:
        mode = _run_mwir(**{"geometry.los_angular_rate_rad_s": 1e-3}).stage_outputs["geometry"][
            "los_rate_mode"
        ]
        assert PlatformStage._relative_los_rate_active(mode)

    def test_target_velocity_door_is_active(self) -> None:
        mode = _run_mwir(**{"geometry.target_speed_m_s": V_TARGET_M_S}).stage_outputs["geometry"][
            "los_rate_mode"
        ]
        assert PlatformStage._relative_los_rate_active(mode)

    def test_both_doors_agreeing_is_active(self) -> None:
        result = _run_mwir(
            **{
                "geometry.target_speed_m_s": V_TARGET_M_S,
                "geometry.target_heading_rad": math.pi / 2.0,
                "geometry.los_angular_rate_rad_s": OMEGA_ANCHOR_RAD_S,
            }
        )
        mode = result.stage_outputs["geometry"]["los_rate_mode"]
        assert PlatformStage._relative_los_rate_active(mode)
        assert result.stage_outputs["platform"]["smear_width_m"] == pytest.approx(
            OMEGA_ANCHOR_RAD_S * FOCAL_LENGTH_M * T_INT_S, rel=1e-12
        )


# ---------------------------------------------------------------------------
# 3. Rule 4 on a new scene class
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestDualPathOnUpLookingMovingTarget:
    """The generalized rate reaches BOTH spatial paths (Rule 4)."""

    TARGET_SPEED_M_S = 3000.0

    def test_consistency_check_passes(self) -> None:
        result = _run_uplooking(
            **{
                "geometry.target_speed_m_s": self.TARGET_SPEED_M_S,
                "geometry.target_heading_rad": math.pi / 2.0,
            }
        )
        geo = result.stage_outputs["geometry"]
        assert geo["los_direction"] == "up"
        assert geo["scene_class"] == "space_to_space"
        assert result.stage_outputs["platform"]["smear_width_m"] > 0.0

        consistency = result.stage_outputs["performance"]["dual_path_consistency"]
        assert consistency.passed_x, consistency
        assert consistency.passed_y, consistency

    def test_smear_is_the_relative_rate_times_the_focal_scale(self) -> None:
        result = _run_uplooking(
            **{
                "geometry.target_speed_m_s": self.TARGET_SPEED_M_S,
                "geometry.target_heading_rad": math.pi / 2.0,
            }
        )
        geo = result.stage_outputs["geometry"]
        rate = float(geo["los_angular_rate_rad_s"])
        # ω = v/R for a crossing target, even up-looking (θ_o obtuse).
        assert rate == pytest.approx(self.TARGET_SPEED_M_S / float(geo["slant_range_m"]), rel=1e-12)
        assert result.stage_outputs["platform"]["smear_width_m"] == pytest.approx(
            rate * 3.0 * 0.10, rel=1e-12
        )

    def test_stationary_up_looking_scene_is_unaffected(self) -> None:
        result = _run_uplooking()
        assert result.stage_outputs["platform"]["smear_width_m"] == 0.0
        consistency = result.stage_outputs["performance"]["dual_path_consistency"]
        assert consistency.passed_x and consistency.passed_y
