"""Geometry-projected metrics require GeometryStage's published values (CU-096 retired).

The CU-096 residue was a set of partial-fixture fallbacks that re-derived the
slant range / ground range / incidence angle from ``geometry.path_zenith_rad``
whenever PerformanceStage ran without GeometryStage. The Geometry-Flexibility
Phase 5 close retires them (guardrail G4 — a generalization does not keep its
carve-out): these stages now **consume only** what GeometryStage published.
A partial fixture that never ran GeometryStage gets *no* geometry-projected
metric — absent, not derived, and above all not silently wrong (the Phase-1
hemisphere validator made the old fallback raise for up-looking fixtures;
now there is nothing left to misinterpret).

Contract pinned here (see ``RADIANT_Geometry.md`` §4.3):

* **No GeometryStage output → the GSD family, ground range, and the
  diffraction ground projection are absent.** Skipped, never derived from
  parameters — and never an exception.
* **Published values are consumed verbatim** at a real off-nadir angle
  (θ_o = 45°, where the target-side θ_o and the sensor-side η differ by ~8 %
  in slant range at 500 km — the original CU-096 confusion this file's
  predecessor pinned).
* The live chain is unaffected: ``ChainRunner`` always runs GeometryStage
  first (its integration suite covers that path).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
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

_GSD_METRICS = ("gsd_cross_track_m", "gsd_along_track_m", "gsd_geometric_mean_m")


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
    # The parameter is set on purpose: the contract is that the stage does NOT
    # read it to derive geometry — a set-but-unconsumed θ_o must change nothing.
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
    """A partial-fixture state with no GeometryStage output → must skip, not derive."""
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


class TestNoGeometryStageSkips:
    """Without GeometryStage output the geometry-projected metrics are absent."""

    @pytest.mark.parametrize("metric", _GSD_METRICS)
    def test_gsd_absent(self, metric: str) -> None:
        out = _compute_gsd_metrics(_state_no_geometry(), _params(theta_o_rad=_THETA_O))
        assert metric not in out.metrics

    def test_gsd_skip_leaves_state_untouched(self) -> None:
        """The skip returns the same state object — no partial writes."""
        state = _state_no_geometry()
        assert _compute_gsd_metrics(state, _params(theta_o_rad=_THETA_O)) is state

    def test_ground_range_absent(self) -> None:
        out = _gsd_then_access(_state_no_geometry(), _params(theta_o_rad=_THETA_O))
        assert "ground_range_m" not in out.metrics

    def test_diffraction_ground_projection_absent(self) -> None:
        out = _compute_diffraction_limit_metrics(
            _state_no_geometry(), _params(theta_o_rad=_THETA_O)
        )
        assert "diffraction_limit_ground_m" not in out.metrics

    def test_nadir_params_do_not_resurrect_the_derivation(self) -> None:
        """Even the trivial nadir case is not derived from parameters."""
        out = _compute_gsd_metrics(_state_no_geometry(), _params(theta_o_rad=0.0))
        assert "gsd_cross_track_m" not in out.metrics


class TestPublishedGeometryConsumedVerbatim:
    """Published θ_o-consistent values drive the metrics exactly (the CU-096 physics)."""

    def test_offnadir_gsd_matches_theta_o_slant(self) -> None:
        out = _compute_gsd_metrics(_state_with_published(_THETA_O), _params(theta_o_rad=_THETA_O))
        slant_theta_o = slant_range_from_theta_o_m(_THETA_O, _ALT_M, 0.0)
        expected = _PITCH_UM * 1e-6 * slant_theta_o / _FOCAL_M
        assert out.metrics["gsd_cross_track_m"] == pytest.approx(expected, rel=1e-9)

    def test_offnadir_ground_range_matches_published(self) -> None:
        out = _gsd_then_access(_state_with_published(_THETA_O), _params(theta_o_rad=_THETA_O))
        expected = ground_range_from_theta_o_m(_THETA_O, _ALT_M, 0.0)
        assert out.metrics["ground_range_m"] == pytest.approx(expected, rel=1e-9)

    def test_offnadir_diffraction_uses_published_slant(self) -> None:
        out = _compute_diffraction_limit_metrics(
            _state_with_published(_THETA_O), _params(theta_o_rad=_THETA_O)
        )
        assert "diffraction_limit_ground_m" in out.metrics

    def test_nadir_gsd_is_pitch_times_altitude_over_focal(self) -> None:
        out = _compute_gsd_metrics(_state_with_published(0.0), _params(theta_o_rad=0.0))
        assert out.metrics["gsd_cross_track_m"] == pytest.approx(
            _PITCH_UM * 1e-6 * _ALT_M / _FOCAL_M, rel=1e-12
        )
