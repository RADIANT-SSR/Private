"""Off-nadir validation of the θ_o-consistent partial-fixture fallbacks (CU-096).

The live chain runs GeometryStage first, which publishes θ_o-consistent slant
range / ground range / incidence; the downstream performance & platform stages
consume those published values. But those stages also carry a *fallback* for
partial fixtures that never ran GeometryStage — and that fallback used to feed
``geometry.path_zenith_rad`` (which is the **target-side** path zenith θ_o) into
sensor-off-nadir-η helpers (``slant_range_spherical_m`` / ``compute_gsd`` /
``compute_ground_range_m``), describing a *different* line of sight off-nadir.

Every shipped golden sits at the nadir default (η = θ_o = 0) where the two
interpretations coincide, so the golden suite cannot see this. These tests pin
the fix at a real off-nadir angle: the fallback must now (a) equal the
θ_o-consistent geometry, and (b) equal what GeometryStage would have published —
and must *not* equal the old η-misinterpreting value.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.geometry import slant_range_spherical_m  # the η-based helper (the old bug)
from radiant.core.parameters import ParameterSet
from radiant.core.viewing_triangle import (
    ground_range_from_theta_o_m,
    slant_range_from_theta_o_m,
)
from radiant.detector._schema import PIXEL_PITCH_X, PIXEL_PITCH_Y
from radiant.geometry._schema import PATH_ZENITH_RAD, SENSOR_ALTITUDE_M
from radiant.optics._schema import APERTURE_DIAMETER_M, FOCAL_LENGTH_M
from radiant.performance.stage import (
    _compute_access_metrics,
    _compute_diffraction_limit_metrics,
    _compute_gsd_metrics,
)
from radiant.spectral_integration._schema import FILTER_MAX_UM, FILTER_MIN_UM

_ALT_M = 500_000.0
_THETA_O = math.radians(45.0)  # a real off-nadir angle where θ_o ≠ η
_FOCAL_M = 1.2
_PITCH_UM = 18.0


def _params(*, theta_o_rad: float) -> ParameterSet:
    ps = ParameterSet(
        [
            FOCAL_LENGTH_M,
            APERTURE_DIAMETER_M,
            PIXEL_PITCH_X,
            PIXEL_PITCH_Y,
            SENSOR_ALTITUDE_M,
            PATH_ZENITH_RAD,
            FILTER_MIN_UM,
            FILTER_MAX_UM,
        ]
    )
    ps.set("geometry.sensor_altitude_m", _ALT_M)
    ps.set("geometry.path_zenith_rad", theta_o_rad)
    ps.set("optics.focal_length_m", _FOCAL_M)
    ps.set("optics.aperture_diameter_m", 0.3)
    ps.set("detector.pixel_pitch_x_um", _PITCH_UM)
    ps.set("detector.pixel_pitch_y_um", _PITCH_UM)
    ps.set("spectral_integration.filter_min_um", 3.5)
    ps.set("spectral_integration.filter_max_um", 5.0)
    ps.resolve()
    return ps


def _gsd_then_access(base_state: ChainState, params: ParameterSet) -> ChainState:
    """Run the GSD metric (its output is a precondition) then access metrics."""
    return _compute_access_metrics(_compute_gsd_metrics(base_state, params), params)


def _state_no_geometry() -> ChainState:
    """A partial-fixture state with no GeometryStage output → exercises the fallback."""
    return ChainState(wavelength_um=np.linspace(3.5, 5.0, 10))


def _state_with_published(theta_o_rad: float) -> ChainState:
    """A state carrying the θ_o-consistent values GeometryStage would publish."""
    slant = slant_range_from_theta_o_m(theta_o_rad, _ALT_M, 0.0)
    ground = ground_range_from_theta_o_m(theta_o_rad, _ALT_M, 0.0)
    return (
        ChainState(wavelength_um=np.linspace(3.5, 5.0, 10))
        .with_stage_output("geometry", "slant_range_m", slant)
        # On a spherical Earth the incidence angle at the target equals θ_o.
        .with_stage_output("geometry", "incidence_angle_rad", theta_o_rad)
        .with_stage_output("geometry", "ground_range_m", ground)
    )


class TestGsdFallbackUsesThetaO:
    def test_offnadir_gsd_matches_theta_o_slant(self) -> None:
        """The fallback GSD uses the θ_o slant range, not the η one."""
        out = _compute_gsd_metrics(_state_no_geometry(), _params(theta_o_rad=_THETA_O))
        slant_theta_o = slant_range_from_theta_o_m(_THETA_O, _ALT_M, 0.0)
        expected = _PITCH_UM * 1e-6 * slant_theta_o / _FOCAL_M
        assert out.metrics["gsd_cross_track_m"] == pytest.approx(expected, rel=1e-9)

    def test_offnadir_gsd_is_not_the_old_eta_value(self) -> None:
        """Guard against regressing to the η-misinterpreting slant (the CU-096 bug)."""
        out = _compute_gsd_metrics(_state_no_geometry(), _params(theta_o_rad=_THETA_O))
        slant_eta = slant_range_spherical_m(_ALT_M, _THETA_O)  # θ_o wrongly read as η
        wrong = _PITCH_UM * 1e-6 * slant_eta / _FOCAL_M
        # The two interpretations differ by ~8 % at 45° / 500 km — well outside tol.
        assert out.metrics["gsd_cross_track_m"] != pytest.approx(wrong, rel=1e-3)

    def test_fallback_equals_published(self) -> None:
        """Fallback (no GeometryStage) equals the GeometryStage-published GSD."""
        params = _params(theta_o_rad=_THETA_O)
        fallback = _compute_gsd_metrics(_state_no_geometry(), params)
        published = _compute_gsd_metrics(_state_with_published(_THETA_O), params)
        assert fallback.metrics["gsd_cross_track_m"] == pytest.approx(
            published.metrics["gsd_cross_track_m"], rel=1e-9
        )
        assert fallback.metrics["gsd_along_track_m"] == pytest.approx(
            published.metrics["gsd_along_track_m"], rel=1e-9
        )

    def test_nadir_unchanged(self) -> None:
        """At nadir the fallback is the plain pitch·h/f — regression guard."""
        out = _compute_gsd_metrics(_state_no_geometry(), _params(theta_o_rad=0.0))
        assert out.metrics["gsd_cross_track_m"] == pytest.approx(
            _PITCH_UM * 1e-6 * _ALT_M / _FOCAL_M, rel=1e-12
        )


class TestGroundRangeFallbackUsesThetaO:
    def test_offnadir_ground_range_matches_theta_o(self) -> None:
        out = _gsd_then_access(_state_no_geometry(), _params(theta_o_rad=_THETA_O))
        expected = ground_range_from_theta_o_m(_THETA_O, _ALT_M, 0.0)
        assert out.metrics["ground_range_m"] == pytest.approx(expected, rel=1e-9)

    def test_fallback_equals_published(self) -> None:
        params = _params(theta_o_rad=_THETA_O)
        fallback = _gsd_then_access(_state_no_geometry(), params)
        published = _gsd_then_access(_state_with_published(_THETA_O), params)
        assert fallback.metrics["ground_range_m"] == pytest.approx(
            published.metrics["ground_range_m"], rel=1e-9
        )


class TestDiffractionFallbackUsesThetaO:
    def test_offnadir_diffraction_uses_theta_o_slant(self) -> None:
        """The diffraction-limited ground spot uses the θ_o slant range."""
        params = _params(theta_o_rad=_THETA_O)
        fallback = _compute_diffraction_limit_metrics(_state_no_geometry(), params)
        published = _compute_diffraction_limit_metrics(_state_with_published(_THETA_O), params)
        assert "diffraction_limit_ground_m" in fallback.metrics
        assert fallback.metrics["diffraction_limit_ground_m"] == pytest.approx(
            published.metrics["diffraction_limit_ground_m"], rel=1e-9
        )
