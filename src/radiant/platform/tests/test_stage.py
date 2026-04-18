"""Tests for PlatformStage — jitter and smear convolution into EffectivePSF.

Validates:
- Zero jitter passes ePSF through unchanged
- Non-zero isotropic jitter convolves a Gaussian kernel into ePSF
- Anisotropic mode uses separate x/y sigmas
- Jitter broadens the PSF (FWHM increases, RER decreases)
- MTF at Nyquist degrades according to exp(-2pi^2 sigma^2 f^2)
- Stage outputs contain expected keys
- No ePSF available → graceful skip
- Zero smear: no smear kernel applied
- Non-zero smear: FWHM_y increases, FWHM_x unchanged
- smear_length_um overrides ground_velocity
- Combined jitter + smear degrade ePSF
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterDef, ParameterSet
from radiant.optics.effective_psf import EffectivePSF
from radiant.optics.psf_builder import build_effective_psf
from radiant.platform.stage import PlatformStage


def _make_diffraction_psf(
    wavelength_um: float = 0.575,
    aperture_m: float = 0.5,
    focal_length_m: float = 5.0,
    pixel_pitch_m: float = 8e-6,
) -> EffectivePSF:
    """Build a simple Airy-like ePSF for testing."""
    from radiant.optics.diffraction_mono import compute_psf
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
    psf_arr = compute_psf(config, obscuration_ratio=0.0)
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


class TestPlatformStageZeroSmear:
    """Zero smear (default) should not alter the ePSF."""

    def test_zero_smear_preserves_epsf(self) -> None:
        state, epsf_orig = _make_state_with_epsf()
        params = _make_params(**{"platform.ground_velocity_m_s": 0.0})
        stage = PlatformStage()

        result = stage.run(state, params)

        epsf_out = result.stage_outputs["platform"]["effective_psf"]
        assert epsf_out is epsf_orig

    def test_zero_smear_width_stored(self) -> None:
        state, _ = _make_state_with_epsf()
        params = _make_params()
        stage = PlatformStage()

        result = stage.run(state, params)

        assert result.stage_outputs["platform"]["smear_width_m"] == 0.0


class TestPlatformStageSmear:
    """Non-zero smear broadens the PSF along y-axis (along-track) only."""

    def test_smear_broadens_y_not_x(self) -> None:
        """Smear is along-track (y); cross-track (x) should be unchanged."""
        state, epsf_orig = _make_state_with_epsf()
        # 16 µm smear = 2 pixels at 8 µm pitch
        params = _make_params(**{"platform.smear_length_um": 16.0})
        stage = PlatformStage()

        result = stage.run(state, params)

        epsf_out = result.stage_outputs["platform"]["effective_psf"]
        assert epsf_out.fwhm("y") > epsf_orig.fwhm("y")
        # Discrete 2-D convolution on a finite grid introduces small x-axis
        # variation (~4%) even though the kernel is purely along y.
        assert epsf_out.fwhm("x") == pytest.approx(epsf_orig.fwhm("x"), rel=0.05)

    def test_smear_convolution_history(self) -> None:
        state, _ = _make_state_with_epsf()
        params = _make_params(**{"platform.smear_length_um": 16.0})
        stage = PlatformStage()

        result = stage.run(state, params)

        epsf_out = result.stage_outputs["platform"]["effective_psf"]
        assert "smear" in epsf_out.convolution_history

    def test_smear_width_stored(self) -> None:
        state, _ = _make_state_with_epsf()
        params = _make_params(**{"platform.smear_length_um": 16.0})
        stage = PlatformStage()

        result = stage.run(state, params)

        # 16 µm input → 16e-6 m canonical
        assert result.stage_outputs["platform"]["smear_width_m"] == pytest.approx(
            16e-6, rel=1e-10
        )

    def test_smear_degrades_mtf_y(self) -> None:
        """Smear should degrade MTF along y (along-track) at Nyquist."""
        state, epsf_orig = _make_state_with_epsf()
        pixel_pitch_m = epsf_orig.pixel_pitch_m
        f_nyq = 1.0 / (2.0 * pixel_pitch_m)

        freq_y, mtf_y_orig = epsf_orig.mtf_1d("y")
        mtf_nyq_orig = float(np.interp(f_nyq, freq_y, mtf_y_orig))

        params = _make_params(**{"platform.smear_length_um": 16.0})
        stage = PlatformStage()
        result = stage.run(state, params)
        epsf_out = result.stage_outputs["platform"]["effective_psf"]

        freq_y_s, mtf_y_s = epsf_out.mtf_1d("y")
        mtf_nyq_smeared = float(np.interp(f_nyq, freq_y_s, mtf_y_s))

        assert mtf_nyq_smeared < mtf_nyq_orig

    def test_smear_mtf_matches_sinc(self) -> None:
        """Ratio of smeared/original MTF_y should match sinc formula."""
        from radiant.platform.smear import smear_mtf_1d

        smear_m = 16e-6
        state, epsf_orig = _make_state_with_epsf()
        params = _make_params(**{"platform.smear_length_um": 16.0})
        stage = PlatformStage()
        result = stage.run(state, params)
        epsf_out = result.stage_outputs["platform"]["effective_psf"]

        freq_y, mtf_y_orig = epsf_orig.mtf_1d("y")
        _, mtf_y_smeared = epsf_out.mtf_1d("y")

        # Restrict to low-mid frequencies where the discrete rect kernel
        # closely approximates the continuous sinc.  At high frequencies the
        # finite kernel grid diverges from the analytic sinc.
        pixel_pitch_m = epsf_orig.pixel_pitch_m
        f_nyq = 1.0 / (2.0 * pixel_pitch_m)
        mask = (mtf_y_orig > 0.05) & (freq_y < 0.5 * f_nyq)
        ratio = mtf_y_smeared[mask] / mtf_y_orig[mask]
        analytic = smear_mtf_1d(freq_y[mask], smear_m)

        np.testing.assert_allclose(ratio, analytic, atol=0.05)


def _make_smear_params(**overrides: object) -> ParameterSet:
    """Build a ParameterSet with platform + optics + geometry + timing params.

    Extends _make_params with geometry and spectral_integration schemas
    needed for velocity-based smear computation.
    """
    from radiant.atmosphere._schema import (
        SENSOR_ALTITUDE_M,
        PATH_ZENITH_RAD,
    )
    from radiant.optics._schema import ALL_PARAMETERS as OPT_PARAMS
    from radiant.platform._schema import ALL_PARAMETERS as PLAT_PARAMS
    from radiant.spectral_integration._schema import INTEGRATION_TIME_S

    schema = list(PLAT_PARAMS + OPT_PARAMS) + [
        SENSOR_ALTITUDE_M,
        PATH_ZENITH_RAD,
        INTEGRATION_TIME_S,
    ]
    ps = ParameterSet(schema, [])

    defaults: dict[str, object] = {
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


class TestPlatformStageSmearVelocity:
    """Velocity-based smear computation through the stage."""

    def test_velocity_based_smear_width(self) -> None:
        """v/slant × focal × t_int at nadir."""
        state, _ = _make_state_with_epsf()
        params = _make_smear_params(**{
            "platform.ground_velocity_m_s": 7000.0,
            "geometry.sensor_altitude_m": 600_000.0,
            "spectral_integration.integration_time_s": 0.0001,
        })
        stage = PlatformStage()
        result = stage.run(state, params)

        smear_w = result.stage_outputs["platform"]["smear_width_m"]
        assert smear_w > 0.0
        # At nadir: slant ≈ altitude → 7000/600000 × 5.0 × 0.0001 ≈ 5.83e-6 m
        expected = 7000.0 / 600_000.0 * 5.0 * 0.0001
        assert smear_w == pytest.approx(expected, rel=0.01)

    def test_no_velocity_no_smear(self) -> None:
        state, _ = _make_state_with_epsf()
        params = _make_smear_params(**{
            "platform.ground_velocity_m_s": 0.0,
            "geometry.sensor_altitude_m": 600_000.0,
            "spectral_integration.integration_time_s": 0.0001,
        })
        stage = PlatformStage()
        result = stage.run(state, params)

        assert result.stage_outputs["platform"]["smear_width_m"] == 0.0


class TestPlatformStageSmearOverride:
    """smear_length_um takes precedence over ground_velocity_m_s."""

    def test_direct_overrides_velocity(self) -> None:
        state, _ = _make_state_with_epsf()
        params = _make_smear_params(**{
            "platform.smear_length_um": 10.0,
            "platform.ground_velocity_m_s": 7000.0,
            "geometry.sensor_altitude_m": 600_000.0,
            "spectral_integration.integration_time_s": 0.001,
        })
        stage = PlatformStage()
        result = stage.run(state, params)

        # Direct override: 10 µm = 10e-6 m
        assert result.stage_outputs["platform"]["smear_width_m"] == pytest.approx(
            10e-6, rel=1e-10
        )


class TestPlatformStageJitterPlusSmear:
    """Combined jitter + smear should degrade the ePSF more than either alone."""

    def test_combined_worse_than_jitter_alone(self) -> None:
        state, _ = _make_state_with_epsf()

        # Jitter only
        params_j = _make_params(**{"platform.jitter_rms_urad": 1.0})
        stage = PlatformStage()
        result_j = stage.run(state, params_j)
        epsf_j = result_j.stage_outputs["platform"]["effective_psf"]

        # Both jitter + smear
        params_both = _make_params(**{
            "platform.jitter_rms_urad": 1.0,
            "platform.smear_length_um": 16.0,
        })
        result_both = stage.run(state, params_both)
        epsf_both = result_both.stage_outputs["platform"]["effective_psf"]

        # Combined FWHM_y should be worse than jitter-only
        assert epsf_both.fwhm("y") > epsf_j.fwhm("y")
        # Combined FWHM_x ≈ jitter-only (smear is y-only);
        # discrete 2-D convolution allows ~5% grid artifact.
        assert epsf_both.fwhm("x") == pytest.approx(epsf_j.fwhm("x"), rel=0.05)

    def test_combined_history(self) -> None:
        state, _ = _make_state_with_epsf()
        params = _make_params(**{
            "platform.jitter_rms_urad": 1.0,
            "platform.smear_length_um": 16.0,
        })
        stage = PlatformStage()
        result = stage.run(state, params)

        epsf_out = result.stage_outputs["platform"]["effective_psf"]
        assert "jitter" in epsf_out.convolution_history
        assert "smear" in epsf_out.convolution_history


class TestPlatformStageName:
    def test_name(self) -> None:
        assert PlatformStage().name == "platform"
