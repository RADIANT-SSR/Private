"""Tests for DetectorStage MTF product path — pixel, IPC, diffusion MTF terms.

Validates that DetectorStage computes pixel aperture, IPC, and charge
diffusion analytic MTFs for both x and y axes and stores them in
ChainState.mtf_terms.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.detector._schema import ALL_PARAMETERS as DET_PARAMS
from radiant.detector.diffusion import diffusion_mtf_1d
from radiant.detector.ipc import ipc_mtf_1d
from radiant.detector.stage import DetectorStage
from radiant.optics._schema import ALL_PARAMETERS as OPT_PARAMS
from radiant.readout._schema import ALL_PARAMETERS as RO_PARAMS
from radiant.spectral_integration._schema import ALL_PARAMETERS as SI_PARAMS


def _make_state(
    wl: np.ndarray,
    signal_e: float = 10000.0,
    pixel_pitch_m: float = 18e-6,
    focal_length_m: float = 1.2,
) -> ChainState:
    """Build a ChainState with spectral_integration outputs and freq grid."""
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

    # Set frequency grid as OpticsStage would.
    f_ny = 1.0 / (2.0 * pixel_pitch_m)
    freq_m = np.linspace(0, f_ny, 200)
    freq_mrad = freq_m * focal_length_m * 1e3
    state = state.with_spatial_freq(freq_mrad)
    return state


def _make_params(
    pitch: float = 18.0,
    ipc_coupling: float = 0.0,
    diffusion_length_m: float = 0.0,
    focal_length_m: float = 1.2,
) -> ParameterSet:
    from radiant.api._param_registry import _FNUMBER_GROUP

    schema = list(DET_PARAMS) + list(SI_PARAMS) + list(RO_PARAMS) + list(OPT_PARAMS)
    ps = ParameterSet(schema, [_FNUMBER_GROUP])
    ps.set("detector.qe_value", 0.7)
    ps.set("detector.pixel_pitch_x_um", pitch)
    ps.set("detector.pixel_pitch_y_um", pitch)
    ps.set("detector.dark_rate_e_per_s", 100.0)
    ps.set("detector.ipc_coupling", ipc_coupling)
    ps.set("detector.charge_diffusion_length_m", diffusion_length_m)
    ps.set("spectral_integration.integration_time_s", 0.005)
    ps.set("spectral_integration.filter_min_um", 3.5)
    ps.set("spectral_integration.filter_max_um", 5.0)
    ps.set("optics.focal_length_m", focal_length_m)
    ps.set("optics.aperture_diameter_m", 0.3)
    ps.resolve()
    return ps


@pytest.fixture()
def wl() -> np.ndarray:
    return np.linspace(3.5, 5.0, 50)


class TestPixelApertureMTF:
    """Pixel aperture MTF = |sinc(f * pitch)|."""

    def test_at_nyquist_square_pixels(self, wl: np.ndarray) -> None:
        """MTF_pixel at Nyquist = sinc(0.5) = 2/π ≈ 0.6366."""
        pitch = 18.0
        pitch_m = pitch * 1e-6
        f_m = 1.2
        state = _make_state(wl, pixel_pitch_m=pitch_m, focal_length_m=f_m)
        params = _make_params(pitch=pitch, focal_length_m=f_m)
        out = DetectorStage().run(state, params)

        freq_mrad = out.spatial_freq_cycles_per_mrad
        freq_m = freq_mrad / (f_m * 1e3)
        f_ny = 1.0 / (2.0 * pitch_m)

        # Find index closest to Nyquist.
        idx_ny = np.argmin(np.abs(freq_m - f_ny))
        expected = np.abs(np.sinc(freq_m[idx_ny] * pitch_m))

        assert out.mtf_terms["mtf_pixel_aperture_x"][idx_ny] == pytest.approx(
            expected, abs=1e-10
        )
        assert out.mtf_terms["mtf_pixel_aperture_y"][idx_ny] == pytest.approx(
            expected, abs=1e-10
        )

    def test_square_pixels_x_equals_y(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        params = _make_params()
        out = DetectorStage().run(state, params)

        np.testing.assert_array_equal(
            out.mtf_terms["mtf_pixel_aperture_x"],
            out.mtf_terms["mtf_pixel_aperture_y"],
        )


class TestIPCMTF:
    """IPC MTF from analytic formula."""

    def test_ipc_coupling_matches_analytic(self, wl: np.ndarray) -> None:
        coupling = 0.03
        pitch = 18.0
        pitch_m = pitch * 1e-6
        f_m = 1.2
        state = _make_state(wl, pixel_pitch_m=pitch_m, focal_length_m=f_m)
        params = _make_params(pitch=pitch, ipc_coupling=coupling, focal_length_m=f_m)
        out = DetectorStage().run(state, params)

        freq_mrad = out.spatial_freq_cycles_per_mrad
        freq_m = freq_mrad / (f_m * 1e3)

        expected_x = ipc_mtf_1d(freq_m, coupling, pitch_m, axis="x")
        expected_y = ipc_mtf_1d(freq_m, coupling, pitch_m, axis="y")

        np.testing.assert_allclose(out.mtf_terms["mtf_ipc_x"], expected_x, atol=1e-12)
        np.testing.assert_allclose(out.mtf_terms["mtf_ipc_y"], expected_y, atol=1e-12)

    def test_zero_coupling_is_unity(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        params = _make_params(ipc_coupling=0.0)
        out = DetectorStage().run(state, params)

        freq_mrad = out.spatial_freq_cycles_per_mrad
        np.testing.assert_array_equal(out.mtf_terms["mtf_ipc_x"], np.ones(len(freq_mrad)))
        np.testing.assert_array_equal(out.mtf_terms["mtf_ipc_y"], np.ones(len(freq_mrad)))


class TestDiffusionMTF:
    """Charge diffusion MTF (isotropic: x == y)."""

    def test_diffusion_x_equals_y(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        params = _make_params(diffusion_length_m=5e-6)
        out = DetectorStage().run(state, params)

        np.testing.assert_array_equal(
            out.mtf_terms["mtf_charge_diffusion_x"],
            out.mtf_terms["mtf_charge_diffusion_y"],
        )

    def test_diffusion_matches_analytic(self, wl: np.ndarray) -> None:
        L_d = 5e-6
        f_m = 1.2
        state = _make_state(wl, focal_length_m=f_m)
        params = _make_params(diffusion_length_m=L_d, focal_length_m=f_m)
        out = DetectorStage().run(state, params)

        freq_mrad = out.spatial_freq_cycles_per_mrad
        freq_m = freq_mrad / (f_m * 1e3)

        expected = diffusion_mtf_1d(freq_m, L_d)
        np.testing.assert_allclose(
            out.mtf_terms["mtf_charge_diffusion_x"], expected, atol=1e-12
        )

    def test_zero_diffusion_is_unity(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        params = _make_params(diffusion_length_m=0.0)
        out = DetectorStage().run(state, params)

        freq_mrad = out.spatial_freq_cycles_per_mrad
        np.testing.assert_array_equal(
            out.mtf_terms["mtf_charge_diffusion_x"], np.ones(len(freq_mrad))
        )
