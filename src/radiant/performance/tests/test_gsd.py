"""Tests for GSD (ground sample distance) computation.

Level 0: analytic formula checks on ``compute_gsd`` (pure function).
Level 0b: spherical geometry helpers (slant range, incidence angle).
Level 0c: off-nadir GSD with spherical Earth correction.
Level 1: edge cases on ``_compute_gsd_metrics`` (ChainState wiring, graceful skips).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere._schema import (
    GROUND_SPEED_M_S,
    PATH_ZENITH_RAD,
    SENSOR_ALTITUDE_M,
)
from radiant.core.chain import ChainState
from radiant.core.geometry import (
    EARTH_RADIUS_M,
    incidence_angle_rad,
    slant_range_spherical_m,
)
from radiant.core.parameters import ParameterSet
from radiant.detector._schema import (
    N_PIXELS_CROSS,
    PIXEL_PITCH_X,
    PIXEL_PITCH_Y,
)
from radiant.optics._schema import (
    APERTURE_DIAMETER_M,
    FOCAL_LENGTH_M,
)
from radiant.performance.gsd import GSDResult, compute_gsd
from radiant.performance.stage import _compute_gsd_metrics


def _make_params(
    altitude_m: float | None = 500_000.0,
    focal_length_m: float = 1.2,
    pitch_x_um: float = 18.0,
    pitch_y_um: float | None = None,
    path_zenith_rad: float | None = None,
    n_pixels_cross: int | None = None,
    ground_speed_m_s: float | None = None,
) -> ParameterSet:
    """Build a minimal ParameterSet with geometry + optics + detector params.

    Note: pixel_pitch values are in µm (input units). ParameterSet converts
    to canonical meters internally via the schema's input_unit='um'.
    altitude_m=None omits geometry from schema entirely (lab scenario).
    """
    if pitch_y_um is None:
        pitch_y_um = pitch_x_um
    schema: list = [FOCAL_LENGTH_M, APERTURE_DIAMETER_M,
                    PIXEL_PITCH_X, PIXEL_PITCH_Y]
    if altitude_m is not None:
        schema.append(SENSOR_ALTITUDE_M)
    if path_zenith_rad is not None:
        schema.append(PATH_ZENITH_RAD)
    if n_pixels_cross is not None:
        schema.append(N_PIXELS_CROSS)
    if ground_speed_m_s is not None:
        schema.append(GROUND_SPEED_M_S)
    ps = ParameterSet(schema)
    if altitude_m is not None:
        ps.set("geometry.sensor_altitude_m", altitude_m)
    if path_zenith_rad is not None:
        ps.set("geometry.path_zenith_rad", path_zenith_rad)
    if n_pixels_cross is not None:
        ps.set("detector.n_pixels_cross", n_pixels_cross)
    if ground_speed_m_s is not None:
        ps.set("geometry.ground_speed_m_s", ground_speed_m_s)
    ps.set("optics.focal_length_m", focal_length_m)
    ps.set("optics.aperture_diameter_m", 0.3)
    ps.set("detector.pixel_pitch_x_um", pitch_x_um)
    ps.set("detector.pixel_pitch_y_um", pitch_y_um)
    ps.resolve()
    return ps


def _make_state() -> ChainState:
    """Build a minimal ChainState (GSD doesn't read frames)."""
    wl = np.linspace(3.5, 5.0, 10)
    return ChainState(wavelength_um=wl)


# ---------------------------------------------------------------------------
# Level 0 — pure function formula correctness (nadir, existing)
# ---------------------------------------------------------------------------


class TestGSDFormula:
    """GSD = pixel_pitch_m × altitude_m / focal_length_m."""

    @pytest.mark.level0
    def test_leo_500km_18um_pitch(self) -> None:
        """Standard LEO scenario: 18 µm pitch, f=1.2 m, h=500 km."""
        result = compute_gsd(
            pitch_x_m=18e-6, pitch_y_m=18e-6,
            altitude_m=500_000.0, focal_length_m=1.2,
        )
        assert result.cross_track_m == pytest.approx(7.5, rel=1e-10)
        assert result.along_track_m == pytest.approx(7.5, rel=1e-10)

    @pytest.mark.level0
    def test_geo_36000km_24um_pitch(self) -> None:
        """GEO scenario: 24 µm pitch, f=3.6 m, h=35786 km."""
        h = 35_786_000.0
        result = compute_gsd(
            pitch_x_m=24e-6, pitch_y_m=24e-6,
            altitude_m=h, focal_length_m=3.6,
        )
        expected = 24e-6 * h / 3.6  # ≈ 238.57 m
        assert result.cross_track_m == pytest.approx(expected, rel=1e-10)

    @pytest.mark.level0
    def test_rectangular_pixels(self) -> None:
        """Non-square pixels give different cross-track and along-track GSD."""
        result = compute_gsd(
            pitch_x_m=18e-6, pitch_y_m=24e-6,
            altitude_m=500_000.0, focal_length_m=1.2,
        )
        assert result.cross_track_m == pytest.approx(7.5, rel=1e-10)
        assert result.along_track_m == pytest.approx(10.0, rel=1e-10)

    @pytest.mark.level0
    def test_airborne_8km(self) -> None:
        """Airborne scenario: 15 µm pitch, f=0.5 m, h=8 km."""
        result = compute_gsd(
            pitch_x_m=15e-6, pitch_y_m=15e-6,
            altitude_m=8_000.0, focal_length_m=0.5,
        )
        assert result.cross_track_m == pytest.approx(0.24, rel=1e-10)

    @pytest.mark.level0
    def test_result_is_frozen(self) -> None:
        """GSDResult is immutable."""
        result = compute_gsd(18e-6, 18e-6, 500_000.0, 1.2)
        assert isinstance(result, GSDResult)
        with pytest.raises(AttributeError):
            result.cross_track_m = 999.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Level 0b — spherical Earth geometry helpers
# ---------------------------------------------------------------------------


class TestSlantRangeSpherical:
    """Ray-sphere intersection: slant range from sensor to Earth surface.

    Formula: ST = (R_E+h)·cos(θ) − √[R_E² − (R_E+h)²·sin²(θ)]
    where θ is the off-nadir look angle and h is altitude above the surface.
    """

    R_E = EARTH_RADIUS_M

    @pytest.mark.level0
    def test_nadir_returns_altitude(self) -> None:
        """At zenith=0, slant range equals altitude exactly."""
        assert slant_range_spherical_m(600_000.0, 0.0) == pytest.approx(
            600_000.0, rel=1e-12
        )

    @pytest.mark.level0
    def test_nadir_airborne(self) -> None:
        """At zenith=0, airborne: slant = altitude."""
        assert slant_range_spherical_m(8_000.0, 0.0) == pytest.approx(
            8_000.0, rel=1e-12
        )

    @pytest.mark.level0
    def test_small_angle_matches_flat_earth(self) -> None:
        """At 5 deg from 600 km, spherical ≈ flat-Earth to < 0.1%."""
        h = 600_000.0
        zen = math.radians(5.0)
        spherical = slant_range_spherical_m(h, zen)
        flat = h / math.cos(zen)
        assert abs(spherical - flat) / flat < 0.001

    @pytest.mark.level0
    def test_45deg_600km(self) -> None:
        """At 45 deg from 600 km: slant = 892.9 km (ray-sphere intersection).

        Hand calculation:
          disc = R_E² − (R_E+h)²·sin²(45°)
          ST = (R_E+h)·cos(45°) − √disc
        """
        slant = slant_range_spherical_m(600_000.0, math.radians(45.0))
        assert slant == pytest.approx(892_900.0, rel=0.001)

    @pytest.mark.level0
    def test_30deg_600km(self) -> None:
        """At 30 deg from 600 km: slant ≈ 704.1 km."""
        slant = slant_range_spherical_m(600_000.0, math.radians(30.0))
        assert slant == pytest.approx(704_100.0, rel=0.001)

    @pytest.mark.level0
    def test_spherical_greater_than_flat_earth(self) -> None:
        """Spherical slant range > flat-Earth at off-nadir angles.

        Earth curves away from the flat tangent plane, so the line of sight
        travels farther before hitting the curved surface.
        """
        h = 600_000.0
        zen = math.radians(30.0)
        spherical = slant_range_spherical_m(h, zen)
        flat = h / math.cos(zen)
        assert spherical > flat

    @pytest.mark.level0
    def test_airborne_flat_earth_regime(self) -> None:
        """At 8 km altitude, 30 deg: spherical ≈ flat-Earth to < 0.1%.

        Low altitude means small Earth curvature effect (~0.02%).
        """
        h = 8_000.0
        zen = math.radians(30.0)
        spherical = slant_range_spherical_m(h, zen)
        flat = h / math.cos(zen)
        assert abs(spherical - flat) / flat < 0.001

    @pytest.mark.level0
    def test_negative_zenith_raises(self) -> None:
        """Negative zenith angle raises ValueError."""
        with pytest.raises(ValueError, match="zenith"):
            slant_range_spherical_m(600_000.0, -0.1)

    @pytest.mark.level0
    def test_beyond_horizon_raises(self) -> None:
        """Zenith angle beyond the horizon raises ValueError.

        At 600 km, the horizon angle is arcsin(R_E/(R_E+h)) ≈ 66.05 deg.
        A zenith of 70 deg is below the horizon.
        """
        with pytest.raises(ValueError, match="horizon"):
            slant_range_spherical_m(600_000.0, math.radians(70.0))

    @pytest.mark.level0
    def test_near_horizon_finite(self) -> None:
        """Just inside the horizon limit: slant range is large but finite.

        At 600 km, horizon ≈ 66.05 deg. At 65 deg, should still work.
        """
        slant = slant_range_spherical_m(600_000.0, math.radians(65.0))
        assert slant > 0
        assert math.isfinite(slant)

    @pytest.mark.level0
    def test_zero_altitude(self) -> None:
        """altitude = 0: slant = 0 regardless of zenith."""
        assert slant_range_spherical_m(0.0, 0.0) == pytest.approx(0.0, abs=1e-10)


class TestIncidenceAngle:
    """Incidence angle at the ground from sensor zenith and altitude.

    sin(incidence) = (R_E + h) / R_E × sin(zenith)
    Incidence > zenith due to Earth curvature.
    """

    @pytest.mark.level0
    def test_nadir_returns_zero(self) -> None:
        """At zenith=0, incidence = 0."""
        assert incidence_angle_rad(600_000.0, 0.0) == pytest.approx(0.0, abs=1e-15)

    @pytest.mark.level0
    def test_45deg_600km(self) -> None:
        """At 45 deg zenith from 600 km, incidence ≈ 50.7 deg.

        sin(inc) = (6971/6371) × sin(45°) = 1.09419 × 0.70711 = 0.77373
        inc = arcsin(0.77373) ≈ 50.68 deg
        """
        inc = incidence_angle_rad(600_000.0, math.radians(45.0))
        assert math.degrees(inc) == pytest.approx(50.68, abs=0.1)

    @pytest.mark.level0
    def test_incidence_exceeds_zenith(self) -> None:
        """Incidence angle at ground always exceeds sensor zenith (for h > 0)."""
        zen = math.radians(30.0)
        inc = incidence_angle_rad(600_000.0, zen)
        assert inc > zen

    @pytest.mark.level0
    def test_small_angle_incidence_approx_zenith(self) -> None:
        """At small zenith, incidence ≈ zenith (Earth curvature negligible)."""
        zen = math.radians(5.0)
        inc = incidence_angle_rad(600_000.0, zen)
        assert abs(inc - zen) / zen < 0.12  # < 12% difference at 5 deg

    @pytest.mark.level0
    def test_airborne_incidence_approx_zenith(self) -> None:
        """At 8 km altitude, incidence ≈ zenith (negligible curvature)."""
        zen = math.radians(30.0)
        inc = incidence_angle_rad(8_000.0, zen)
        assert inc == pytest.approx(zen, rel=0.002)  # < 0.2% difference

    @pytest.mark.level0
    def test_negative_zenith_raises(self) -> None:
        """Negative zenith angle raises ValueError."""
        with pytest.raises(ValueError, match="zenith"):
            incidence_angle_rad(600_000.0, -0.1)


# ---------------------------------------------------------------------------
# Level 0c — off-nadir GSD with spherical Earth correction
# ---------------------------------------------------------------------------


class TestOffNadirGSD:
    """Off-nadir GSD using spherical Earth slant range and incidence angle.

    Reference: scenario 3.4 system (8 µm pixel, f=3.5 m, 600 km altitude).
    Truth values computed from ray-sphere intersection (verified in test
    derivation). NOTE: these differ from the original walkthrough.md which
    used the atmospheric slant-path formula instead of geometric slant range.

    Cross-track GSD = p × slant_range / f
    Along-track GSD = p × slant_range / (f × cos(incidence))
    Geometric mean = sqrt(cross × along)
    """

    # Scenario 3.4 system parameters
    P_X = 8e-6    # pixel pitch [m]
    P_Y = 8e-6    # pixel pitch [m]
    F = 3.5        # focal length [m]
    H = 600_000.0  # altitude [m]

    @pytest.mark.level0
    def test_nadir_cross_equals_along(self) -> None:
        """At zenith=0, cross-track = along-track = p × H / f exactly."""
        result = compute_gsd(self.P_X, self.P_Y, self.H, self.F,
                             path_zenith_rad=0.0)
        expected = self.P_X * self.H / self.F  # 1.371 m
        assert result.cross_track_m == pytest.approx(expected, rel=1e-10)
        assert result.along_track_m == pytest.approx(expected, rel=1e-10)

    @pytest.mark.level0
    def test_nadir_default_zenith(self) -> None:
        """Default path_zenith_rad=0.0 gives nadir formula (backward compat)."""
        result_default = compute_gsd(self.P_X, self.P_Y, self.H, self.F)
        result_explicit = compute_gsd(self.P_X, self.P_Y, self.H, self.F,
                                      path_zenith_rad=0.0)
        assert result_default.cross_track_m == result_explicit.cross_track_m
        assert result_default.along_track_m == result_explicit.along_track_m

    @pytest.mark.level0
    def test_45deg_cross_track(self) -> None:
        """At 45 deg, cross-track GSD ≈ 2.04 m.

        slant(45°, 600 km) = 892.9 km
        GSD_cross = 8e-6 × 892900 / 3.5 = 2.041 m
        """
        result = compute_gsd(self.P_X, self.P_Y, self.H, self.F,
                             path_zenith_rad=math.radians(45.0))
        assert result.cross_track_m == pytest.approx(2.041, rel=0.005)

    @pytest.mark.level0
    def test_45deg_along_track(self) -> None:
        """At 45 deg, along-track GSD ≈ 3.22 m.

        incidence(45°, 600 km) ≈ 50.7 deg
        GSD_along = 8e-6 × 892900 / (3.5 × cos(50.7°)) = 3.221 m
        """
        result = compute_gsd(self.P_X, self.P_Y, self.H, self.F,
                             path_zenith_rad=math.radians(45.0))
        assert result.along_track_m == pytest.approx(3.221, rel=0.005)

    @pytest.mark.level0
    def test_30deg_values(self) -> None:
        """At 30 deg from 600 km: cross ≈ 1.61 m, along ≈ 1.92 m.

        slant(30°) = 704.1 km, incidence ≈ 33.2 deg
        """
        result = compute_gsd(self.P_X, self.P_Y, self.H, self.F,
                             path_zenith_rad=math.radians(30.0))
        assert result.cross_track_m == pytest.approx(1.609, rel=0.005)
        assert result.along_track_m == pytest.approx(1.923, rel=0.005)

    @pytest.mark.level0
    def test_15deg_values(self) -> None:
        """At 15 deg from 600 km: cross ≈ 1.42 m, along ≈ 1.49 m."""
        result = compute_gsd(self.P_X, self.P_Y, self.H, self.F,
                             path_zenith_rad=math.radians(15.0))
        assert result.cross_track_m == pytest.approx(1.425, rel=0.005)
        assert result.along_track_m == pytest.approx(1.485, rel=0.005)

    @pytest.mark.level0
    def test_along_track_exceeds_cross_track(self) -> None:
        """At off-nadir, along-track GSD > cross-track GSD (foreshortening)."""
        result = compute_gsd(self.P_X, self.P_Y, self.H, self.F,
                             path_zenith_rad=math.radians(30.0))
        assert result.along_track_m > result.cross_track_m

    @pytest.mark.level0
    def test_geometric_mean(self) -> None:
        """Geometric mean = sqrt(cross × along)."""
        result = compute_gsd(self.P_X, self.P_Y, self.H, self.F,
                             path_zenith_rad=math.radians(45.0))
        expected_gm = math.sqrt(result.cross_track_m * result.along_track_m)
        assert result.geometric_mean_m == pytest.approx(expected_gm, rel=1e-10)

    @pytest.mark.level0
    def test_geometric_mean_nadir_equals_gsd(self) -> None:
        """At nadir with square pixels, geometric mean = GSD."""
        result = compute_gsd(self.P_X, self.P_Y, self.H, self.F,
                             path_zenith_rad=0.0)
        assert result.geometric_mean_m == pytest.approx(
            result.cross_track_m, rel=1e-10
        )

    @pytest.mark.level0
    def test_gsd_increases_with_zenith(self) -> None:
        """GSD monotonically increases with zenith angle."""
        prev_cross = 0.0
        for deg in [0, 15, 30, 45]:
            result = compute_gsd(self.P_X, self.P_Y, self.H, self.F,
                                 path_zenith_rad=math.radians(deg))
            assert result.cross_track_m > prev_cross
            prev_cross = result.cross_track_m

    @pytest.mark.level0
    def test_airborne_small_correction(self) -> None:
        """Airborne at 8 km, 30 deg: off-nadir GSD ≈ flat-Earth GSD.

        At low altitude, spherical correction is negligible (<0.01%).
        Flat-Earth: GSD = p × H/(f×cos(30°)) = 15e-6 × 8000/(0.5×0.866) = 0.277 m
        """
        result = compute_gsd(
            15e-6, 15e-6, 8_000.0, 0.5,
            path_zenith_rad=math.radians(30.0),
        )
        flat_slant = 8_000.0 / math.cos(math.radians(30.0))
        flat_cross = 15e-6 * flat_slant / 0.5
        assert result.cross_track_m == pytest.approx(flat_cross, rel=0.001)


# ---------------------------------------------------------------------------
# Level 1 — ChainState wiring and graceful skips
# ---------------------------------------------------------------------------


class TestGSDMetricsWiring:
    @pytest.mark.level1
    def test_metrics_populated(self) -> None:
        """GSD appears in ChainState metrics for orbital scenario."""
        state = _make_state()
        params = _make_params(altitude_m=500_000.0, focal_length_m=1.2, pitch_x_um=18.0)
        out = _compute_gsd_metrics(state, params)
        assert out.metrics["gsd_cross_track_m"] == pytest.approx(7.5, rel=1e-10)
        assert out.metrics["gsd_along_track_m"] == pytest.approx(7.5, rel=1e-10)

    @pytest.mark.level1
    def test_no_altitude_skips(self) -> None:
        """Lab/TVAC scenario: no altitude in schema. GSD should not appear."""
        state = _make_state()
        params = _make_params(altitude_m=None)
        out = _compute_gsd_metrics(state, params)
        assert "gsd_cross_track_m" not in out.metrics
        assert "gsd_along_track_m" not in out.metrics

    @pytest.mark.level1
    def test_zero_altitude_skips(self) -> None:
        """Ground-level sensor: altitude = 0. GSD = 0 is meaningless, skip."""
        state = _make_state()
        params = _make_params(altitude_m=0.0)
        out = _compute_gsd_metrics(state, params)
        assert "gsd_cross_track_m" not in out.metrics

    @pytest.mark.level1
    def test_zenith_zero_matches_nadir(self) -> None:
        """path_zenith_rad=0.0 gives identical GSD to current nadir behavior."""
        state = _make_state()
        params_no_zen = _make_params(altitude_m=600_000.0, focal_length_m=3.5,
                                     pitch_x_um=8.0)
        params_zen0 = _make_params(altitude_m=600_000.0, focal_length_m=3.5,
                                   pitch_x_um=8.0, path_zenith_rad=0.0)
        out_no = _compute_gsd_metrics(state, params_no_zen)
        out_zen = _compute_gsd_metrics(state, params_zen0)
        assert out_zen.metrics["gsd_cross_track_m"] == pytest.approx(
            out_no.metrics["gsd_cross_track_m"], rel=1e-10
        )
        assert out_zen.metrics["gsd_along_track_m"] == pytest.approx(
            out_no.metrics["gsd_along_track_m"], rel=1e-10
        )

    @pytest.mark.level1
    def test_off_nadir_gives_larger_gsd(self) -> None:
        """path_zenith_rad > 0 gives larger GSD than nadir."""
        state = _make_state()
        params_nadir = _make_params(altitude_m=600_000.0, focal_length_m=3.5,
                                    pitch_x_um=8.0, path_zenith_rad=0.0)
        params_offnadir = _make_params(altitude_m=600_000.0, focal_length_m=3.5,
                                       pitch_x_um=8.0,
                                       path_zenith_rad=math.radians(30.0))
        out_nadir = _compute_gsd_metrics(state, params_nadir)
        out_off = _compute_gsd_metrics(state, params_offnadir)
        assert out_off.metrics["gsd_cross_track_m"] > out_nadir.metrics["gsd_cross_track_m"]
        assert out_off.metrics["gsd_along_track_m"] > out_nadir.metrics["gsd_along_track_m"]

    @pytest.mark.level1
    def test_geometric_mean_in_metrics(self) -> None:
        """gsd_geometric_mean_m is stored in metrics."""
        state = _make_state()
        params = _make_params(altitude_m=600_000.0, focal_length_m=3.5,
                              pitch_x_um=8.0, path_zenith_rad=math.radians(30.0))
        out = _compute_gsd_metrics(state, params)
        gm = out.metrics["gsd_geometric_mean_m"]
        cross = out.metrics["gsd_cross_track_m"]
        along = out.metrics["gsd_along_track_m"]
        assert gm == pytest.approx(math.sqrt(cross * along), rel=1e-10)


# ---------------------------------------------------------------------------
# Level 1 — Access metrics wiring
# ---------------------------------------------------------------------------


class TestAccessMetricsWiring:
    """Verify access geometry metrics wired via _compute_access_metrics."""

    @pytest.mark.level1
    def test_ground_range_at_nadir(self) -> None:
        """At nadir, ground_range_m = 0."""
        state = _make_state()
        params = _make_params(
            altitude_m=600_000.0, focal_length_m=3.5, pitch_x_um=8.0,
            path_zenith_rad=0.0, n_pixels_cross=10_000,
        )
        state = _compute_gsd_metrics(state, params)
        from radiant.performance.stage import _compute_access_metrics
        out = _compute_access_metrics(state, params)
        assert out.metrics["ground_range_m"] == pytest.approx(0.0, abs=1e-10)

    @pytest.mark.level1
    def test_ground_range_offnadir(self) -> None:
        """Off-nadir produces nonzero ground range."""
        state = _make_state()
        params = _make_params(
            altitude_m=600_000.0, focal_length_m=3.5, pitch_x_um=8.0,
            path_zenith_rad=math.radians(30.0), n_pixels_cross=10_000,
        )
        state = _compute_gsd_metrics(state, params)
        from radiant.performance.stage import _compute_access_metrics
        out = _compute_access_metrics(state, params)
        assert out.metrics["ground_range_m"] > 0.0

    @pytest.mark.level1
    def test_swath_width_present(self) -> None:
        """Swath width = GSD_cross × n_pixels_cross."""
        state = _make_state()
        params = _make_params(
            altitude_m=600_000.0, focal_length_m=3.5, pitch_x_um=8.0,
            path_zenith_rad=0.0, n_pixels_cross=10_000,
        )
        state = _compute_gsd_metrics(state, params)
        from radiant.performance.stage import _compute_access_metrics
        out = _compute_access_metrics(state, params)
        gsd_cross = out.metrics["gsd_cross_track_m"]
        expected_swath = gsd_cross * 10_000
        assert out.metrics["swath_width_m"] == pytest.approx(
            expected_swath, rel=1e-10,
        )

    @pytest.mark.level1
    def test_access_rate_with_speed(self) -> None:
        """Access rate = swath × ground_speed."""
        state = _make_state()
        params = _make_params(
            altitude_m=600_000.0, focal_length_m=3.5, pitch_x_um=8.0,
            path_zenith_rad=0.0, n_pixels_cross=10_000,
            ground_speed_m_s=6_900.0,
        )
        state = _compute_gsd_metrics(state, params)
        from radiant.performance.stage import _compute_access_metrics
        out = _compute_access_metrics(state, params)
        swath = out.metrics["swath_width_m"]
        expected_rate = swath * 6_900.0
        assert out.metrics["access_rate_m2_s"] == pytest.approx(
            expected_rate, rel=1e-10,
        )

    @pytest.mark.level1
    def test_no_speed_skips_rate(self) -> None:
        """Without ground_speed, access_rate is not in metrics."""
        state = _make_state()
        params = _make_params(
            altitude_m=600_000.0, focal_length_m=3.5, pitch_x_um=8.0,
            path_zenith_rad=0.0, n_pixels_cross=10_000,
        )
        state = _compute_gsd_metrics(state, params)
        from radiant.performance.stage import _compute_access_metrics
        out = _compute_access_metrics(state, params)
        assert "swath_width_m" in out.metrics
        assert "access_rate_m2_s" not in out.metrics

    @pytest.mark.level1
    def test_no_n_pixels_skips_swath(self) -> None:
        """Without n_pixels_cross, swath and access rate are not in metrics."""
        state = _make_state()
        params = _make_params(
            altitude_m=600_000.0, focal_length_m=3.5, pitch_x_um=8.0,
            path_zenith_rad=0.0,
        )
        state = _compute_gsd_metrics(state, params)
        from radiant.performance.stage import _compute_access_metrics
        out = _compute_access_metrics(state, params)
        assert "ground_range_m" in out.metrics
        assert "swath_width_m" not in out.metrics

    @pytest.mark.level1
    def test_no_altitude_skips_all(self) -> None:
        """Without altitude, no access metrics."""
        state = _make_state()
        params = _make_params(altitude_m=None)
        from radiant.performance.stage import _compute_access_metrics
        out = _compute_access_metrics(state, params)
        assert "ground_range_m" not in out.metrics
