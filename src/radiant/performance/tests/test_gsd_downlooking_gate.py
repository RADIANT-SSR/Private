"""GSD is published only for down-looking scenes (up-looking crash, walkthrough item 3/4).

Ground sample distance is the ground footprint of one pixel, so it exists only
when the LOS intersects a ground plane *below* the sensor.  GeometryStage
publishes ``incidence_angle_rad = theta_o``, and an up-looking scene (sensor
beneath the target) legitimately carries θ_o = π.  Before this gate,
:func:`~radiant.performance.stage._compute_gsd_metrics` handed that π straight
to ``compute_gsd_from_geometry``, whose ``[0, π/2)`` validator raised — aborting
the **entire** chain evaluation, not just the one metric.  In the GUI that
surfaced as "Parameter Rejected — incidence_angle_rad = 3.14159… must be in
[0, pi/2)" when the operator set a target altitude above the sensor, and as a
schematic that would no longer redraw.

The metric must instead be *absent* for a scene it does not describe, which is
this module's established convention for an inapplicable metric.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.detector._schema import PIXEL_PITCH_X, PIXEL_PITCH_Y
from radiant.geometry._schema import PATH_ZENITH_RAD, SENSOR_ALTITUDE_M
from radiant.optics._schema import FOCAL_LENGTH_M
from radiant.performance.stage import _compute_gsd_metrics

_ALT_M = 10_000.0  # an airborne sensor — nonzero, so the altitude guard does not mask
_FOCAL_M = 1.2
_PITCH_UM = 18.0

_GSD_METRICS = ("gsd_cross_track_m", "gsd_along_track_m", "gsd_geometric_mean_m")


def _params(theta_o_rad: float) -> ParameterSet:
    ps = ParameterSet(
        [FOCAL_LENGTH_M, PIXEL_PITCH_X, PIXEL_PITCH_Y, SENSOR_ALTITUDE_M, PATH_ZENITH_RAD]
    )
    ps.set("geometry.sensor_altitude_m", _ALT_M)
    ps.set("geometry.path_zenith_rad", theta_o_rad)
    ps.set("optics.focal_length_m", _FOCAL_M)
    ps.set("detector.pixel_pitch_x_um", _PITCH_UM)
    ps.set("detector.pixel_pitch_y_um", _PITCH_UM)
    ps.resolve()
    return ps


def _state(direction: str | None, theta_o_rad: float) -> ChainState:
    """A state as GeometryStage publishes it; *direction* ``None`` omits the label."""
    state = ChainState(wavelength_um=np.linspace(3.5, 5.0, 10))
    if direction is None:
        return state
    slant = abs(_ALT_M - 30_000.0) if direction == "up" else _ALT_M
    return (
        state.with_stage_output("geometry", "los_direction", direction)
        .with_stage_output("geometry", "slant_range_m", slant)
        .with_stage_output("geometry", "incidence_angle_rad", theta_o_rad)
    )


class TestUpLookingSkipsGsd:
    """θ_o = π (sensor below target) publishes no GSD and, crucially, does not raise."""

    def test_uplooking_does_not_raise(self) -> None:
        _compute_gsd_metrics(_state("up", math.pi), _params(math.pi))

    @pytest.mark.parametrize("metric", _GSD_METRICS)
    def test_uplooking_publishes_no_gsd(self, metric: str) -> None:
        out = _compute_gsd_metrics(_state("up", math.pi), _params(math.pi))
        assert metric not in out.metrics

    def test_uplooking_leaves_state_untouched(self) -> None:
        """A skipped metric returns the same state object — no partial writes."""
        state = _state("up", math.pi)
        assert _compute_gsd_metrics(state, _params(math.pi)) is state


class TestLevelSkipsGsd:
    """A level LOS (θ_o = π/2) has no ground footprint either."""

    @pytest.mark.parametrize("metric", _GSD_METRICS)
    def test_level_publishes_no_gsd(self, metric: str) -> None:
        out = _compute_gsd_metrics(_state("level", math.pi / 2.0), _params(math.pi / 2.0))
        assert metric not in out.metrics


class TestDownLookingUnchanged:
    """Regression guard: the gate must not alter the down-looking result."""

    def test_nadir_gsd_is_pitch_times_altitude_over_focal(self) -> None:
        out = _compute_gsd_metrics(_state("down", 0.0), _params(0.0))
        assert out.metrics["gsd_cross_track_m"] == pytest.approx(
            _PITCH_UM * 1e-6 * _ALT_M / _FOCAL_M, rel=1e-12
        )

    def test_offnadir_down_still_publishes(self) -> None:
        theta_o = math.radians(40.0)
        out = _compute_gsd_metrics(_state("down", theta_o), _params(theta_o))
        for metric in _GSD_METRICS:
            assert metric in out.metrics


class TestDirectionLabelAbsentFallsBackToThetaO:
    """Partial fixtures without GeometryStage gate on θ_o directly (the CU-096 path)."""

    def test_uplooking_theta_o_skips_without_label(self) -> None:
        out = _compute_gsd_metrics(_state(None, math.pi), _params(math.pi))
        assert "gsd_cross_track_m" not in out.metrics

    def test_downlooking_theta_o_computes_without_label(self) -> None:
        out = _compute_gsd_metrics(_state(None, 0.0), _params(0.0))
        assert out.metrics["gsd_cross_track_m"] == pytest.approx(
            _PITCH_UM * 1e-6 * _ALT_M / _FOCAL_M, rel=1e-12
        )
