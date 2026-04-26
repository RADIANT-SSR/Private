"""Tests for ReadoutStage MTF product path — TDI misalignment MTF term.

Validates that ReadoutStage computes TDI cross-scan misalignment MTF
for both x and y axes and stores them in ChainState.mtf_terms.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.noise_budget import NoiseBudget
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.detector._schema import ALL_PARAMETERS as DET_PARAMS
from radiant.optics._schema import ALL_PARAMETERS as OPT_PARAMS
from radiant.readout._schema import ALL_PARAMETERS as RO_PARAMS
from radiant.readout.stage import ReadoutStage
from radiant.readout.tdi_mtf import tdi_misalign_m, tdi_misalign_mtf_1d
from radiant.spectral_integration._schema import ALL_PARAMETERS as SI_PARAMS


def _make_state(
    wl: np.ndarray,
    signal_e: float = 10000.0,
    pixel_pitch_m: float = 18e-6,
    focal_length_m: float = 1.2,
) -> ChainState:
    """Build a ChainState with detector outputs pre-loaded."""
    state = ChainState(wavelength_um=wl)
    frame = RadiometricFrame(
        name="photoelectrons",
        wavelength_um=wl,
        in_band_value=signal_e,
        in_band_unit="e-",
    )
    state = state.with_frame(frame)
    state = state.with_stage_output("spectral_integration", "signal_e", signal_e)
    state = state.with_stage_output("spectral_integration", "background_e", 0.0)
    state = state.with_stage_output("spectral_integration", "nearfield_e", 0.0)
    state = state.with_stage_output("spectral_integration", "stray_e", 0.0)
    state = state.with_stage_output("spectral_integration", "contrast_e", 0.0)

    # Provide a minimal raw noise budget so DetectorStage isn't needed.
    budget = NoiseBudget(
        terms={"signal_shot": 100.0, "read_noise": 20.0},
        sigma_temporal_e=102.0,
        sigma_spatial_e=0.0,
    )
    state = state.with_stage_output("detector", "signal_e", signal_e)
    state = state.with_stage_output("detector", "noise_budget_raw", budget)
    state = state.with_stage_output("detector", "dark_e", 0.0)
    state = state.with_stage_output("detector", "glow_e", 0.0)

    # Set frequency grid.
    f_ny = 1.0 / (2.0 * pixel_pitch_m)
    freq_m = np.linspace(0, f_ny, 200)
    freq_mrad = freq_m * focal_length_m * 1e3
    return state.with_spatial_freq(freq_mrad)


def _make_params(
    misalign_pix: float = 0.0,
    pitch: float = 18.0,
    focal_length_m: float = 1.2,
) -> ParameterSet:
    from radiant.api._param_registry import _FNUMBER_GROUP

    schema = list(DET_PARAMS) + list(SI_PARAMS) + list(RO_PARAMS) + list(OPT_PARAMS)
    ps = ParameterSet(schema, [_FNUMBER_GROUP])
    ps.set("detector.qe_value", 0.7)
    ps.set("detector.pixel_pitch_x_um", pitch)
    ps.set("detector.pixel_pitch_y_um", pitch)
    ps.set("spectral_integration.integration_time_s", 0.005)
    ps.set("spectral_integration.filter_min_um", 3.5)
    ps.set("spectral_integration.filter_max_um", 5.0)
    ps.set("optics.focal_length_m", focal_length_m)
    ps.set("optics.aperture_diameter_m", 0.3)
    ps.set("readout.tdi_misalign_pixels", misalign_pix)
    ps.resolve()
    return ps


@pytest.fixture()
def wl() -> np.ndarray:
    return np.linspace(3.5, 5.0, 50)


class TestTDIMisalignMTF:
    """TDI misalignment affects cross-scan (x) only; y = unity."""

    @pytest.mark.level1
    def test_nonzero_misalign_x_matches_analytic(self, wl: np.ndarray) -> None:
        misalign_pix = 0.1
        pitch = 18.0
        pitch_m = pitch * 1e-6
        f_m = 1.2
        state = _make_state(wl, pixel_pitch_m=pitch_m, focal_length_m=f_m)
        params = _make_params(misalign_pix=misalign_pix, pitch=pitch, focal_length_m=f_m)
        out = ReadoutStage().run(state, params)

        freq_mrad = out.spatial_freq_cycles_per_mrad
        freq_m = freq_mrad / (f_m * 1e3)
        m = tdi_misalign_m(misalign_pix, pitch_m)
        expected_x = tdi_misalign_mtf_1d(freq_m, m)

        np.testing.assert_allclose(out.mtf_terms["mtf_tdi_x"], expected_x, atol=1e-12)

    @pytest.mark.level1
    def test_nonzero_misalign_y_is_unity(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        params = _make_params(misalign_pix=0.1)
        out = ReadoutStage().run(state, params)

        freq_mrad = out.spatial_freq_cycles_per_mrad
        np.testing.assert_array_equal(out.mtf_terms["mtf_tdi_y"], np.ones(len(freq_mrad)))

    @pytest.mark.level1
    def test_zero_misalign_all_unity(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        params = _make_params(misalign_pix=0.0)
        out = ReadoutStage().run(state, params)

        freq_mrad = out.spatial_freq_cycles_per_mrad
        ones = np.ones(len(freq_mrad))
        np.testing.assert_array_equal(out.mtf_terms["mtf_tdi_x"], ones)
        np.testing.assert_array_equal(out.mtf_terms["mtf_tdi_y"], ones)
