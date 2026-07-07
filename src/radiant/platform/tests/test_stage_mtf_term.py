"""Tests for PlatformStage MTF product path — jitter and smear MTF terms.

Validates that PlatformStage computes jitter and smear analytic MTFs
for both x and y axes and stores them in ChainState.mtf_terms.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.optics.psf.builder import build_effective_psf
from radiant.optics.psf.effective import EffectivePSF
from radiant.platform.jitter import jitter_mtf_1d
from radiant.platform.smear import smear_mtf_1d
from radiant.platform.stage import PlatformStage


def _make_diffraction_psf(
    wavelength_um: float = 0.575,
    aperture_m: float = 0.5,
    focal_length_m: float = 5.0,
    pixel_pitch_m: float = 8e-6,
) -> EffectivePSF:
    from radiant.optics.psf_mono import compute_psf
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
    from radiant.optics._schema import ALL_PARAMETERS as OPT_PARAMS
    from radiant.platform._schema import ALL_PARAMETERS as PLAT_PARAMS

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


def _make_state_with_epsf_and_freq() -> tuple[ChainState, EffectivePSF]:
    """Build a ChainState with an EffectivePSF and spatial frequency grid."""
    epsf = _make_diffraction_psf()
    wl = np.array([0.45, 0.575, 0.70])
    state = ChainState(wavelength_um=wl)
    state = state.with_stage_output("optics", "effective_psf", epsf)

    # Set spatial frequency grid (cycles/mrad) as OpticsStage would.
    # For pixel_pitch = 8 µm, f = 5 m: Nyquist = 1/(2*8e-6) = 62500 cy/m
    #   = 62500 * 5.0 * 1e-3 = 312.5 cy/mrad.
    # Use a grid in cycles/m units that covers up to Nyquist, then convert.
    focal_length_m = 5.0
    pixel_pitch_m = 8e-6
    f_nyquist_m = 1.0 / (2.0 * pixel_pitch_m)
    freq_m = np.linspace(0, f_nyquist_m, 200)
    freq_mrad = freq_m * focal_length_m * 1e-3
    state = state.with_spatial_freq(freq_mrad)
    return state, epsf


class TestIsotropicJitterMTF:
    """Isotropic jitter: mtf_jitter_x == mtf_jitter_y."""

    @pytest.mark.level1
    def test_isotropic_jitter_x_equals_y(self) -> None:
        state, _ = _make_state_with_epsf_and_freq()
        params = _make_params(**{"platform.jitter_rms_urad": 5.0})
        out = PlatformStage().run(state, params)

        np.testing.assert_array_equal(
            out.mtf_terms["mtf_jitter_x"],
            out.mtf_terms["mtf_jitter_y"],
        )

    @pytest.mark.level1
    def test_isotropic_jitter_matches_analytic(self) -> None:
        state, _ = _make_state_with_epsf_and_freq()
        jitter_urad = 5.0
        focal_length_m = 5.0
        params = _make_params(**{"platform.jitter_rms_urad": jitter_urad})
        out = PlatformStage().run(state, params)

        freq_mrad = out.spatial_freq_cycles_per_mrad
        freq_m = freq_mrad / (focal_length_m * 1e-3)
        sigma_m = jitter_urad * 1e-6 * focal_length_m  # rad * f

        expected = jitter_mtf_1d(freq_m, sigma_m)
        np.testing.assert_allclose(out.mtf_terms["mtf_jitter_x"], expected, atol=1e-12)


class TestAnisotropicJitterMTF:
    """Anisotropic jitter: mtf_jitter_x ≠ mtf_jitter_y at non-zero freq."""

    @pytest.mark.level1
    def test_anisotropic_x_gt_y(self) -> None:
        """σ_x < σ_y → mtf_jitter_x > mtf_jitter_y at non-zero freq."""
        state, _ = _make_state_with_epsf_and_freq()
        params = _make_params(
            **{
                "platform.jitter_axes": "anisotropic",
                "platform.jitter_rms_x_urad": 2.0,
                "platform.jitter_rms_y_urad": 5.0,
            }
        )
        out = PlatformStage().run(state, params)

        # At non-zero frequencies, smaller sigma → higher MTF.
        mtf_x = out.mtf_terms["mtf_jitter_x"]
        mtf_y = out.mtf_terms["mtf_jitter_y"]
        # Skip DC (both = 1.0).
        assert np.all(mtf_x[1:] > mtf_y[1:])

    @pytest.mark.level1
    def test_anisotropic_matches_analytic(self) -> None:
        state, _ = _make_state_with_epsf_and_freq()
        focal_length_m = 5.0
        jitter_x_urad = 2.0
        jitter_y_urad = 5.0
        params = _make_params(
            **{
                "platform.jitter_axes": "anisotropic",
                "platform.jitter_rms_x_urad": jitter_x_urad,
                "platform.jitter_rms_y_urad": jitter_y_urad,
            }
        )
        out = PlatformStage().run(state, params)

        freq_mrad = out.spatial_freq_cycles_per_mrad
        freq_m = freq_mrad / (focal_length_m * 1e-3)

        sigma_x_m = jitter_x_urad * 1e-6 * focal_length_m
        sigma_y_m = jitter_y_urad * 1e-6 * focal_length_m

        expected_x = jitter_mtf_1d(freq_m, sigma_x_m)
        expected_y = jitter_mtf_1d(freq_m, sigma_y_m)

        np.testing.assert_allclose(out.mtf_terms["mtf_jitter_x"], expected_x, atol=1e-12)
        np.testing.assert_allclose(out.mtf_terms["mtf_jitter_y"], expected_y, atol=1e-12)


class TestSmearMTF:
    """Along-track smear: mtf_smear_y < 1 but mtf_smear_x == 1."""

    @pytest.mark.level1
    def test_along_track_smear_y_degrades(self) -> None:
        state, _ = _make_state_with_epsf_and_freq()
        params = _make_params(**{"platform.smear_length_um": 5.0})
        out = PlatformStage().run(state, params)

        mtf_smear_y = out.mtf_terms["mtf_smear_y"]
        # At non-zero freq, smear degrades y-axis MTF.
        assert np.any(mtf_smear_y[1:] < 1.0)

    @pytest.mark.level1
    def test_smear_x_is_unity(self) -> None:
        state, _ = _make_state_with_epsf_and_freq()
        params = _make_params(**{"platform.smear_length_um": 5.0})
        out = PlatformStage().run(state, params)

        np.testing.assert_array_equal(
            out.mtf_terms["mtf_smear_x"], np.ones_like(out.mtf_terms["mtf_smear_x"])
        )

    @pytest.mark.level1
    def test_smear_matches_analytic(self) -> None:
        state, _ = _make_state_with_epsf_and_freq()
        smear_um = 5.0
        focal_length_m = 5.0
        params = _make_params(**{"platform.smear_length_um": smear_um})
        out = PlatformStage().run(state, params)

        freq_mrad = out.spatial_freq_cycles_per_mrad
        freq_m = freq_mrad / (focal_length_m * 1e-3)
        smear_m = smear_um * 1e-6

        expected = smear_mtf_1d(freq_m, smear_m)
        np.testing.assert_allclose(out.mtf_terms["mtf_smear_y"], expected, atol=1e-12)


class TestZeroMotionMTF:
    """Zero jitter and zero smear → all MTF terms are unity."""

    @pytest.mark.level1
    def test_all_unity(self) -> None:
        state, _ = _make_state_with_epsf_and_freq()
        params = _make_params()
        out = PlatformStage().run(state, params)

        freq = out.spatial_freq_cycles_per_mrad
        ones = np.ones_like(freq)

        np.testing.assert_array_equal(out.mtf_terms["mtf_jitter_x"], ones)
        np.testing.assert_array_equal(out.mtf_terms["mtf_jitter_y"], ones)
        np.testing.assert_array_equal(out.mtf_terms["mtf_smear_x"], ones)
        np.testing.assert_array_equal(out.mtf_terms["mtf_smear_y"], ones)
