"""Tests for PlatformStage — jitter convolution into EffectivePSF.

Validates:
- Zero jitter passes ePSF through unchanged
- Non-zero isotropic jitter convolves a Gaussian kernel into ePSF
- Anisotropic mode uses separate x/y sigmas
- Jitter broadens the PSF (FWHM increases, RER decreases)
- MTF at Nyquist degrades according to exp(-2pi^2 sigma^2 f^2)
- Stage outputs contain expected keys
- No ePSF available → graceful skip
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterDef, ParameterSet
from radiant.optics.psf import EffectivePSF, build_effective_psf
from radiant.platform.stage import PlatformStage


def _make_diffraction_psf(
    wavelength_um: float = 0.575,
    aperture_m: float = 0.5,
    focal_length_m: float = 5.0,
    pixel_pitch_m: float = 8e-6,
) -> EffectivePSF:
    """Build a simple Airy-like ePSF for testing."""
    from radiant.optics.diffraction import compute_psf
    from radiant.optics.sampling import compute_sampling

    wavelength_m = wavelength_um * 1e-6
    config = compute_sampling(
        wavelength_m=wavelength_m,
        focal_length_m=focal_length_m,
        aperture_diameter_m=aperture_m,
        pixel_pitch_m=pixel_pitch_m,
        pupil_npix=128,
        psf_oversample=8,
    )
    psf_arr = compute_psf(config, obscuration_ratio=0.0, wfe_rms_waves=0.0)
    return build_effective_psf(
        psf_arr,
        kernels=[],
        sample_spacing_m=config.focal_spacing_m,
        pixel_pitch_m=pixel_pitch_m,
        wavelength_um=wavelength_um,
    )


def _make_params(**overrides: object) -> ParameterSet:
    """Build a minimal ParameterSet with platform + optics params."""
    from radiant.platform._schema import ALL_PARAMETERS as PLAT_PARAMS
    from radiant.optics._schema import ALL_PARAMETERS as OPT_PARAMS

    schema = list(PLAT_PARAMS + OPT_PARAMS)
    ps = ParameterSet(schema, [])

    defaults = {
        "platform.jitter_rms_urad": 0.0,
        "platform.jitter_axes": "isotropic",
        "platform.jitter_rms_x_urad": 0.0,
        "platform.jitter_rms_y_urad": 0.0,
        "optics.aperture_diameter_m": 0.5,
        "optics.focal_length_m": 5.0,
        "optics.f_number": 10.0,
    }
    defaults.update(overrides)
    for k, v in defaults.items():
        ps.set(k, v)

    ps.resolve()
    return ps


def _make_state_with_epsf() -> tuple[ChainState, EffectivePSF]:
    """Build a ChainState with an EffectivePSF in optics outputs."""
    epsf = _make_diffraction_psf()
    wl = np.array([0.45, 0.575, 0.70])
    state = ChainState(wavelength_um=wl)
    state = state.with_stage_output("optics", "effective_psf", epsf)
    return state, epsf


class TestPlatformStageZeroJitter:
    """Zero jitter should pass the ePSF through unchanged."""

    def test_zero_jitter_preserves_epsf(self) -> None:
        state, epsf_orig = _make_state_with_epsf()
        params = _make_params()
        stage = PlatformStage()

        result = stage.run(state, params)

        epsf_out = result.stage_outputs["platform"]["effective_psf"]
        assert epsf_out is epsf_orig

    def test_zero_jitter_sigma_outputs(self) -> None:
        state, _ = _make_state_with_epsf()
        params = _make_params()
        stage = PlatformStage()

        result = stage.run(state, params)

        assert result.stage_outputs["platform"]["jitter_sigma_x_m"] == 0.0
        assert result.stage_outputs["platform"]["jitter_sigma_y_m"] == 0.0


class TestPlatformStageIsotropicJitter:
    """Isotropic jitter should broaden the PSF symmetrically."""

    def test_jitter_broadens_psf(self) -> None:
        state, epsf_orig = _make_state_with_epsf()
        params = _make_params(**{"platform.jitter_rms_urad": 1.0})
        stage = PlatformStage()

        result = stage.run(state, params)

        epsf_out = result.stage_outputs["platform"]["effective_psf"]
        assert epsf_out.fwhm("x") > epsf_orig.fwhm("x")
        assert epsf_out.fwhm("y") > epsf_orig.fwhm("y")

    def test_jitter_degrades_rer(self) -> None:
        state, epsf_orig = _make_state_with_epsf()
        params = _make_params(**{"platform.jitter_rms_urad": 1.0})
        stage = PlatformStage()

        result = stage.run(state, params)

        epsf_out = result.stage_outputs["platform"]["effective_psf"]
        assert epsf_out.rer() < epsf_orig.rer()

    def test_convolution_history(self) -> None:
        state, _ = _make_state_with_epsf()
        params = _make_params(**{"platform.jitter_rms_urad": 1.0})
        stage = PlatformStage()

        result = stage.run(state, params)

        epsf_out = result.stage_outputs["platform"]["effective_psf"]
        assert "jitter" in epsf_out.convolution_history

    def test_sigma_focal_plane(self) -> None:
        """sigma_fp = jitter_rad * focal_length_m."""
        jitter_urad = 2.0
        focal_m = 5.0
        expected_sigma_m = 2.0e-6 * focal_m  # 10 µm

        state, _ = _make_state_with_epsf()
        params = _make_params(**{"platform.jitter_rms_urad": jitter_urad})
        stage = PlatformStage()

        result = stage.run(state, params)

        assert result.stage_outputs["platform"]["jitter_sigma_x_m"] == pytest.approx(
            expected_sigma_m, rel=1e-10
        )
        assert result.stage_outputs["platform"]["jitter_sigma_y_m"] == pytest.approx(
            expected_sigma_m, rel=1e-10
        )

    def test_mtf_at_nyquist_degrades(self) -> None:
        """System MTF at Nyquist should decrease with jitter."""
        state, epsf_orig = _make_state_with_epsf()
        pixel_pitch_m = epsf_orig.pixel_pitch_m
        f_nyq = 1.0 / (2.0 * pixel_pitch_m)

        freq_x, mtf_x_orig = epsf_orig.mtf_1d("x")
        mtf_nyq_orig = float(np.interp(f_nyq, freq_x, mtf_x_orig))

        params = _make_params(**{"platform.jitter_rms_urad": 1.0})
        stage = PlatformStage()
        result = stage.run(state, params)
        epsf_out = result.stage_outputs["platform"]["effective_psf"]

        freq_x_j, mtf_x_j = epsf_out.mtf_1d("x")
        mtf_nyq_jittered = float(np.interp(f_nyq, freq_x_j, mtf_x_j))

        assert mtf_nyq_jittered < mtf_nyq_orig

    def test_large_jitter_kills_mtf(self) -> None:
        """5 urad jitter on 5m focal length → 25 µm sigma (3+ pixels). MTF@Nyq ~ 0."""
        state, _ = _make_state_with_epsf()
        params = _make_params(**{"platform.jitter_rms_urad": 5.0})
        stage = PlatformStage()
        result = stage.run(state, params)

        epsf_out = result.stage_outputs["platform"]["effective_psf"]
        pixel_pitch_m = epsf_out.pixel_pitch_m
        f_nyq = 1.0 / (2.0 * pixel_pitch_m)

        freq_x, mtf_x = epsf_out.mtf_1d("x")
        mtf_nyq = float(np.interp(f_nyq, freq_x, mtf_x))

        assert mtf_nyq < 0.01


class TestPlatformStageAnisotropicJitter:
    """Anisotropic mode should use separate x/y sigmas."""

    def test_anisotropic_different_axes(self) -> None:
        state, epsf_orig = _make_state_with_epsf()
        params = _make_params(**{
            "platform.jitter_axes": "anisotropic",
            "platform.jitter_rms_x_urad": 2.0,
            "platform.jitter_rms_y_urad": 0.5,
        })
        stage = PlatformStage()
        result = stage.run(state, params)

        epsf_out = result.stage_outputs["platform"]["effective_psf"]
        # x-axis should be broader than y-axis (more jitter)
        assert epsf_out.fwhm("x") > epsf_out.fwhm("y")

    def test_anisotropic_sigma_outputs(self) -> None:
        state, _ = _make_state_with_epsf()
        params = _make_params(**{
            "platform.jitter_axes": "anisotropic",
            "platform.jitter_rms_x_urad": 3.0,
            "platform.jitter_rms_y_urad": 1.0,
        })
        stage = PlatformStage()
        result = stage.run(state, params)

        # 3 µrad × 5 m = 15 µm = 15e-6 m
        assert result.stage_outputs["platform"]["jitter_sigma_x_m"] == pytest.approx(
            15e-6, rel=1e-10
        )
        # 1 µrad × 5 m = 5 µm = 5e-6 m
        assert result.stage_outputs["platform"]["jitter_sigma_y_m"] == pytest.approx(
            5e-6, rel=1e-10
        )


class TestPlatformStageNoEpsf:
    """No ePSF from optics → graceful skip."""

    def test_no_epsf_skips_jitter(self) -> None:
        wl = np.array([0.45, 0.575, 0.70])
        state = ChainState(wavelength_um=wl)
        params = _make_params(**{"platform.jitter_rms_urad": 5.0})
        stage = PlatformStage()

        result = stage.run(state, params)

        assert "effective_psf" not in result.stage_outputs.get("platform", {})

    def test_no_epsf_stores_sigma(self) -> None:
        wl = np.array([0.45, 0.575, 0.70])
        state = ChainState(wavelength_um=wl)
        params = _make_params(**{"platform.jitter_rms_urad": 2.0})
        stage = PlatformStage()

        result = stage.run(state, params)

        assert result.stage_outputs["platform"]["jitter_sigma_x_m"] == pytest.approx(
            10e-6, rel=1e-10
        )


class TestPlatformStageName:
    def test_name(self) -> None:
        assert PlatformStage().name == "platform"
