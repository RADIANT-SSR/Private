"""Centered FFT convolution of two equal-size real grids (CU-165).

The one place the PSF path's convolution arithmetic lives (Rule 19):
both :func:`radiant.optics.psf.builder.build_effective_psf` and
:meth:`radiant.optics.psf.effective.EffectivePSF.with_kernel` apply a
center-origin kernel to a center-origin PSF on the same grid, and both
historically evaluated

    real(fftshift(ifft2(fft2(ifftshift(a)) · fft2(ifftshift(b)))))

— three full complex-to-complex FFTs plus two whole-array rolls per
kernel, which at the CU-165 grids (16384², 4.3 GB complex) dominated a
93-second ``evaluate()``.

**Exactness.** For even n, shifting by exactly n/2 in both axes maps to a
checkerboard in frequency: ``fft2(ifftshift(x)) = S ⊙ fft2(x)`` with
``S[k, l] = (−1)^(k+l)``. The two checkerboards cancel in the product
(``S² = 1``), so the legacy expression equals

    fftshift(irfft2(rfft2(a) · rfft2(b)))

**identically** in exact arithmetic — same grid, same discretization, same
mathematics; only the floating-point rounding path differs (validated to
≤1e-13 relative in ``tests/test_fft_convolve.py``, ten orders below the
golden suite's rel=1e-3). The real-input transforms halve the time and
memory. Odd-size grids (never produced by ``compute_sampling``, which pads
to powers of two) fall back to the legacy expression unchanged.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def convolve_centered(
    a: npt.NDArray[np.float64],
    b: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Circular convolution of two equal-shape, center-origin real arrays.

    Parameters
    ----------
    a:
        First array (e.g. the PSF), origin at ``(n//2, n//2)``.
    b:
        Second array (e.g. the padded kernel), origin at ``(n//2, n//2)``.

    Returns
    -------
    ndarray
        The convolution, center-origin, same shape, real (float64).
    """
    n_rows, n_cols = a.shape
    if n_rows % 2 == 0 and n_cols % 2 == 0:
        # Even grid: shift-elision + real-input FFTs (see module docstring).
        product = np.fft.rfft2(a) * np.fft.rfft2(b)
        return np.asarray(
            np.fft.fftshift(np.fft.irfft2(product, s=(n_rows, n_cols))),
            dtype=np.float64,
        )
    # Odd grid: the checkerboard identity needs even n — legacy path.
    a_fft = np.fft.fft2(np.fft.ifftshift(a))
    b_fft = np.fft.fft2(np.fft.ifftshift(b))
    return np.asarray(np.real(np.fft.fftshift(np.fft.ifft2(a_fft * b_fft))), dtype=np.float64)


__all__ = ["convolve_centered"]
