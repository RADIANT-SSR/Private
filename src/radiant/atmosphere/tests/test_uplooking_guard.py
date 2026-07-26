"""Phase-2-pending rejection of up-looking / level atmospheric paths.

ADR-0011 makes up-looking and level geometry legal to *express*; the
direction-aware atmosphere is Phase 2 (Gaps 108/109).  Until it lands,
:class:`~radiant.atmosphere.stage.AtmosphereStage` refuses such a path at
stage entry with one actionable error — instead of letting it reach a
backend and surface as a zenith-ceiling or "looking-up configuration"
message from three layers down.

The one up-looking geometry that *does* run today is the wholly-vacuum
one: both endpoints at or above ``h_atm_top`` (the LEO→GEO quick win of
Phase 1).  It is served exactly, with no column at all.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.atmosphere._schema import ALL_PARAMETERS as ATMO_PARAMS
from radiant.atmosphere.exo_target import evaluate_with_exo_target
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.atmosphere.stage import AtmosphereStage
from radiant.core.chain import ChainState
from radiant.core.descriptors import T1Thermal
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.spectral import SpectralData
from radiant.geometry._schema import ALL_PARAMETERS as GEO_PARAMS

H_ATM_TOP_M = 1.0e5
H_GEO_M = 3.5786e7
H_LEO_M = 5.0e5


@pytest.fixture
def wl() -> np.ndarray:
    return np.linspace(3.5, 5.0, 60)


def _params(sensor_alt_m: float, model: str = "simple") -> ParameterSet:
    ps = ParameterSet(list(GEO_PARAMS + ATMO_PARAMS))
    ps.set("geometry.sensor_altitude_m", sensor_alt_m)
    ps.set("atmosphere.model", model)
    ps.resolve()
    return ps


def _state(wl: np.ndarray, los: LineOfSightGeometry, h_tgt_m: float) -> ChainState:
    """ChainState carrying the Option C descriptor triple for *los*."""
    epsilon = SpectralData(
        name="target.epsilon",
        wavelength_um=wl,
        values=np.full_like(wl, 0.95),
        unit="",
        source="test",
    )
    target = T1Thermal(
        T_t=300.0,
        epsilon=epsilon,
        scene_type="point_source",
        target_location="airborne",
        h_tgt=h_tgt_m,
    )
    state = ChainState(wavelength_um=wl)
    state = state.with_stage_output("source", "target", target)
    state = state.with_stage_output("source", "background", None)
    return state.with_stage_output("source", "los_geometry", los)


class TestStageEntryRejection:
    """The refusal is early, actionable, and names the pending capability."""

    @pytest.mark.level1
    def test_uplooking_through_atmosphere_raises(self, wl: np.ndarray) -> None:
        """Ground sensor, 10 km airborne target: the classic A1 up-path."""
        los = LineOfSightGeometry(
            h_tgt=10_000.0,
            h_sensor=0.0,
            theta_o=math.pi,  # target straight overhead ⇒ sensor straight below
            h_atm_top=H_ATM_TOP_M,
        )
        with pytest.raises(ParameterBoundsError) as exc:
            AtmosphereStage().run(_state(wl, los, 10_000.0), _params(0.0))
        message = str(exc.value)
        assert "up-looking/level atmospheric path" in message
        assert "Phase 2" in message
        assert "Gaps 108/109" in message
        # Rule 15: it must NOT be the backend's zenith-ceiling message.
        assert "ZENITH_CEILING" not in message
        assert "out of the supported range" not in message

    @pytest.mark.level1
    def test_level_path_raises(self, wl: np.ndarray) -> None:
        """Equal altitudes (the A5 horizontal arm) are Phase 2 as well."""
        # Two aircraft at 8 km, 40 km apart: theta_o = π/2 + φ/2 (each sees
        # the other slightly below its own horizontal).
        phi = 40_000.0 / 6.371e6
        los = LineOfSightGeometry(
            h_tgt=8_000.0,
            h_sensor=8_000.0,
            theta_o=math.pi / 2.0 + phi / 2.0,
            h_atm_top=H_ATM_TOP_M,
        )
        with pytest.raises(ParameterBoundsError, match="up-looking/level atmospheric path"):
            AtmosphereStage().run(_state(wl, los, 8_000.0), _params(8_000.0))

    @pytest.mark.level1
    def test_downlooking_path_is_untouched(self, wl: np.ndarray) -> None:
        """The guard is inert for every existing (down-looking) scene."""
        los = LineOfSightGeometry(
            h_tgt=0.0,
            h_sensor=8_000.0,
            theta_o=0.0,
            h_atm_top=H_ATM_TOP_M,
        )
        out = AtmosphereStage().run(_state(wl, los, 0.0), _params(8_000.0))
        assert "at_aperture" in out.frames

    @pytest.mark.level1
    def test_uplooking_exo_target_from_inside_atmosphere_raises(self, wl: np.ndarray) -> None:
        """Ground → satellite (SST) still traverses the column: Phase 2.

        The target is exo, so the target *leg* is not vacuum end-to-end —
        the sensor sits under 100 km of air.  Serving it through the
        exo-target vacuum identities would silently drop that column.
        """
        los = LineOfSightGeometry(
            h_tgt=H_GEO_M,
            h_sensor=0.0,
            theta_o=math.pi,
            h_atm_top=H_ATM_TOP_M,
        )
        with pytest.raises(ParameterBoundsError, match="up-looking/level atmospheric path"):
            AtmosphereStage().run(_state(wl, los, H_GEO_M), _params(0.0))


class TestLeoToGeoVacuumPath:
    """Phase 1 quick win: up-looking space-to-space runs end-to-end."""

    @pytest.fixture
    def leo_to_geo_los(self) -> LineOfSightGeometry:
        """LEO sensor directly beneath a GEO target — theta_o = π exactly."""
        return LineOfSightGeometry(
            h_tgt=H_GEO_M,
            h_sensor=H_LEO_M,
            theta_o=math.pi,
            h_atm_top=H_ATM_TOP_M,
        )

    @pytest.mark.level0
    def test_wrapper_returns_exact_vacuum_bundle(
        self, wl: np.ndarray, leo_to_geo_los: LineOfSightGeometry
    ) -> None:
        """τ ≡ 1, L_path ≡ 0, E_sky ≡ 0 on **both** branches [exact].

        Both endpoints are above the column and the LOS continues into
        space, so the background branch is vacuum too — unlike the
        down-looking exo-target case, which keeps the ground→sensor column
        behind the target.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)  # no degradation warnings
            q = evaluate_with_exo_target(
                SimpleAtmosphere(standard_atmosphere="midlat_summer"),
                wl,
                leo_to_geo_los,
                _params(H_LEO_M),
            )
        np.testing.assert_array_equal(q.tau_up, np.ones_like(wl))
        np.testing.assert_array_equal(q.tau_sun, np.ones_like(wl))
        np.testing.assert_array_equal(q.tau_full_up, np.ones_like(wl))
        np.testing.assert_array_equal(q.L_path_up, np.zeros_like(wl))
        np.testing.assert_array_equal(q.L_path_full, np.zeros_like(wl))
        np.testing.assert_array_equal(q.E_sky_scattered, np.zeros_like(wl))
        np.testing.assert_array_equal(q.E_sky_thermal, np.zeros_like(wl))
        assert np.any(q.E_TOA > 0.0), "E_TOA must still be the core solar irradiance"

    @pytest.mark.level1
    def test_stage_runs_the_quick_win(
        self, wl: np.ndarray, leo_to_geo_los: LineOfSightGeometry
    ) -> None:
        """AtmosphereStage serves the up-looking space-to-space scene."""
        out = AtmosphereStage().run(
            _state(wl, leo_to_geo_los, H_GEO_M),
            _params(H_LEO_M),
        )
        assert "at_aperture" in out.frames
        tau = out.stage_outputs["atmosphere"]["tau_atm"]
        np.testing.assert_array_equal(tau, np.ones_like(wl))

    @pytest.mark.level1
    def test_obtuse_theta_o_short_of_vertical_also_runs(self, wl: np.ndarray) -> None:
        """The quick win is not limited to the exactly-vertical case."""
        los = LineOfSightGeometry(
            h_tgt=H_GEO_M,
            h_sensor=H_LEO_M,
            theta_o=math.radians(179.0),
            h_atm_top=H_ATM_TOP_M,
        )
        out = AtmosphereStage().run(_state(wl, los, H_GEO_M), _params(H_LEO_M))
        np.testing.assert_array_equal(out.stage_outputs["atmosphere"]["tau_atm"], np.ones_like(wl))

    @pytest.mark.level1
    def test_downlooking_exo_target_keeps_the_full_column(self, wl: np.ndarray) -> None:
        """Regression: the down-looking exo branch is unchanged (Gap 95).

        Sensor above the exo target ⇒ the LOS continues past it to the
        ground, so the background branch must still carry a real column.
        """
        los = LineOfSightGeometry(
            h_tgt=150_000.0,
            h_sensor=800_000.0,
            theta_o=0.0,
            h_atm_top=H_ATM_TOP_M,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            q = evaluate_with_exo_target(
                SimpleAtmosphere(standard_atmosphere="midlat_summer"),
                wl,
                los,
                _params(800_000.0),
            )
        np.testing.assert_array_equal(q.tau_up, np.ones_like(wl))
        assert float(q.tau_full_up.min()) < 1.0, (
            "the down-looking exo branch must retain the ground→sensor column"
        )
