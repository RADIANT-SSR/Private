"""Tests for GSD (ground sample distance) computation.

Level 0: analytic formula checks on ``compute_gsd`` (pure function).
Level 1: edge cases on ``_compute_gsd_metrics`` (ChainState wiring, graceful skips).
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.performance.gsd import GSDResult, compute_gsd
from radiant.performance.stage import _compute_gsd_metrics

from radiant.atmosphere._schema import SENSOR_ALTITUDE_M
from radiant.detector._schema import (
    PIXEL_PITCH_X,
    PIXEL_PITCH_Y,
)
from radiant.optics._schema import (
    APERTURE_DIAMETER_M,
    FOCAL_LENGTH_M,
)


def _make_params(
    altitude_m: float | None = 500_000.0,
    focal_length_m: float = 1.2,
    pitch_x_um: float = 18.0,
    pitch_y_um: float | None = None,
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
    ps = ParameterSet(schema)
    if altitude_m is not None:
        ps.set("geometry.sensor_altitude_m", altitude_m)
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
# Level 0 — pure function formula correctness
# ---------------------------------------------------------------------------


class TestGSDFormula:
    """GSD = pixel_pitch_m × altitude_m / focal_length_m."""

    def test_leo_500km_18um_pitch(self) -> None:
        """Standard LEO scenario: 18 µm pitch, f=1.2 m, h=500 km."""
        result = compute_gsd(
            pitch_x_m=18e-6, pitch_y_m=18e-6,
            altitude_m=500_000.0, focal_length_m=1.2,
        )
        assert result.cross_track_m == pytest.approx(7.5, rel=1e-10)
        assert result.along_track_m == pytest.approx(7.5, rel=1e-10)

    def test_geo_36000km_24um_pitch(self) -> None:
        """GEO scenario: 24 µm pitch, f=3.6 m, h=35786 km."""
        h = 35_786_000.0
        result = compute_gsd(
            pitch_x_m=24e-6, pitch_y_m=24e-6,
            altitude_m=h, focal_length_m=3.6,
        )
        expected = 24e-6 * h / 3.6  # ≈ 238.57 m
        assert result.cross_track_m == pytest.approx(expected, rel=1e-10)

    def test_rectangular_pixels(self) -> None:
        """Non-square pixels give different cross-track and along-track GSD."""
        result = compute_gsd(
            pitch_x_m=18e-6, pitch_y_m=24e-6,
            altitude_m=500_000.0, focal_length_m=1.2,
        )
        assert result.cross_track_m == pytest.approx(7.5, rel=1e-10)
        assert result.along_track_m == pytest.approx(10.0, rel=1e-10)

    def test_airborne_8km(self) -> None:
        """Airborne scenario: 15 µm pitch, f=0.5 m, h=8 km."""
        result = compute_gsd(
            pitch_x_m=15e-6, pitch_y_m=15e-6,
            altitude_m=8_000.0, focal_length_m=0.5,
        )
        assert result.cross_track_m == pytest.approx(0.24, rel=1e-10)

    def test_result_is_frozen(self) -> None:
        """GSDResult is immutable."""
        result = compute_gsd(18e-6, 18e-6, 500_000.0, 1.2)
        assert isinstance(result, GSDResult)
        with pytest.raises(AttributeError):
            result.cross_track_m = 999.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Level 1 — ChainState wiring and graceful skips
# ---------------------------------------------------------------------------


class TestGSDMetricsWiring:
    def test_metrics_populated(self) -> None:
        """GSD appears in ChainState metrics for orbital scenario."""
        state = _make_state()
        params = _make_params(altitude_m=500_000.0, focal_length_m=1.2, pitch_x_um=18.0)
        out = _compute_gsd_metrics(state, params)
        assert out.metrics["gsd_cross_track_m"] == pytest.approx(7.5, rel=1e-10)
        assert out.metrics["gsd_along_track_m"] == pytest.approx(7.5, rel=1e-10)

    def test_no_altitude_skips(self) -> None:
        """Lab/TVAC scenario: no altitude in schema. GSD should not appear."""
        state = _make_state()
        params = _make_params(altitude_m=None)
        out = _compute_gsd_metrics(state, params)
        assert "gsd_cross_track_m" not in out.metrics
        assert "gsd_along_track_m" not in out.metrics

    def test_zero_altitude_skips(self) -> None:
        """Ground-level sensor: altitude = 0. GSD = 0 is meaningless, skip."""
        state = _make_state()
        params = _make_params(altitude_m=0.0)
        out = _compute_gsd_metrics(state, params)
        assert "gsd_cross_track_m" not in out.metrics
