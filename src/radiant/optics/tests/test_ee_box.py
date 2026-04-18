"""Tests for EE_box computation from EffectivePSF.

Validates:
- EE_box for 1×1 pixel
- EE_box increases with n_pixels
- EE_box for full grid → 1.0
- Invalid inputs

See RADIANT_Spatial_Complete.md §2, CLAUDE.md Rule 9.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.optics.psf_mono import compute_psf
from radiant.optics.ee_box import compute_ee_box
from radiant.optics.psf.effective import EffectivePSF
from radiant.optics.psf.builder import build_effective_psf
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


class TestComputeEEBox:
    def test_1x1_positive(self, epsf: EffectivePSF) -> None:
        ee = compute_ee_box(epsf, n_pixels=1)
        assert 0.0 < ee < 1.0

    def test_increases_with_n(self, epsf: EffectivePSF) -> None:
        ee1 = compute_ee_box(epsf, n_pixels=1)
        ee3 = compute_ee_box(epsf, n_pixels=3)
        ee5 = compute_ee_box(epsf, n_pixels=5)
        assert ee1 < ee3 < ee5

    def test_large_box_near_one(self, epsf: EffectivePSF) -> None:
        ee = compute_ee_box(epsf, n_pixels=50)
        assert ee == pytest.approx(1.0, abs=0.01)

    def test_zero_n_raises(self, epsf: EffectivePSF) -> None:
        with pytest.raises(ValueError, match="n_pixels must be >= 1"):
            compute_ee_box(epsf, n_pixels=0)

    def test_negative_n_raises(self, epsf: EffectivePSF) -> None:
        with pytest.raises(ValueError, match="n_pixels must be >= 1"):
            compute_ee_box(epsf, n_pixels=-1)

    def test_default_is_1x1(self, epsf: EffectivePSF) -> None:
        ee_default = compute_ee_box(epsf)
        ee_1x1 = compute_ee_box(epsf, n_pixels=1)
        assert ee_default == ee_1x1
