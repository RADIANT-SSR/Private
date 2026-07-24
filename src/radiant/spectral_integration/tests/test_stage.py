"""Tests for SpectralIntegrationStage wrapper."""

from __future__ import annotations

import types

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.detector._schema import ALL_PARAMETERS as DET_PARAMS
from radiant.spectral_integration._schema import ALL_PARAMETERS as SI_PARAMS
from radiant.spectral_integration.stage import SpectralIntegrationStage


def _make_state(wl: np.ndarray, L: float = 1.0) -> ChainState:
    """ChainState with post_optics frame and optics stage outputs."""
    state = ChainState(wavelength_um=wl)
    frame = RadiometricFrame(
        name="post_optics",
        wavelength_um=wl,
        spectral_radiance=np.full_like(wl, L),
    )
    state = state.with_frame(frame)
    state = state.with_stage_output("optics", "A_collect", 0.07)
    state = state.with_stage_output("optics", "Omega_pixel", 2.25e-10)
    state = state.with_stage_output("optics", "EE_box", 1.0)
    return state.with_stage_output("optics", "regime", "extended")


def _make_point_source_state(wl: np.ndarray, ee_box: float) -> ChainState:
    """Point-source ChainState with the given EE_box (audit B1-5)."""
    state = ChainState(wavelength_um=wl)
    state = state.with_frame(
        RadiometricFrame(name="post_optics", wavelength_um=wl, spectral_radiance=np.full_like(wl, 2.0))
    )
    state = state.with_frame(
        RadiometricFrame(
            name="at_aperture_target", wavelength_um=wl, spectral_radiance=np.full_like(wl, 2.0)
        )
    )
    state = state.with_stage_output("optics", "A_collect", 0.07)
    state = state.with_stage_output("optics", "Omega_pixel", 2.25e-10)
    state = state.with_stage_output("optics", "tau_opt", 0.8)
    state = state.with_stage_output("optics", "EE_box", ee_box)
    state = state.with_stage_output("optics", "regime", "point_source")
    state = state.with_stage_output("source", "projected_area_m2", 1.0)
    state = state.with_stage_output("source", "range_m", 500e3)
    return state.with_stage_output("atmosphere", "L_path", np.zeros_like(wl))


def _make_sub_pixel_state(wl: np.ndarray, ee_box: float, fill_fraction: float = 0.3) -> ChainState:
    """Sub-pixel ChainState with target + background frames (audit B1-5)."""
    state = ChainState(wavelength_um=wl)
    state = state.with_frame(
        RadiometricFrame(name="post_optics", wavelength_um=wl, spectral_radiance=np.full_like(wl, 2.0))
    )
    state = state.with_frame(
        RadiometricFrame(
            name="at_aperture_target", wavelength_um=wl, spectral_radiance=np.full_like(wl, 3.0)
        )
    )
    state = state.with_frame(
        RadiometricFrame(
            name="at_aperture_background", wavelength_um=wl, spectral_radiance=np.full_like(wl, 1.5)
        )
    )
    state = state.with_stage_output("optics", "A_collect", 0.07)
    state = state.with_stage_output("optics", "Omega_pixel", 2.25e-10)
    state = state.with_stage_output("optics", "tau_opt", 0.8)
    state = state.with_stage_output("optics", "EE_box", ee_box)
    state = state.with_stage_output("optics", "regime", "sub_pixel")
    state = state.with_stage_output("source", "fill_fraction", fill_fraction)
    state = state.with_stage_output("atmosphere", "L_path", np.zeros_like(wl))
    return state.with_stage_output(
        "atmosphere", "atm_quantities", types.SimpleNamespace(L_path_full=np.zeros_like(wl))
    )


def _make_params(
    lam_min: float = 3.5,
    lam_max: float = 5.0,
    t_int: float = 0.005,
    qe: float = 0.7,
) -> ParameterSet:
    schema = list(SI_PARAMS) + list(DET_PARAMS)
    ps = ParameterSet(schema)
    ps.set("spectral_integration.filter_min_um", lam_min)
    ps.set("spectral_integration.filter_max_um", lam_max)
    ps.set("spectral_integration.integration_time_s", t_int)
    ps.set("detector.qe_value", qe)
    ps.set("detector.pixel_pitch_x_um", 18.0)
    ps.set("detector.pixel_pitch_y_um", 18.0)
    ps.resolve()
    return ps


class TestSpectralIntegrationStage:
    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 200)

    @pytest.mark.level1
    def test_produces_photoelectrons_frame(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        out = SpectralIntegrationStage().run(state, _make_params())
        assert "photoelectrons" in out.frames
        pe = out.frames["photoelectrons"]
        assert pe.in_band_value is not None
        assert pe.in_band_value > 0.0

    @pytest.mark.level1
    def test_signal_scales_with_t_int(self, wl: np.ndarray) -> None:
        state = _make_state(wl, L=1.0)
        out1 = SpectralIntegrationStage().run(state, _make_params(t_int=0.005))
        out2 = SpectralIntegrationStage().run(state, _make_params(t_int=0.010))
        pe1 = out1.frames["photoelectrons"].in_band_value
        pe2 = out2.frames["photoelectrons"].in_band_value
        assert pe1 is not None and pe2 is not None
        assert pe2 == pytest.approx(pe1 * 2.0, rel=1e-6)

    @pytest.mark.level1
    def test_signal_scales_with_qe(self, wl: np.ndarray) -> None:
        state = _make_state(wl, L=1.0)
        out1 = SpectralIntegrationStage().run(state, _make_params(qe=0.35))
        out2 = SpectralIntegrationStage().run(state, _make_params(qe=0.70))
        pe1 = out1.frames["photoelectrons"].in_band_value
        pe2 = out2.frames["photoelectrons"].in_band_value
        assert pe1 is not None and pe2 is not None
        assert pe2 == pytest.approx(pe1 * 2.0, rel=1e-3)

    @pytest.mark.level1
    def test_EE_box_not_applied_extended(self, wl: np.ndarray) -> None:
        """In extended regime, EE_box = 1.0 must not be applied. If it
        were != 1 in extended regime, the stage raises (programming error)."""
        state = _make_state(wl)
        # Manually set EE_box != 1 with extended regime should raise.
        state2 = state.with_stage_output("optics", "EE_box", 0.8)
        with pytest.raises(RuntimeError, match="EE_box != 1.0"):
            SpectralIntegrationStage().run(state2, _make_params())

    @pytest.mark.level1
    def test_EE_box_applied_once_point_source(self, wl: np.ndarray) -> None:
        """Rule 9 positive path (audit B1-5): point-source signal ∝ EE_box.

        EE_box=0.5 must give exactly half the EE_box=1.0 signal (applied once,
        multiplicatively). The prior suite only tested the extended-regime
        guard, never that the positive path applies EE_box exactly once.
        """
        full = SpectralIntegrationStage().run(
            _make_point_source_state(wl, 1.0), _make_params()
        )
        half = SpectralIntegrationStage().run(
            _make_point_source_state(wl, 0.5), _make_params()
        )
        s_full = full.frames["photoelectrons"].in_band_value
        s_half = half.frames["photoelectrons"].in_band_value
        assert s_full is not None and s_half is not None
        assert s_half == pytest.approx(0.5 * s_full, rel=1e-12)

    @pytest.mark.level1
    def test_EE_box_exempts_background_sub_pixel(self, wl: np.ndarray) -> None:
        """Rule 9 (audit B1-5): in sub-pixel regime EE_box scales only the
        target (fill-fraction) term; the background/path pedestal is exempt.

        Consequence: signal is affine in EE_box (target part linear, background
        part constant), so equal EE_box steps give equal signal steps, and at
        EE_box=0 a positive background-only signal remains.
        """
        s0 = SpectralIntegrationStage().run(
            _make_sub_pixel_state(wl, 0.0), _make_params()
        ).frames["photoelectrons"].in_band_value
        s5 = SpectralIntegrationStage().run(
            _make_sub_pixel_state(wl, 0.5), _make_params()
        ).frames["photoelectrons"].in_band_value
        s10 = SpectralIntegrationStage().run(
            _make_sub_pixel_state(wl, 1.0), _make_params()
        ).frames["photoelectrons"].in_band_value
        assert s0 is not None and s5 is not None and s10 is not None
        assert s0 > 0.0  # background + path pedestal survives EE_box=0
        assert (s10 - s5) == pytest.approx(s5 - s0, rel=1e-9)  # affine in EE_box

    @pytest.mark.level1
    def test_hand_calculated_flat_source(self, wl: np.ndarray) -> None:
        """Verify against a hand calculation for a flat source.

        L = 1.0 W/m²/sr/µm, A = 0.07 m², Ω = 2.25e-10 sr,
        QE = 1.0, t_int = 1.0 s.

        e_rate(λ) = L · A · Ω · (λ_m / hc) · QE
        For λ = 4.0 µm → λ_m = 4e-6 m:
            e_rate = 1.0 * 0.07 * 2.25e-10 * (4e-6 / 1.9864e-25) * 1.0
                   = 0.07 * 2.25e-10 * 2.014e19
                   = 0.07 * 4.531e9 = 3.17e8 e-/s/µm

        Integrated over 1.5 µm bandwidth: ∫ ≈ 5.05e8 e-/s.
        With t_int = 1 s: ~5.05e8 e-.
        """
        state = _make_state(wl, L=1.0)
        params = _make_params(lam_min=3.5, lam_max=5.0, t_int=1.0, qe=1.0)
        out = SpectralIntegrationStage().run(state, params)
        pe = out.frames["photoelectrons"].in_band_value
        assert pe is not None
        # Verify to within 1% of the trapezoidal hand calculation.
        assert pe == pytest.approx(5.05e8, rel=0.01)

    @pytest.mark.level1
    def test_name(self) -> None:
        assert SpectralIntegrationStage().name == "spectral_integration"
