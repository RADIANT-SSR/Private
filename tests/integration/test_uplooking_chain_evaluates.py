"""An up-looking scene must evaluate end-to-end (GUI walkthrough items 3 & 4).

The reported symptom was a GUI one: raising ``geometry.target_altitude_m``
above the sensor altitude popped "Parameter Rejected — compute_gsd_from_geometry:
incidence_angle_rad = 3.141592653589793 must be in [0, pi/2)", and the geometry
schematic then refused to redraw.  Neither is a GUI defect.  An up-looking scene
publishes θ_o = π, ``PerformanceStage`` fed it to the GSD validator, and the
raise propagated out of ``evaluate()`` — so *every* consumer of the result
(metrics, readouts, the schematic that draws from the geometry outputs) died
together.

:mod:`radiant.performance.tests.test_gsd_downlooking_gate` pins the gate itself.
This module pins the property the operator actually cares about: the whole chain
completes for a sensor looking up, the non-ground metrics survive, and the
down-looking numbers are untouched.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from radiant.api.sensor import Sensor

_CONFIG = Path(__file__).resolve().parents[2] / "examples" / "mwir_leo_minimal.yaml"

_GSD_METRICS = ("gsd_cross_track_m", "gsd_along_track_m", "gsd_geometric_mean_m")


def _sensor(h_sensor_m: float, h_target_m: float) -> Sensor:
    """The shipped minimal MWIR config re-pointed at the requested altitude pair."""
    return (
        Sensor.load(_CONFIG)
        .set("geometry.sensor_altitude_m", h_sensor_m)
        .set("geometry.target_altitude_m", h_target_m)
    )


class TestAirborneSensorLookingUp:
    """A 10 km sensor viewing a 30 km target — the reported failing configuration."""

    @pytest.fixture(scope="class")
    def result(self):  # type: ignore[no-untyped-def]
        return _sensor(10_000.0, 30_000.0).evaluate()

    def test_chain_completes(self, result) -> None:  # type: ignore[no-untyped-def]
        """The evaluation that used to raise now returns a result at all."""
        assert result is not None

    def test_geometry_is_uplooking(self, result) -> None:  # type: ignore[no-untyped-def]
        """Confirm the fixture really exercises the up-looking branch (θ_o = π)."""
        geometry = result.stage_outputs["geometry"]
        assert geometry["los_direction"] == "up"
        assert geometry["theta_o_rad"] == pytest.approx(math.pi, abs=1e-12)

    @pytest.mark.parametrize("metric", _GSD_METRICS)
    def test_gsd_is_absent_not_wrong(self, result, metric: str) -> None:  # type: ignore[no-untyped-def]
        """No ground plane below the sensor → no ground sample distance."""
        assert result.metrics.get(metric) is None

    def test_radiometry_still_computed(self, result) -> None:  # type: ignore[no-untyped-def]
        """The metrics that do not reference a ground plane must survive the skip."""
        assert result.metrics.get("snr") is not None

    def test_geometry_outputs_available_for_the_schematic(self, result) -> None:  # type: ignore[no-untyped-def]
        """Item 4: the schematic draws from these, so they must exist post-evaluate."""
        geometry = result.stage_outputs["geometry"]
        for key in ("h_sensor_m", "h_target_m", "slant_range_m", "theta_o_rad"):
            assert geometry[key] is not None


class TestGroundSensorLookingUp:
    """A ground sensor (altitude 0) viewing a 30 km target also completes."""

    def test_chain_completes_and_skips_gsd(self) -> None:
        result = _sensor(0.0, 30_000.0).evaluate()
        assert result.stage_outputs["geometry"]["los_direction"] == "up"
        assert result.metrics.get("gsd_cross_track_m") is None


class TestDownLookingUnchanged:
    """Regression guard: the gate must not perturb the down-looking baseline."""

    def test_leo_nadir_gsd_still_computed(self) -> None:
        result = _sensor(500_000.0, 0.0).evaluate()
        assert result.stage_outputs["geometry"]["los_direction"] == "down"
        # pitch 18 µm × 500 km / f 1.2 m = 7.5 m, the shipped example's value.
        assert result.metrics["gsd_cross_track_m"] == pytest.approx(7.5, rel=1e-9)
