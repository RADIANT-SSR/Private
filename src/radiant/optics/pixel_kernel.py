"""Pixel aperture kernel for PSF convolution.

The pixel integrates light over its active area, which is equivalent
to convolving the PSF with a 2-D rect function of dimensions
``(pitch_x × fill_factor, pitch_y × fill_factor)``.

This is a separable kernel: the 2-D result is the outer product of
two 1-D rect kernels.

Sampling (CU-003, option a): each 1-D kernel sample carries the exact
**area overlap** of its sample cell ``[x_i − Δ/2, x_i + Δ/2]`` with the
rect ``[−w/2, +w/2]`` (anti-aliased edges), not a binary inside/outside
test. The binary mask quantised the rect width to the sample grid, which
made the kernel's DFT deviate from the analytic sinc product-path term by
up to ~4.5e-2 at detector Nyquist in undersampled configs; the
area-integrated kernel reduces that discretisation error ~13× — down to
the ``sinc(πfΔ)`` bin-average envelope (~3.5e-3 at Nyquist for the worst
measured config), which is the irreducible floor of any nonnegative
sampled kernel (Poisson summation; CU-003 investigation, 2026-07-07).

See RADIANT_Spatial_Complete.md §6 step 1.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def make_pixel_aperture_kernel_2d(
    npix: int,
    sample_spacing_m: float,
    pixel_pitch_x_m: float,
    pixel_pitch_y_m: float,
    fill_factor: float = 1.0,
) -> npt.NDArray[np.float64]:
    """Build a 2-D pixel aperture rect kernel.

    Parameters
    ----------
    npix:
        Side length of the square kernel grid (must be odd).
    sample_spacing_m:
        Physical spacing between kernel samples [m].
    pixel_pitch_x_m:
        Pixel pitch along x [m].
    pixel_pitch_y_m:
        Pixel pitch along y [m].
    fill_factor:
        Photosensitive fraction of the pixel cell, in (0, 1].

    Returns
    -------
    ndarray of shape ``(npix, npix)``
        Normalised 2-D rect kernel (sums to 1.0).
    """
    kx = _rect_1d(npix, sample_spacing_m, pixel_pitch_x_m * fill_factor)
    ky = _rect_1d(npix, sample_spacing_m, pixel_pitch_y_m * fill_factor)

    kernel = np.outer(ky, kx)
    total = kernel.sum()
    if total > 0.0:
        kernel /= total

    return kernel


def _rect_1d(
    npix: int,
    sample_spacing_m: float,
    width_m: float,
) -> npt.NDArray[np.float64]:
    """1-D rect centred on the grid, sampled by exact area overlap.

    Each sample's weight is the length of the intersection of its sample
    cell ``[x_i − Δ/2, x_i + Δ/2]`` with the rect ``[−w/2, +w/2]``,
    normalised by ``Δ``:

        w_i = clip((w/2 − |x_i|)/Δ + 1/2, 0, 1)

    Interior samples get 1, edge samples get their fractional coverage,
    exterior samples get 0 — the kernel is exact for the underlying
    continuous rect regardless of how the grid lands on the edges
    (CU-003 option a). Nonnegative by construction, so the PSF-path
    nonnegativity and EE invariants are preserved.
    """
    c = npix // 2
    x = (np.arange(npix) - c) * sample_spacing_m
    half = width_m / 2.0
    coverage = np.clip((half - np.abs(x)) / sample_spacing_m + 0.5, 0.0, 1.0)
    total = coverage.sum()
    if total > 0.0:
        coverage /= total
    return coverage
