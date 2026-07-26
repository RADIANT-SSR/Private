"""Guardrail G2 — the sensor endpoint has exactly one source: ``los.h_sensor``.

``docs/plans/Geometry_Flexibility_Plan.md`` §3.5 G2: the PR that puts
``h_sensor`` on :class:`~radiant.core.los_geometry.LineOfSightGeometry`
deletes every backend side-load of ``geometry.sensor_altitude_m``.  These
tests prove the property behaviourally (not by grep): when the LOS and the
ParameterSet disagree, the answer tracks the **LOS**, and a LOS that does
not carry the endpoint fails with an actionable error instead of silently
falling back to the parameter.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from radiant.atmosphere._sensor_endpoint import require_sensor_altitude_m
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError

from .test_evaluate import _resolved_params


@pytest.fixture
def wl() -> np.ndarray:
    return np.linspace(8.0, 13.0, 51)


def _evaluate(los: LineOfSightGeometry, wl: np.ndarray, params_sensor_alt_m: float) -> np.ndarray:
    """τ_up from SimpleAtmosphere for *los*, with params pinned elsewhere."""
    atm = SimpleAtmosphere(standard_atmosphere="midlat_summer")
    params = _resolved_params(wl, sensor_altitude_m=params_sensor_alt_m)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return atm.evaluate(wl, los, params).tau_up


class TestOneSourceOfTruth:
    @pytest.mark.level1
    def test_result_tracks_the_los_not_the_parameter(self, wl: np.ndarray) -> None:
        """τ_up follows ``los.h_sensor`` even when the parameter disagrees.

        A 2 km sensor sees a much shorter column than a 500 km one, so the
        two τ_up arrays are far apart — there is no tolerance question.  The
        parameter is deliberately set to the *other* value in each run: if
        any backend still side-loaded it, the two assertions could not both
        hold.
        """
        los_2km = LineOfSightGeometry(h_tgt=0.0, h_sensor=2_000.0, theta_o=0.0, h_atm_top=1.0e5)
        los_500km = LineOfSightGeometry(h_tgt=0.0, h_sensor=500_000.0, theta_o=0.0, h_atm_top=1.0e5)

        tau_2km_param_wrong = _evaluate(los_2km, wl, params_sensor_alt_m=500_000.0)
        tau_2km_param_right = _evaluate(los_2km, wl, params_sensor_alt_m=2_000.0)
        tau_500km_param_wrong = _evaluate(los_500km, wl, params_sensor_alt_m=2_000.0)

        np.testing.assert_array_equal(tau_2km_param_wrong, tau_2km_param_right)
        assert float(tau_2km_param_wrong.min()) > float(tau_500km_param_wrong.min()), (
            "a 2 km up-leg column must transmit more than a 500 km one — the "
            "backend is not reading the LOS endpoint"
        )

    @pytest.mark.level1
    def test_missing_endpoint_raises_actionable_error(self, wl: np.ndarray) -> None:
        """A pre-ADR-0011 payload fails loud — no silent params fallback."""
        legacy = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, h_atm_top=1.0e5)
        assert legacy.h_sensor is None
        with pytest.raises(ParameterBoundsError, match="does not carry the sensor endpoint"):
            _evaluate(legacy, wl, params_sensor_alt_m=2_000.0)

    @pytest.mark.level0
    def test_error_action_names_the_fixture_remedy(self) -> None:
        """Rule 15: the action tells a fixture author exactly what to add."""
        legacy = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        with pytest.raises(ParameterBoundsError) as exc:
            require_sensor_altitude_m(legacy, "unit-test")
        message = str(exc.value)
        assert "h_sensor=" in message
        assert "tests/" in message

    @pytest.mark.level0
    def test_returns_the_carried_altitude(self) -> None:
        los = LineOfSightGeometry(h_tgt=0.0, h_sensor=12_345.0, theta_o=0.0)
        assert require_sensor_altitude_m(los, "unit-test") == pytest.approx(
            12_345.0, rel=0.0, abs=0.0
        )
