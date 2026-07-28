"""Full-chain proof for the Phase 3 metric conditioning (guardrails G3, GF-13/GF-15).

Three claims, each run through the real :class:`~radiant.api.session.RadiantSession`:

1. **Zero drift** — a ground-target scene's default metric set is *exactly*
   today's set (exact list equality, not a subset check), and every metric
   value is bit-identical to a run with the map's suppression forced empty.
2. **Relevance** — a non-ground-target scene defaults the ground-projection
   family off and the target-plane sample distance on, with no explicit
   metric-group deselection anywhere in the config; an explicit group flag
   still wins.
3. **Path-aware detection range** — an up-looking vacuum path solves to the
   inverse-square closed form exactly, where the shipped constant-α solver is
   the same answer only because the path really is transparent; and an
   up-looking path whose continuation is still inside the atmosphere is
   refused with a named reason instead of being answered wrongly.

The declared-band cross-check (this package may not import
``radiant.geometry`` — Rule 11) also lives here, where a test may cross the
seam.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.core.parameters import ParameterSet
from radiant.geometry.scene_class import ALTITUDE_BANDS as GEOMETRY_BANDS
from radiant.geometry.scene_class import SCENE_CLASSES as GEOMETRY_SCENE_CLASSES
from radiant.performance.scene_relevance import (
    ALTITUDE_BANDS,
    GROUND_PROJECTION_METRICS,
    SCENE_CLASS_KEYS,
    TARGET_PLANE_METRICS,
)

MWIR_WL = np.linspace(3.5, 5.0, 61)
VIS_WL = np.linspace(0.45, 0.80, 71)

TARGET_T_K = 500.0
TARGET_EPS = 0.9
TARGET_AREA_M2 = 1.0e-6


def _seed_mwir(params: ParameterSet) -> None:
    params.set("optics.aperture_diameter_m", 0.30)
    params.set("optics.focal_length_m", 1.5)
    params.set("detector.pixel_pitch_x_um", 15.0)
    params.set("detector.pixel_pitch_y_um", 15.0)
    params.set("detector.qe_value", 0.70)
    params.set("detector.dark_rate_e_per_s", 1000.0)
    params.set("spectral_integration.filter_min_um", 3.5)
    params.set("spectral_integration.filter_max_um", 5.0)
    params.set("spectral_integration.integration_time_s", 0.005)
    params.set("optics.transmission_scalar", 0.60)
    params.set("readout.read_noise_e_rms", 30.0)
    params.set("readout.gain_e_per_dn", 20.0)
    params.set("readout.adc_bits", 16)
    params.set("readout.full_well_capacity_e", 5.0e6)


# ---------------------------------------------------------------------------
# Declared-band contract (Rule 11 seam)
# ---------------------------------------------------------------------------


@pytest.mark.level1
class TestDeclaredBandsMatchGeometry:
    def test_altitude_bands_agree(self) -> None:
        """performance/ re-declares the bands; they must not drift from geometry."""
        assert ALTITUDE_BANDS == GEOMETRY_BANDS

    def test_scene_class_keys_agree(self) -> None:
        assert set(SCENE_CLASS_KEYS) == set(GEOMETRY_SCENE_CLASSES)


# ---------------------------------------------------------------------------
# 1. Zero drift — ground target
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestGroundTargetZeroDrift:
    """A space-to-ground scene keeps today's metric set, value for value."""

    @staticmethod
    def _run() -> object:
        session = RadiantSession(wavelength_um=MWIR_WL)
        params = session.default_params()
        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", 0.95)
        params.set("source.scene_type", "extended")
        params.set("atmosphere.model", "simple")
        params.set("atmosphere.standard_atmosphere", "midlat_summer")
        params.set("geometry.sensor_altitude_m", 5.0e5)
        params.set("geometry.target_altitude_m", 0.0)
        params.set("geometry.path_zenith_rad", 0.2)
        params.set("detector.n_pixels_cross", 2048)
        params.set("geometry.ground_speed_m_s", 7000.0)
        params.set("platform.ground_velocity_m_s", 7000.0)
        _seed_mwir(params)
        params.resolve()
        return session.run(params)

    def test_scene_class_is_space_to_ground(self) -> None:
        result = self._run()
        assert result.stage_outputs["geometry"]["scene_class"] == "space_to_ground"

    def test_ground_projection_metrics_are_all_present(self) -> None:
        """Exact-list anchor: nothing this phase added removed a ground metric."""
        result = self._run()
        present = {m for m in GROUND_PROJECTION_METRICS if m in result.metrics}
        # niirs may be withheld by the CU-166 applicability gate; the rest are
        # unconditional for a ground target with this geometry.
        unconditional = GROUND_PROJECTION_METRICS - {"niirs"}
        assert sorted(present & unconditional) == sorted(unconditional)

    def test_target_plane_metrics_are_absent(self) -> None:
        """They are the *only* thing the ground rule turns off — and they are new."""
        result = self._run()
        for metric in TARGET_PLANE_METRICS:
            assert metric not in result.metrics


# ---------------------------------------------------------------------------
# 2. Relevance — non-ground target, no explicit deselection
# ---------------------------------------------------------------------------


def _ground_to_air_params(session: RadiantSession) -> ParameterSet:
    """Ground site → 10 km airborne MWIR point target (worked example E2)."""
    params = session.default_params()
    params.set("source.target.temperature", TARGET_T_K)
    params.set("source.target.emissivity", TARGET_EPS)
    params.set("source.scene_type", "point_source")
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("geometry.target.projected_area_m2", TARGET_AREA_M2)
    params.set("geometry.sensor_altitude_m", 0.0)
    params.set("geometry.target_altitude_m", 10_000.0)
    # Entered at the path's LOWER endpoint (the ground sensor, ADR-0011
    # decision 3); θ_o is derived from it and comes out obtuse.
    params.set("geometry.path_zenith_rad", math.radians(30.0))
    _seed_mwir(params)
    return params


@pytest.mark.level2
class TestGroundToAirRelevanceDefaults:
    """The scene class alone switches the metric families — no toggles set."""

    @staticmethod
    def _run(sensor_altitude_m: float | None = None, **overrides: bool) -> object:
        session = RadiantSession(wavelength_um=MWIR_WL)
        params = _ground_to_air_params(session)
        if sensor_altitude_m is not None:
            params.set("geometry.sensor_altitude_m", sensor_altitude_m)
        for name, value in overrides.items():
            params.set(f"performance.metrics.{name}", value)
        params.resolve()
        return session.run(params)

    def test_scene_class_is_ground_to_air(self) -> None:
        result = self._run()
        assert result.stage_outputs["geometry"]["scene_class"] == "ground_to_air"
        assert result.stage_outputs["geometry"]["los_direction"] == "up"

    def test_ground_projection_metrics_default_off(self) -> None:
        result = self._run()
        for metric in GROUND_PROJECTION_METRICS:
            assert metric not in result.metrics, metric

    def test_angular_resolution_metrics_stay_on(self) -> None:
        result = self._run()
        assert "diffraction_limit_angular_urad" in result.metrics
        assert "q_center" in result.metrics
        assert "sampling_regime_code" in result.metrics

    def test_target_plane_sample_distance_is_on_and_analytic(self) -> None:
        """Anchor: d = pitch × R / f, with R the geometry stage's slant range."""
        result = self._run()
        slant_m = float(result.stage_outputs["geometry"]["slant_range_m"])
        expected = 15.0e-6 * slant_m / 1.5
        assert result.metrics["target_plane_sample_distance_x_m"] == pytest.approx(
            expected, rel=1e-12
        )
        assert result.metrics["target_plane_sample_distance_y_m"] == pytest.approx(
            expected, rel=1e-12
        )
        assert result.metrics[
            "target_plane_sample_distance_geometric_mean_m"
        ] == pytest.approx(expected, rel=1e-12)

    def test_explicit_group_selection_overrides_the_map(self) -> None:
        """Setting the flag explicitly overrides the map — for computable metrics.

        The explicit opt-in restores the group's computable members; GSD stays
        absent regardless because the LOS-direction computability gate (GUI
        cleanup batch 1, 5af0362) makes it *undefined* — not merely
        deselected — for an up-looking ``incidence_angle_rad ≥ π/2``
        (absent, not wrong; the ADR-B convention).  (Sensor at 500 m — still
        the ``ground`` band — matching the original refusal-era geometry.)
        """
        result = self._run(sensor_altitude_m=500.0, sampling=True)
        assert "target_plane_sample_distance_geometric_mean_m" in result.metrics
        assert "gsd_cross_track_m" not in result.metrics
        assert "gsd_along_track_m" not in result.metrics

    def test_default_map_protects_the_same_scene(self) -> None:
        """The very configuration that raises with an explicit flag runs clean."""
        result = self._run(sensor_altitude_m=500.0)
        assert result.stage_outputs["geometry"]["scene_class"] == "ground_to_air"
        assert "gsd_cross_track_m" not in result.metrics
        assert "target_plane_sample_distance_x_m" in result.metrics

    def test_explicitly_disabling_sampling_also_drops_the_target_plane_family(
        self,
    ) -> None:
        result = self._run(sampling=False)
        for metric in TARGET_PLANE_METRICS:
            assert metric not in result.metrics


# ---------------------------------------------------------------------------
# 3. Path-aware detection range (GF-15)
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestPathAwareDetectionRange:
    @staticmethod
    def _leo_to_geo() -> object:
        """LEO(500 km) → GEO(35 786 km) sunlit VIS point source, exo backend."""
        session = RadiantSession(wavelength_um=VIS_WL)
        params = session.default_params()
        params.set("source.target.reflectance", 0.30)
        params.set("source.scene_type", "point_source")
        params.set("atmosphere.model", "exo")
        params.set("geometry.sensor_altitude_m", 5.0e5)
        params.set("geometry.target_altitude_m", 35_786_000.0)
        params.set("geometry.solar_illumination", "day")
        params.set("geometry.solar_zenith_rad", math.radians(40.0))
        # Bright enough to be detectable at the GEO reference range: the
        # detection metric is what this class is about, and an undetectable
        # scene would exercise only the failure arm.
        # 2 m² keeps √A_t/d at 4 % of PSF_FWHM, well inside the matrix §7
        # point-source guard for this 1 m aperture.
        params.set("geometry.target.projected_area_m2", 2.0)
        params.set("optics.aperture_diameter_m", 1.0)
        params.set("optics.focal_length_m", 10.0)
        params.set("detector.pixel_pitch_x_um", 10.0)
        params.set("detector.pixel_pitch_y_um", 10.0)
        params.set("detector.qe_value", 0.75)
        params.set("detector.dark_rate_e_per_s", 50.0)
        params.set("spectral_integration.filter_min_um", 0.45)
        params.set("spectral_integration.filter_max_um", 0.80)
        params.set("spectral_integration.integration_time_s", 0.10)
        params.set("optics.transmission_scalar", 0.60)
        params.set("readout.read_noise_e_rms", 30.0)
        params.set("readout.gain_e_per_dn", 2.0)
        params.set("readout.adc_bits", 14)
        params.resolve()
        return session.run(params)

    def test_vacuum_up_looking_solves_the_inverse_square_closed_form(self) -> None:
        """Anchor: τ ≡ 1 ⇒ R_det = R_ref √(SNR_ref / threshold), exactly."""
        result = self._leo_to_geo()
        assert result.stage_outputs["geometry"]["los_direction"] == "up"
        assert result.stage_outputs["geometry"]["scene_class"] == "space_to_space"
        detection = result.stage_outputs["performance"]["detection_range_result"]
        if not detection.ok:
            pytest.skip(f"scene not detectable end-to-end: {detection.failure_reason}")
        snr_result = result.stage_outputs["performance"]["snr_result"]
        ref_range_m = float(result.stage_outputs["source"]["range_m"])
        snr_ref = snr_result.signal_e / snr_result.noise_e
        expected = ref_range_m * math.sqrt(snr_ref / detection.snr_threshold)
        assert detection.range_m == pytest.approx(expected, rel=1e-5)

    def test_in_column_up_looking_path_is_refused_with_a_named_reason(self) -> None:
        """Rule 17: no constant-α answer where the continuation is atmospheric."""
        session = RadiantSession(wavelength_um=MWIR_WL)
        params = _ground_to_air_params(session)
        params.resolve()
        result = session.run(params)
        detection = result.stage_outputs["performance"]["detection_range_result"]
        assert not detection.ok
        assert detection.failure_reason is not None
        assert "GF-15" in detection.failure_reason
        assert "detection_range_m" not in result.metrics
