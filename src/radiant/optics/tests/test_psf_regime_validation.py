"""Unit tests for the PSF-dependent regime consistency validator.

Matrix §7 (RADIANT_Use_Case_Matrix.md) defines two PSF-dependent guards
that fire in OpticsStage after the regime is finalized:

* Point-source descriptor with ``√A_t/d > 0.1·PSF_FWHM`` → raise
  :class:`ParameterBoundsError` (point-source approximation breaking
  down — the target is resolved).
* Sub-pixel descriptor with ``√A_t/d < 0.01·PSF_FWHM`` → emit a
  :class:`UserWarning` suggesting reclassification to ``point_source``
  (matrix §1.1).

Both checks are driven by :func:`_validate_psf_regime_consistency` in
``optics/stage.py`` and live there per Rule 19 (the PSF-dependent check
can only run after the PSF exists).
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.core.parameters import ParameterBoundsError
from radiant.optics.psf.effective import EffectivePSF
from radiant.optics.stage import _validate_psf_regime_consistency


# ---------------------------------------------------------------------------
# Helper: build a minimal EffectivePSF with a known FWHM
# ---------------------------------------------------------------------------


def _make_gaussian_epsf(fwhm_m: float, sample_spacing_m: float) -> EffectivePSF:
    """Build an EffectivePSF with a Gaussian core of the specified x-FWHM [m]."""
    sigma_m = fwhm_m / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    sigma_pix = sigma_m / sample_spacing_m
    npix = 65  # odd, large enough to contain several sigmas
    c = npix // 2
    y, x = np.indices((npix, npix), dtype=np.float64)
    r2 = (x - c) ** 2 + (y - c) ** 2
    data = np.exp(-0.5 * r2 / sigma_pix**2)
    data /= data.sum()
    return EffectivePSF(
        data=data,
        sample_spacing_m=sample_spacing_m,
        pixel_pitch_m=18e-6,
        wavelength_um=10.0,
        convolution_history=(),
    )


# ---------------------------------------------------------------------------
# Point-source guard — matrix §7 line 485
# ---------------------------------------------------------------------------


def test_point_source_resolved_target_raises() -> None:
    """√A_t/d = 0.5·PSF_FWHM on a point_source descriptor → raise."""
    fwhm_m = 20e-6  # at FPA
    f_m = 1.0
    epsf = _make_gaussian_epsf(fwhm_m=fwhm_m, sample_spacing_m=fwhm_m / 4.0)
    psf_fwhm_rad = fwhm_m / f_m
    # √A_t/d = 0.5·PSF_FWHM — clearly above the 0.1 threshold.
    angular_rad = 0.5 * psf_fwhm_rad

    with pytest.raises(ParameterBoundsError, match=r"point_source.*PSF_FWHM"):
        _validate_psf_regime_consistency(
            scene_type="point_source",
            angular_extent_rad=angular_rad,
            epsf=epsf,
            focal_length_m=f_m,
        )


def test_point_source_below_threshold_noop() -> None:
    """√A_t/d = 0.01·PSF_FWHM (well under 0.1) must not raise."""
    fwhm_m = 20e-6
    f_m = 1.0
    epsf = _make_gaussian_epsf(fwhm_m=fwhm_m, sample_spacing_m=fwhm_m / 4.0)
    psf_fwhm_rad = fwhm_m / f_m
    angular_rad = 0.01 * psf_fwhm_rad

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        # Should not raise ParameterBoundsError or UserWarning.
        _validate_psf_regime_consistency(
            scene_type="point_source",
            angular_extent_rad=angular_rad,
            epsf=epsf,
            focal_length_m=f_m,
        )


def test_point_source_right_at_threshold_noop() -> None:
    """Ratio exactly equal to 0.1 does not raise (strictly above)."""
    fwhm_m = 20e-6
    f_m = 1.0
    epsf = _make_gaussian_epsf(fwhm_m=fwhm_m, sample_spacing_m=fwhm_m / 4.0)
    psf_fwhm_rad = fwhm_m / f_m
    # Use exactly 0.1 — our check is "> 0.1", so 0.1 itself is OK.
    angular_rad = 0.1 * psf_fwhm_rad

    _validate_psf_regime_consistency(
        scene_type="point_source",
        angular_extent_rad=angular_rad,
        epsf=epsf,
        focal_length_m=f_m,
    )


# ---------------------------------------------------------------------------
# Sub-pixel guard — matrix §1.1 (reclassification warn)
# ---------------------------------------------------------------------------


def test_subpixel_collapses_to_point_warns() -> None:
    """√A_t/d = 1e-4·PSF_FWHM on a sub_pixel descriptor → UserWarning."""
    fwhm_m = 20e-6
    f_m = 1.0
    epsf = _make_gaussian_epsf(fwhm_m=fwhm_m, sample_spacing_m=fwhm_m / 4.0)
    psf_fwhm_rad = fwhm_m / f_m
    angular_rad = 1e-4 * psf_fwhm_rad  # way below 0.01

    with pytest.warns(UserWarning, match=r"effectively a point source"):
        _validate_psf_regime_consistency(
            scene_type="sub_pixel",
            angular_extent_rad=angular_rad,
            epsf=epsf,
            focal_length_m=f_m,
        )


def test_subpixel_above_threshold_noop() -> None:
    """√A_t/d = 0.5·PSF_FWHM on a sub_pixel descriptor — no warning."""
    fwhm_m = 20e-6
    f_m = 1.0
    epsf = _make_gaussian_epsf(fwhm_m=fwhm_m, sample_spacing_m=fwhm_m / 4.0)
    psf_fwhm_rad = fwhm_m / f_m
    angular_rad = 0.5 * psf_fwhm_rad

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        _validate_psf_regime_consistency(
            scene_type="sub_pixel",
            angular_extent_rad=angular_rad,
            epsf=epsf,
            focal_length_m=f_m,
        )


# ---------------------------------------------------------------------------
# No-op cases (guard must not fire)
# ---------------------------------------------------------------------------


def test_extended_scene_noop() -> None:
    """scene_type='extended' — the PSF-dependent guard is a no-op."""
    fwhm_m = 20e-6
    f_m = 1.0
    epsf = _make_gaussian_epsf(fwhm_m=fwhm_m, sample_spacing_m=fwhm_m / 4.0)
    psf_fwhm_rad = fwhm_m / f_m

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        # Even at 10× PSF_FWHM, extended is a no-op.
        _validate_psf_regime_consistency(
            scene_type="extended",
            angular_extent_rad=10.0 * psf_fwhm_rad,
            epsf=epsf,
            focal_length_m=f_m,
        )


def test_missing_psf_noop() -> None:
    """epsf=None (degenerate chain) — validator is a no-op."""
    _validate_psf_regime_consistency(
        scene_type="point_source",
        angular_extent_rad=1e-3,
        epsf=None,
        focal_length_m=1.0,
    )


def test_nonfinite_angular_extent_noop() -> None:
    """Infinite or zero angular extent (no geometry) — validator is a no-op."""
    fwhm_m = 20e-6
    f_m = 1.0
    epsf = _make_gaussian_epsf(fwhm_m=fwhm_m, sample_spacing_m=fwhm_m / 4.0)

    _validate_psf_regime_consistency(
        scene_type="point_source",
        angular_extent_rad=float("inf"),
        epsf=epsf,
        focal_length_m=f_m,
    )
    _validate_psf_regime_consistency(
        scene_type="point_source",
        angular_extent_rad=0.0,
        epsf=epsf,
        focal_length_m=f_m,
    )
    _validate_psf_regime_consistency(
        scene_type="point_source",
        angular_extent_rad=float("nan"),
        epsf=epsf,
        focal_length_m=f_m,
    )
