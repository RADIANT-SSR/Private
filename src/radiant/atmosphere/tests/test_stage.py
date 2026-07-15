"""Tests for AtmosphereStage wrapper (Stage 4 Option C)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere._schema import ALL_PARAMETERS as ATMO_PARAMS
from radiant.atmosphere.stage import AtmosphereStage
from radiant.core.chain import ChainState
from radiant.core.descriptors import T1Thermal
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet
from radiant.core.spectral import SpectralData
from radiant.geometry._schema import ALL_PARAMETERS as GEO_PARAMS


def _make_state_with_descriptors(
    wl: np.ndarray,
    target_T: float = 300.0,
    target_eps: float = 0.95,
) -> ChainState:
    """Create a ChainState with Option C descriptors published under ``source``.

    Stage 4 no longer reads an ``at_target`` frame — AtmosphereStage now
    consumes the ``TargetDescriptor`` / ``BackgroundDescriptor`` /
    ``LineOfSightGeometry`` triple that SourceStage publishes.
    """
    state = ChainState(wavelength_um=wl)
    epsilon = SpectralData(
        name="target.epsilon",
        wavelength_um=wl,
        values=np.full_like(wl, target_eps),
        unit="",
        source="test",
    )
    target = T1Thermal(
        T_t=target_T,
        epsilon=epsilon,
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
    )
    los = LineOfSightGeometry(
        h_tgt=0.0,
        theta_o=0.0,
        theta_s=math.radians(30.0),
        delta_phi=0.0,
    )
    state = state.with_stage_output("source", "target", target)
    state = state.with_stage_output("source", "background", None)
    return state.with_stage_output("source", "los_geometry", los)


def _make_params(
    sensor_alt_m: float = 8000.0,
    model: str = "simple",
) -> ParameterSet:
    ps = ParameterSet(list(GEO_PARAMS + ATMO_PARAMS))
    ps.set("geometry.sensor_altitude_m", sensor_alt_m)
    ps.set("atmosphere.model", model)
    ps.resolve()
    return ps


class TestAtmosphereStage:
    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 100)

    @pytest.mark.level1
    def test_produces_at_aperture_frame(self, wl: np.ndarray) -> None:
        state = _make_state_with_descriptors(wl)
        out = AtmosphereStage().run(state, _make_params())
        assert "at_aperture" in out.frames
        L = out.frames["at_aperture"].spectral_radiance
        assert L is not None
        assert L.shape == wl.shape

    @pytest.mark.level1
    def test_produces_at_aperture_target_frame(self, wl: np.ndarray) -> None:
        state = _make_state_with_descriptors(wl)
        out = AtmosphereStage().run(state, _make_params())
        assert "at_aperture_target" in out.frames
        L = out.frames["at_aperture_target"].spectral_radiance
        assert L is not None
        assert L.shape == wl.shape
        # Canonical at_aperture and at_aperture_target share the target
        # arm's L(λ) by construction (Stage 4 alias).
        np.testing.assert_array_equal(
            out.frames["at_aperture"].spectral_radiance,
            L,
        )

    @pytest.mark.level1
    def test_tau_stashed(self, wl: np.ndarray) -> None:
        state = _make_state_with_descriptors(wl)
        out = AtmosphereStage().run(state, _make_params())
        tau = out.stage_outputs["atmosphere"]["tau_atm"]
        assert tau.shape == wl.shape
        assert np.all(tau >= 0.0)
        assert np.all(tau <= 1.0)

    @pytest.mark.level1
    def test_L_path_stashed(self, wl: np.ndarray) -> None:
        state = _make_state_with_descriptors(wl)
        out = AtmosphereStage().run(state, _make_params())
        lp = out.stage_outputs["atmosphere"]["L_path"]
        assert lp.shape == wl.shape
        assert np.all(np.isfinite(lp))

    @pytest.mark.level1
    def test_atm_quantities_stashed(self, wl: np.ndarray) -> None:
        state = _make_state_with_descriptors(wl)
        out = AtmosphereStage().run(state, _make_params())
        atm_q = out.stage_outputs["atmosphere"]["atm_quantities"]
        assert atm_q.tau_up.shape == wl.shape
        assert atm_q.L_path_up.shape == wl.shape
        assert atm_q.L_path_full.shape == wl.shape

    @pytest.mark.level1
    def test_exo_model(self, wl: np.ndarray) -> None:
        state = _make_state_with_descriptors(wl)
        out = AtmosphereStage().run(state, _make_params(model="exo"))
        tau = out.stage_outputs["atmosphere"]["tau_atm"]
        np.testing.assert_allclose(tau, 1.0, atol=1e-15)
        L = out.frames["at_aperture"].spectral_radiance
        assert L is not None
        # For exo, τ ≡ 1 and L_path ≡ 0, so the at_aperture frame is
        # identically ε·B(T_t).
        assert np.all(L >= 0.0)

    @pytest.mark.level1
    def test_name(self) -> None:
        assert AtmosphereStage().name == "atmosphere"

    @pytest.mark.level1
    def test_requires_target_descriptor(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)  # no descriptors
        with pytest.raises(ValueError, match="TargetDescriptor"):
            AtmosphereStage().run(state, _make_params())


class TestSourceEmissionFrame:
    """Gap 91 — pre-atmosphere source-emission frames (target + background)."""

    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 100)

    @pytest.mark.level1
    def test_persists_at_source_target_frame(self, wl: np.ndarray) -> None:
        state = _make_state_with_descriptors(wl)
        out = AtmosphereStage().run(state, _make_params())
        assert "at_source_target" in out.frames
        L_src = out.frames["at_source_target"].spectral_radiance
        assert L_src is not None
        assert L_src.shape == wl.shape
        assert np.all(np.isfinite(L_src))
        assert np.all(L_src >= 0.0)

    @pytest.mark.level1
    def test_source_emission_equals_graybody_planck(self, wl: np.ndarray) -> None:
        """Truth anchor: a T1 graybody (ρ=0) emits ε·B(λ, T_t) at the source.

        Compared against an INDEPENDENT Planck evaluation built from the
        CODATA constants in ``radiant.core.constants`` — not the assembly's
        own ``planck_spectral_radiance`` — to anchor the persisted frame.
        """
        from radiant.core.constants import c, h, k_B

        T_t, eps = 305.0, 0.9
        state = _make_state_with_descriptors(wl, target_T=T_t, target_eps=eps)
        out = AtmosphereStage().run(state, _make_params())
        L_src = out.frames["at_source_target"].spectral_radiance
        assert L_src is not None

        # Independent Planck spectral radiance in W/m²/sr/µm.
        lam_m = wl * 1e-6
        planck_si = (2.0 * h * c**2 / lam_m**5) / (np.exp(h * c / (lam_m * k_B * T_t)) - 1.0)
        planck_per_um = planck_si * 1e-6  # per-metre → per-µm
        expected = eps * planck_per_um
        np.testing.assert_allclose(L_src, expected, rtol=1e-9)

    @pytest.mark.level1
    def test_at_aperture_consistency(self, wl: np.ndarray) -> None:
        """at_aperture_target ≈ τ_up · at_source_target + L_path_up.

        Proves the persisted frame IS the physical L_source the at-aperture
        assembly consumes.
        """
        state = _make_state_with_descriptors(wl)
        out = AtmosphereStage().run(state, _make_params())
        L_src = out.frames["at_source_target"].spectral_radiance
        L_ap = out.frames["at_aperture_target"].spectral_radiance
        tau = out.stage_outputs["atmosphere"]["tau_atm"]
        l_path = out.stage_outputs["atmosphere"]["L_path"]
        assert L_src is not None and L_ap is not None
        np.testing.assert_allclose(tau * L_src + l_path, L_ap, rtol=1e-9, atol=1e-12)

    @pytest.mark.level1
    def test_no_background_omits_source_background_frame(self, wl: np.ndarray) -> None:
        state = _make_state_with_descriptors(wl)  # background=None
        out = AtmosphereStage().run(state, _make_params())
        assert "at_source_background" not in out.frames

    @pytest.mark.level1
    def test_background_source_frame_and_consistency(self, wl: np.ndarray) -> None:
        from radiant.core.descriptors import GroundBackground

        state = _make_state_with_descriptors(wl)
        eps_g = SpectralData(
            name="background.epsilon_g",
            wavelength_um=wl,
            values=np.full_like(wl, 0.98),
            unit="",
            source="test",
        )
        bg = GroundBackground(epsilon_g=eps_g, T_g=290.0)
        state = state.with_stage_output("source", "background", bg)
        out = AtmosphereStage().run(state, _make_params())

        assert "at_source_background" in out.frames
        L_src_bg = out.frames["at_source_background"].spectral_radiance
        L_ap_bg = out.frames["at_aperture_background"].spectral_radiance
        atm_q = out.stage_outputs["atmosphere"]["atm_quantities"]
        assert L_src_bg is not None and L_ap_bg is not None
        # GroundBackground propagates through the full ground→sensor column.
        np.testing.assert_allclose(
            atm_q.tau_full_up * L_src_bg + atm_q.L_path_full,
            L_ap_bg,
            rtol=1e-9,
            atol=1e-12,
        )
