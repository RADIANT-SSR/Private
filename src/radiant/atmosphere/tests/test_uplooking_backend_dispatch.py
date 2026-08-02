"""Observer-leg backend dispatch for the up-looking topology (CU-226).

Level 0 — which backend arrangement ``supports_uplooking`` admits, which leg
each one serves, and what the refusals say.  The physics of the interpolated
column itself is pinned by ``test_interpolated_uplooking.py``; this module is
the *dispatch* contract:

* a bare ``SimpleAtmosphere`` still serves every leg (zero drift);
* an up-looking run family with a companion serves the observer leg from the
  family and everything else from the companion;
* an up-looking run family **without** a companion is not admitted — it would
  otherwise reach the illumination proxy and fail five calls deeper;
* a level path on a column ladder is refused, not approximated;
* ``L_toward_upper`` is never asked of a one-direction family — the up-looking
  observer leg always reads ``toward_lower`` (design question (i)).
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pytest

from radiant.atmosphere._schema import ALL_PARAMETERS as ATMO_PARAMS
from radiant.atmosphere.interpolated import GeometryPoint, InterpolatedAtmosphere
from radiant.atmosphere.observer_leg import observer_leg_from_los
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.atmosphere.uplooking_quantities import (
    evaluate_uplooking_topology,
    supports_uplooking,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.spectral import SpectralData
from radiant.geometry._schema import ALL_PARAMETERS as GEO_PARAMS

_WL = np.linspace(3.0, 5.0, 9)


@pytest.fixture
def params() -> ParameterSet:
    ps = ParameterSet(list(GEO_PARAMS + ATMO_PARAMS))
    ps.set("geometry.sensor_altitude_m", 0.0)
    ps.set("atmosphere.model", "simple")
    ps.resolve()
    return ps


# Grey synthetic rungs: tau = 1 at the sensor plane, tau = 0.25 at 10 km, so
# every expected value below is an exact hand calculation.
_TAU_TOP = 0.25
_L_TOP = 4.0


def _spectral(name: str, value: float, unit: str) -> SpectralData:
    return SpectralData(
        name=name,
        wavelength_um=_WL.copy(),
        values=np.full_like(_WL, value),
        unit=unit,
        source="test fixture",
    )


def _point(target_m: float, tau: float, l_down: float) -> GeometryPoint:
    return GeometryPoint(
        coordinates={
            "sensor_altitude_m": 0.0,
            "target_altitude_m": target_m,
            "path_zenith_rad": 0.0,
            "solar_zenith_rad": 0.0,
            "solar_azimuth_rad": 0.0,
        },
        transmittance=_spectral("tau", tau, ""),
        path_radiance=_spectral("L_toward_lower", l_down, "W/m²/sr/µm"),
        atm_emission_down=_spectral("unused", 0.0, "W/m²/sr/µm"),
    )


def _simple() -> SimpleAtmosphere:
    return SimpleAtmosphere(
        visibility_km=23.0,
        aerosol_type="rural",
        precipitable_water_cm=1.4,
        standard_atmosphere="midlat_summer",
    )


def _family(*, companion: object | None) -> InterpolatedAtmosphere:
    return InterpolatedAtmosphere(
        [_point(0.0, 1.0, 0.0), _point(10_000.0, _TAU_TOP, _L_TOP)],
        axes=["target_altitude_m"],
        family_direction="up",
        uplooking_companion=companion,
    )


def _los(h_sensor: float = 0.0, h_tgt: float = 10_000.0) -> LineOfSightGeometry:
    return LineOfSightGeometry(
        h_sensor=h_sensor,
        h_tgt=h_tgt,
        theta_o=math.pi,
        theta_s=math.radians(30.0),
        delta_phi=0.0,
    )


class TestSupportsUplooking:
    """Which backend arrangements are admitted."""

    def test_simple_is_admitted(self) -> None:
        assert supports_uplooking(_simple()) is True

    def test_uplooking_family_with_companion_is_admitted(self) -> None:
        assert supports_uplooking(_family(companion=_simple())) is True

    def test_uplooking_family_without_companion_is_refused(self) -> None:
        """No companion means no illumination and no sky leg — refuse at the gate."""
        assert supports_uplooking(_family(companion=None)) is False

    def test_down_looking_family_is_refused(self) -> None:
        down = InterpolatedAtmosphere(
            [_point(0.0, 1.0, 0.0), _point(10_000.0, _TAU_TOP, _L_TOP)],
            axes=["target_altitude_m"],
        )
        assert supports_uplooking(down) is False

    def test_unrelated_object_is_refused(self) -> None:
        assert supports_uplooking(object()) is False

    def test_companion_on_a_down_looking_family_is_refused_at_construction(self) -> None:
        from radiant.atmosphere.errors import AtmosphereValidationError

        with pytest.raises(AtmosphereValidationError, match="uplooking_companion"):
            InterpolatedAtmosphere(
                [_point(0.0, 1.0, 0.0), _point(10_000.0, _TAU_TOP, _L_TOP)],
                axes=["target_altitude_m"],
                family_direction="down",
                uplooking_companion=_simple(),
            )


class TestObserverLegComesFromTheFamily:
    """The whole point of CU-226: the shipped data reaches a composed answer."""

    @pytest.fixture()
    def products(self, params):  # type: ignore[no-untyped-def]
        with pytest.warns(UserWarning, match="TWO atmosphere models"):
            return evaluate_uplooking_topology(_family(companion=_simple()), _WL, _los(), params)

    def test_tau_up_is_the_family_value(self, products) -> None:  # type: ignore[no-untyped-def]
        """τ_obs at the top rung is the rung's own τ, to floating-point exactness."""
        assert products.quantities.tau_up == pytest.approx(_TAU_TOP, abs=1e-12)

    def test_l_path_up_is_the_family_downwelling(self, products) -> None:  # type: ignore[no-untyped-def]
        assert products.quantities.L_path_up == pytest.approx(_L_TOP, abs=1e-12)

    def test_provenance_names_the_evaluator(self, products) -> None:  # type: ignore[no-untyped-def]
        prov = products.provenance["observer_segment_provenance"]
        assert prov["evaluator"] == "InterpolatedAtmosphere.uplooking_column_product"
        assert prov["radiance_product"] == "L_toward_lower"

    def test_backend_split_is_recorded(self, products) -> None:  # type: ignore[no-untyped-def]
        split = products.provenance["backend_split"]
        assert "InterpolatedAtmosphere" in split
        assert "SimpleAtmosphere companion" in split

    def test_sky_at_aperture_is_still_computed(self, products) -> None:  # type: ignore[no-untyped-def]
        """The companion serves the leg the family cannot: a non-zero sky."""
        sky = np.asarray(products.sky_radiance_at_aperture)
        assert sky.shape == _WL.shape
        assert np.all(sky >= 0.0)
        assert float(sky.max()) > 0.0

    def test_the_split_is_also_logged_at_info(self, params, caplog) -> None:  # type: ignore[no-untyped-def]
        """All three declarations, not two (CU-224 ratification condition).

        The hybrid was owner-ratified 2026-08-01 **conditional on staying
        declared**: ``UserWarning`` + INFO log record + ``backend_split``
        provenance marker.  The warning and the marker have their own tests
        above; this pins the third, so softening any one of them fails a test
        rather than passing quietly.
        """
        with (
            caplog.at_level(logging.INFO, logger="radiant.atmosphere.uplooking_quantities"),
            pytest.warns(UserWarning, match="TWO atmosphere models"),
        ):
            evaluate_uplooking_topology(_family(companion=_simple()), _WL, _los(), params)
        assert any("backend" in record.getMessage().lower() for record in caplog.records), (
            "the hybrid split must leave an INFO record, not only a warning"
        )


class TestZeroDriftForSimple:
    """``atmosphere.model='simple'`` takes exactly the pre-CU-226 route."""

    def test_simple_records_a_single_backend(self, params) -> None:  # type: ignore[no-untyped-def]
        products = evaluate_uplooking_topology(_simple(), _WL, _los(), params)
        assert products.provenance["backend_split"] == "all legs: SimpleAtmosphere"

    def test_simple_emits_no_hybrid_warning(self, params, recwarn) -> None:  # type: ignore[no-untyped-def]
        evaluate_uplooking_topology(_simple(), _WL, _los(), params)
        assert not [w for w in recwarn.list if "TWO atmosphere models" in str(w.message)]


class TestRefusals:
    def test_level_path_on_a_column_ladder_is_refused(self, params) -> None:  # type: ignore[no-untyped-def]
        """A level arm is no rung of a ladder — Rule 17 refusal, not an approximation."""
        level = LineOfSightGeometry(
            h_sensor=3_000.0,
            h_tgt=3_000.0,
            theta_o=math.pi / 2.0,
            theta_s=math.radians(30.0),
            delta_phi=0.0,
        )
        with pytest.raises(ParameterBoundsError, match="LEVEL path"):
            evaluate_uplooking_topology(_family(companion=_simple()), _WL, level, params)

    def test_capability_error_names_the_interpolated_route(self, params) -> None:  # type: ignore[no-untyped-def]
        """The refusal an unsupported backend gets must mention what now works."""
        with pytest.raises(ParameterBoundsError, match="up-looking run family"):
            evaluate_uplooking_topology(object(), _WL, _los(), params)


class TestDirectionIsAlwaysTowardLower:
    """Design question (i): ``L_toward_upper`` is unreachable on this branch."""

    @pytest.mark.parametrize("h_tgt", [1.0, 5_000.0, 10_000.0])
    def test_up_looking_observer_leg_reads_toward_lower(self, h_tgt: float) -> None:
        leg = observer_leg_from_los(_los(h_tgt=h_tgt))
        assert leg.toward_sensor == "toward_lower"
