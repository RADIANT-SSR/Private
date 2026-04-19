"""Kolmogorov turbulence kernel for PSF convolution.

Builds a 2-D spatial kernel by inverse-FFT of the analytic Kolmogorov
long-exposure MTF:

    MTF(f) = exp(-3.44 * (lambda * f_angular / r0)^(5/3))

This guarantees exact consistency between the PSF-path kernel and
the MTF-path analytic formula.

See RADIANT_Spatial_Complete.md section 6 step 8, section 9 row 12.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def kolmogorov_kernel_2d(
    npix: int,
    sample_spacing_m: float,
    wavelength_m: float,
    r0_m: float,
    focal_length_m: float,
) -> npt.NDArray[np.float64]:
    """Build a 2-D Kolmogorov turbulence kernel via inverse-FFT of the MTF.

    Parameters
    ----------
    npix:
        Side length of the square kernel grid (must be odd).
    sample_spacing_m:
        Physical spacing between kernel samples [m] on the focal plane.
    wavelength_m:
        Operating wavelength [m].
    r0_m:
        Fried coherence diameter [m]. Must be positive.
    focal_length_m:
        Effective focal length [m].

    Returns
    -------
    ndarray of shape ``(npix, npix)``
        Normalised 2-D turbulence kernel (sums to 1.0).
    """
    # Build 2-D frequency grid in focal-plane cycles/m.
    freq_1d = np.fft.fftfreq(npix, d=sample_spacing_m)
    fx, fy = np.meshgrid(freq_1d, freq_1d, indexing="xy")
    f_focal = np.sqrt(fx**2 + fy**2)

    # Convert focal-plane frequency to angular frequency [cycles/rad].
    f_angular = f_focal * focal_length_m

    # Kolmogorov MTF: exp(-3.44 * (lambda * f_angular / r0)^(5/3))
    arg = wavelength_m * f_angular / r0_m
    mtf_2d = np.exp(-3.44 * arg ** (5.0 / 3.0))

    # Inverse FFT to get the spatial kernel.
    kernel = np.real(np.fft.ifft2(mtf_2d))
    kernel = np.fft.fftshift(kernel)

    # Ensure non-negative (numerical noise can create tiny negatives).
    kernel = np.maximum(kernel, 0.0)

    # Normalise to unit volume.
    total = kernel.sum()
    if total > 0.0:
        kernel /= total

    return kernel
