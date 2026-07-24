"""Tests for EE_box computation from EffectivePSF.

Validates:
- EE_box for 1×1 pixel
- EE_box increases with n_pixels
- EE_box for full grid → 1.0
- Invalid inputs

See RADIANT_Spatial_Complete.md §2, CLAUDE.md Rule 9.
"""

from __future__ import annotations

import pytest

from radiant.optics.ee_box import compute_ee_box
from radiant.optics.psf.builder import build_effective_psf
from radiant.optics.psf.effective import EffectivePSF
from radiant.optics.psf_mono import compute_psf
from radiant.optics.sampling import compute_sampling

WAVELENGTH_M = 4.0e-6
FOCAL_LENGTH_M = 1.50
APERTURE_M = 0.30
PIXEL_PITCH_M = 15e-6


@pytest.fixture()
def epsf() -> EffectivePSF:
    config = compute_sampling(
        wavelength_m=WAVELENGTH_M,
        focal_length_m=FOCAL_LENGTH_M,
        aperture_diameter_m=APERTURE_M,
        pixel_pitch_m=PIXEL_PITCH_M,
        pupil_npix=128,
        psf_oversample=8,
    )
    psf_arr = compute_psf(config)
    return build_effective_psf(
        psf_arr,
        kernels=[],
        sample_spacing_m=config.focal_spacing_m,
        pixel_pitch_m=PIXEL_PITCH_M,
        wavelength_um=WAVELENGTH_M * 1e6,
    )


# --- Q = 2 quantitative anchor fixture (audit finding B1-3) ------------------
# Unaberrated Airy at critical sampling (Q = λF#/p = 2): λ = 4 µm, F# = 4
# (f = 1.2 m, D = 0.30 m), p = λF#/2 = 8 µm. Track A2 §8 gives the analytic
# ensquared energy in the centred 1-pixel box as EE_□ = 0.177327. With the
# CU-188 cell-overlap box weighting this is accurate to ~3e-4 even at the
# DEFAULT psf_oversample=8, so the fixture uses the default sampling.
_Q2_WL_M = 4.0e-6
_Q2_F_M = 1.20
_Q2_D_M = 0.30  # F# = 4.0
_Q2_PITCH_M = 8.0e-6  # Q = 4e-6·4 / 8e-6 = 2.0
_EE_BOX_Q2_ANALYTIC = 0.177327  # Track A2 §8d


@pytest.fixture()
def epsf_q2() -> EffectivePSF:
    config = compute_sampling(
        wavelength_m=_Q2_WL_M,
        focal_length_m=_Q2_F_M,
        aperture_diameter_m=_Q2_D_M,
        pixel_pitch_m=_Q2_PITCH_M,
        pupil_npix=128,
        psf_oversample=8,
    )
    psf_arr = compute_psf(config)
    return build_effective_psf(
        psf_arr,
        kernels=[],
        sample_spacing_m=config.focal_spacing_m,
        pixel_pitch_m=_Q2_PITCH_M,
        wavelength_um=_Q2_WL_M * 1e6,
    )


class TestComputeEEBox:
    @pytest.mark.level1
    def test_1x1_positive(self, epsf: EffectivePSF) -> None:
        ee = compute_ee_box(epsf, n_pixels=1)
        assert 0.0 < ee < 1.0

    @pytest.mark.level1
    def test_ee_box_airy_q2_anchor(self, epsf_q2: EffectivePSF) -> None:
        """EE_box(1×1) for an unaberrated Airy at Q=2 anchors to 0.177327 (B1-3).

        The prior tests are all qualitative (0<ee<1, monotone-in-n, →1 at
        n=50); a factor-2 box-size error passes every one. Track A2 §8 gives
        the analytic ensquared energy of the unaberrated Airy in the centred
        1-pixel box at critical sampling (Q=2) as EE_□ = 0.177327 — computed
        independently of RADIANT by adaptive 2-D quadrature.

        With the CU-188 cell-area-overlap box weighting, RADIANT's sampled-PSF
        EE_box is second-order accurate: it matches 0.177327 to ~3e-4 at the
        DEFAULT psf_oversample=8 used by the fixture (the old point-sampling
        scheme had an O(dx) edge bias of +0.042 here, ≈+24 %, which over-stated
        point-source / sub-pixel SNR). A factor-2 box-size error or a dropped
        normalization breaks the tolerance.
        """
        ee = compute_ee_box(epsf_q2, n_pixels=1)
        assert ee == pytest.approx(_EE_BOX_Q2_ANALYTIC, abs=1e-3)

    @pytest.mark.level1
    def test_increases_with_n(self, epsf: EffectivePSF) -> None:
        ee1 = compute_ee_box(epsf, n_pixels=1)
        ee3 = compute_ee_box(epsf, n_pixels=3)
        ee5 = compute_ee_box(epsf, n_pixels=5)
        assert ee1 < ee3 < ee5

    @pytest.mark.level1
    def test_large_box_near_one(self, epsf: EffectivePSF) -> None:
        ee = compute_ee_box(epsf, n_pixels=50)
        assert ee == pytest.approx(1.0, abs=0.01)

    @pytest.mark.level1
    def test_zero_n_raises(self, epsf: EffectivePSF) -> None:
        with pytest.raises(ValueError, match="n_pixels must be >= 1"):
            compute_ee_box(epsf, n_pixels=0)

    @pytest.mark.level1
    def test_negative_n_raises(self, epsf: EffectivePSF) -> None:
        with pytest.raises(ValueError, match="n_pixels must be >= 1"):
            compute_ee_box(epsf, n_pixels=-1)

    @pytest.mark.level1
    def test_default_is_1x1(self, epsf: EffectivePSF) -> None:
        ee_default = compute_ee_box(epsf)
        ee_1x1 = compute_ee_box(epsf, n_pixels=1)
        assert ee_default == ee_1x1
