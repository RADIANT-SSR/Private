"""Gap 95: exo-altitude target (h_tgt ≥ h_atm_top) — vacuum target leg.

Level 0 for the identity substitution in
:func:`radiant.atmosphere.exo_target.evaluate_with_exo_target`: the
target→sensor leg of a target above the atmospheric column is exactly
τ_up = 1 / L_path_up = 0 / τ_sun = 1, while the ground→sensor full
column (background branch) is byte-identical to a surface-target
evaluation of the same backend.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.exo_target import evaluate_with_exo_target
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.core.los_geometry import LineOfSightGeometry

from .test_evaluate import _resolved_params


@pytest.fixture
def wl() -> np.ndarray:
    return np.linspace(8.0, 13.0, 51)


@pytest.fixture
def params(wl: np.ndarray):  # type: ignore[no-untyped-def]
    return _resolved_params(wl, sensor_altitude_m=500_000.0)


def _quiet_evaluate(model: object, wl: np.ndarray, los, params) -> AtmosphericQuantities:  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return evaluate_with_exo_target(model, wl, los, params)


class TestVacuumTargetLeg:
    @pytest.mark.level0
    def test_exo_target_identities(self, wl: np.ndarray, params) -> None:  # type: ignore[no-untyped-def]
        """h_tgt = 150 km ≥ h_atm_top = 100 km: τ_up ≡ 1, L_path_up ≡ 0,
        τ_sun ≡ 1 [all dimensionless / W/m²/sr/µm]."""
        model = SimpleAtmosphere()
        los = LineOfSightGeometry(h_tgt=150_000.0, theta_o=0.0, h_atm_top=1.0e5)
        q = _quiet_evaluate(model, wl, los, params)
        np.testing.assert_array_equal(q.tau_up, np.ones_like(wl))
        np.testing.assert_array_equal(q.tau_sun, np.ones_like(wl))
        np.testing.assert_array_equal(q.L_path_up, np.zeros_like(wl))

    @pytest.mark.level0
    def test_background_column_matches_surface_evaluation(self, wl: np.ndarray, params) -> None:  # type: ignore[no-untyped-def]
        """The full-column and sky quantities equal a surface-target run of
        the same backend — the background branch is untouched."""
        model = SimpleAtmosphere()
        exo = LineOfSightGeometry(h_tgt=150_000.0, theta_o=0.0, h_atm_top=1.0e5)
        surface = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, h_atm_top=1.0e5)
        q_exo = _quiet_evaluate(model, wl, exo, params)
        q_surf = _quiet_evaluate(model, wl, surface, params)
        np.testing.assert_array_equal(q_exo.tau_full_up, q_surf.tau_full_up)
        np.testing.assert_array_equal(q_exo.L_path_full, q_surf.L_path_full)
        np.testing.assert_array_equal(q_exo.E_sky_thermal, q_surf.E_sky_thermal)
        np.testing.assert_array_equal(q_exo.E_TOA, q_surf.E_TOA)
        # The full column really is an atmosphere, not vacuum.
        assert q_exo.tau_full_up.min() < 1.0

    @pytest.mark.level0
    def test_at_equality_boundary(self, wl: np.ndarray, params) -> None:  # type: ignore[no-untyped-def]
        """h_tgt exactly at h_atm_top takes the vacuum branch (the column
        above the target has zero extent)."""
        model = SimpleAtmosphere()
        los = LineOfSightGeometry(h_tgt=1.0e5, theta_o=0.0, h_atm_top=1.0e5)
        q = _quiet_evaluate(model, wl, los, params)
        np.testing.assert_array_equal(q.tau_up, np.ones_like(wl))

    @pytest.mark.level1
    def test_endo_target_passes_through(self, wl: np.ndarray, params) -> None:  # type: ignore[no-untyped-def]
        """Below h_atm_top the wrapper is a transparent pass-through."""
        model = SimpleAtmosphere()
        los = LineOfSightGeometry(h_tgt=5_000.0, theta_o=0.0, h_atm_top=1.0e5)
        via_wrapper = _quiet_evaluate(model, wl, los, params)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            direct = model.evaluate(wl, los, params)
        np.testing.assert_array_equal(via_wrapper.tau_up, direct.tau_up)
        np.testing.assert_array_equal(via_wrapper.L_path_up, direct.L_path_up)

    @pytest.mark.level1
    def test_single_column_backends_serve_exo_targets(
        self, wl: np.ndarray, params, tmp_path
    ) -> None:  # type: ignore[no-untyped-def]
        """A single-file tabulated import — which refuses 0 < h_tgt <
        h_atm_top — serves an exo target exactly through the wrapper."""
        from radiant.atmosphere.tabulated import TabulatedAtmosphere

        npz = tmp_path / "column.npz"
        np.savez(
            npz,
            wavelength_um=wl,
            transmittance=0.8 * np.ones_like(wl),
            path_radiance=0.05 * np.ones_like(wl),
            atm_emission_down=0.02 * np.ones_like(wl),
        )
        model = TabulatedAtmosphere.from_npz(npz)
        los = LineOfSightGeometry(h_tgt=150_000.0, theta_o=0.0, h_atm_top=1.0e5)
        q = _quiet_evaluate(model, wl, los, params)
        np.testing.assert_array_equal(q.tau_up, np.ones_like(wl))
        np.testing.assert_array_equal(q.L_path_up, np.zeros_like(wl))
        np.testing.assert_allclose(q.tau_full_up, 0.8, rtol=1e-12)
        np.testing.assert_allclose(q.L_path_full, 0.05, rtol=1e-12)


class TestLosGeometryExoTarget:
    @pytest.mark.level0
    def test_exo_h_tgt_constructs(self) -> None:
        los = LineOfSightGeometry(h_tgt=101_000.0, theta_o=0.0, h_atm_top=1.0e5)
        assert los.h_tgt == 101_000.0
        assert los.slant_range_atm == 0.0  # no column above the target [m]
        assert los.path_airmass_up == 1.0  # vacuum limit [dimensionless]

    @pytest.mark.level0
    def test_negative_h_tgt_still_rejected(self) -> None:
        from radiant.core.parameters import ParameterBoundsError

        with pytest.raises(ParameterBoundsError, match="negative"):
            LineOfSightGeometry(h_tgt=-1.0, theta_o=0.0, h_atm_top=1.0e5)
