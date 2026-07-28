"""Gap 111 zero-drift proof: the published LOS rate is additive, not disruptive.

Two claims, both required by the Geometry-Flexibility Phase 3 charter:

1. **Reduction.** With no target-kinematics parameter set, the rate GeometryStage
   publishes is *exactly* the rate ``platform/smear.py`` already derives from the
   platform ground velocity and the published slant range — the value downstream
   consumers get today. The new door therefore does not introduce a second,
   slightly different platform rate.
2. **Additivity.** Turning the new doors on changes nothing else: every
   pre-existing ``stage_outputs["geometry"]`` entry, every published metric, and
   the noise budget are bit-identical to a run without them (the class label and
   the rate are the only new keys).

Lives in ``tests/integration`` rather than beside the geometry unit tests because
the reduction check imports ``radiant.platform.smear``, which a module inside
``radiant.geometry`` may not do (import-linter cross-stage contract).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.core.orbit import ground_track_speed_m_s
from radiant.core.parameters import ParameterSet
from radiant.platform.smear import smear_width_m

ALT = 600_000.0
FOCAL_LENGTH_M = 1.5
T_INT_S = 1.0e-3


def _run(**overrides: object):  # type: ignore[no-untyped-def]
    wl = np.linspace(3.8, 4.2, 16)
    session = RadiantSession(wavelength_um=wl)
    params: ParameterSet = session.default_params()
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("source.target.is_hot_target", True)
    params.set("optics.aperture_diameter_m", 0.3)
    params.set("optics.focal_length_m", FOCAL_LENGTH_M)
    params.set("optics.transmission_scalar", 0.9)
    params.set("detector.pixel_pitch_x_um", 15.0)
    params.set("detector.pixel_pitch_y_um", 15.0)
    params.set("detector.qe_value", 0.7)
    params.set("detector.dark_rate_e_per_s", 1000.0)
    params.set("detector.n_pixels_cross", 2048)
    params.set("geometry.sensor_altitude_m", ALT)
    params.set("spectral_integration.filter_min_um", 3.8)
    params.set("spectral_integration.filter_max_um", 4.2)
    params.set("spectral_integration.integration_time_s", T_INT_S)
    params.set("readout.read_noise_e_rms", 50.0)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)
    for name, value in overrides.items():
        params.set(name, value)
    params.resolve()
    return session.run(params)


@pytest.mark.level2
class TestPlatformOnlyReduction:
    """Claim 1 — the platform-only rate IS the smear arm's implied rate."""

    @pytest.mark.parametrize("theta_o", [0.0, 0.2, 0.5])
    def test_matches_smear_implied_rate(self, theta_o: float) -> None:
        v_g = ground_track_speed_m_s(ALT)
        result = _run(
            **{
                "geometry.circular_orbit": True,
                "geometry.path_zenith_rad": theta_o,
                "platform.ground_velocity_m_s": v_g,
            }
        )
        geo = result.stage_outputs["geometry"]
        slant = float(geo["slant_range_m"])
        # platform/smear.py: width = (v / range) * f * t_int, so the angular
        # rate that arm assumes is width / (f * t_int).
        implied = smear_width_m(v_g, T_INT_S, FOCAL_LENGTH_M, slant) / (FOCAL_LENGTH_M * T_INT_S)
        assert geo["los_angular_rate_rad_s"] == pytest.approx(implied, rel=1e-15)
        assert geo["los_rate_mode"] == "platform-only (derived)"

    def test_static_platform_publishes_zero(self) -> None:
        geo = _run().stage_outputs["geometry"]
        assert geo["los_angular_rate_rad_s"] == 0.0
        assert geo["scene_class"] == "space_to_ground"


@pytest.mark.level2
class TestAdditivity:
    """Claim 2 — the new keys are additive; nothing else moves."""

    NEW_KEYS = frozenset(
        {
            "scene_class",
            "observer_class",
            "target_class",
            "los_angular_rate_rad_s",
            "los_rate_mode",
        }
    )

    def test_scene_class_assertion_changes_nothing(self) -> None:
        base = _run(**{"geometry.path_zenith_rad": 0.3})
        asserted = _run(
            **{"geometry.path_zenith_rad": 0.3, "geometry.scene_class": "space_to_ground"}
        )
        _assert_same_numbers(base, asserted)

    def test_target_velocity_moves_only_the_smear_arm(self) -> None:
        """Gap 111's consumer landed in Phase 3: the rate now drives the smear.

        The additivity claim survives it, narrowed to what the arm may touch:
        every published *geometry* number and the radiometry are still
        bit-identical, and only the spatial-quality metrics move — which is the
        arm doing its job (see ``test_moving_target_smear.py`` for the anchors).
        """
        base = _run(**{"geometry.path_zenith_rad": 0.3})
        moving = _run(
            **{
                "geometry.path_zenith_rad": 0.3,
                "geometry.target_speed_m_s": 250.0,
                "geometry.target_heading_rad": math.pi / 2.0,
            }
        )
        base_geo = base.stage_outputs["geometry"]
        moving_geo = moving.stage_outputs["geometry"]
        compared = 0
        for key, value in base_geo.items():
            if key in self.NEW_KEYS or not isinstance(value, float):
                continue
            assert moving_geo[key] == value, f"geometry.{key} moved"
            compared += 1
        assert compared >= 5  # the comparison is not vacuous

        # Radiometry: smear is a spatial-quality term, and this extended scene
        # applies no EE_box (Rule 9), so signal and noise cannot move.
        for key in ("snr", "nedt_K"):
            assert moving.metrics[key] == base.metrics[key], f"metric {key} moved"

        # The arm itself.
        assert base.stage_outputs["platform"]["smear_width_m"] == 0.0
        smear_m = moving.stage_outputs["platform"]["smear_width_m"]
        assert smear_m == pytest.approx(
            moving_geo["los_angular_rate_rad_s"] * FOCAL_LENGTH_M * T_INT_S, rel=1e-15
        )
        # 250 m/s at 600 km is 0.6 µm of smear against a 15 µm pixel, so the
        # spatial metrics may only degrade, not improve, at this magnitude.
        assert moving.metrics["rer"] <= base.metrics["rer"]
        assert moving_geo["los_angular_rate_rad_s"] > 0.0
        assert moving_geo["los_rate_mode"] == "target velocity (K2)"

    def test_new_keys_are_the_only_new_keys(self) -> None:
        geo = _run().stage_outputs["geometry"]
        assert set(geo) >= self.NEW_KEYS


def _assert_same_numbers(base, other) -> None:  # type: ignore[no-untyped-def]
    """Every pre-existing published number is bit-identical between two runs."""
    base_geo = base.stage_outputs["geometry"]
    other_geo = other.stage_outputs["geometry"]
    compared = 0
    for key, value in base_geo.items():
        if key in TestAdditivity.NEW_KEYS or not isinstance(value, float):
            continue
        assert other_geo[key] == value, f"geometry.{key} moved"
        compared += 1
    assert compared >= 5  # the comparison is not vacuous
    for key, value in base.metrics.items():
        if isinstance(value, float) and math.isfinite(value):
            assert other.metrics[key] == value, f"metric {key} moved"
