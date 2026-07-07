"""Electronics MTF — readout amplifier bandwidth as a spatial low-pass.

Finite amplifier bandwidth low-passes the readout waveform; at pixel
clock rate ``f_clk`` the temporal response maps onto the focal plane as
a 1-D blur along the readout (cross-scan, x) axis with equivalent
Gaussian sigma ``sigma_e`` [m]:

    MTF_elec(f) = exp(-2 pi^2 sigma_e^2 f^2)

Rule 4: this term enters BOTH spatial paths — a Gaussian-in-x kernel on
the EffectivePSF (applied in PerformanceStage, like IPC) and the
analytic MTF term in the product path (pushed by ReadoutStage). It is
therefore included in the dual-path consistency check, unlike TDI
mis-registration.

See RADIANT docs/tracking/gaps.md Gap 32.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def electronics_mtf_1d(
    freq_cycles_per_m: npt.NDArray[np.float64],
    sigma_m: float,
) -> npt.NDArray[np.float64]:
    """Analytic electronics MTF, ``exp(-2 pi^2 sigma^2 f^2)``.

    Parameters
    ----------
    freq_cycles_per_m:
        Spatial frequency axis [cycles/m].
    sigma_m:
        Equivalent Gaussian blur sigma on the focal plane [m].

    Returns
    -------
    ndarray
        MTF values in (0, 1]; all ones when sigma is zero.
    """
    if sigma_m < 0.0:
        raise ValueError(f"electronics_mtf_1d: sigma_m must be non-negative, got {sigma_m}.")
    if sigma_m == 0.0:
        return np.ones_like(freq_cycles_per_m)
    return np.exp(-2.0 * np.pi**2 * sigma_m**2 * freq_cycles_per_m**2)


def electronics_kernel_2d(
    npix: int,
    sample_spacing_m: float,
    sigma_m: float,
) -> npt.NDArray[np.float64]:
    """Square kernel: Gaussian along x (readout axis), delta along y.

    Parameters
    ----------
    npix:
        Side length of the square kernel grid (must be odd).
    sample_spacing_m:
        Physical spacing between kernel samples [m].
    sigma_m:
        Electronics blur sigma [m].

    Returns
    -------
    ndarray of shape (npix, npix)
        Normalised kernel (sums to 1.0). Delta if sigma is zero.
    """
    if npix < 1 or npix % 2 == 0:
        raise ValueError(f"npix must be a positive odd integer, got {npix}")
    if sample_spacing_m <= 0.0:
        raise ValueError(f"sample_spacing_m must be positive, got {sample_spacing_m}")
    if sigma_m < 0.0:
        raise ValueError(f"sigma_m must be non-negative, got {sigma_m}")

    c = npix // 2
    kernel = np.zeros((npix, npix), dtype=np.float64)
    if sigma_m == 0.0:
        kernel[c, c] = 1.0
        return kernel

    x = (np.arange(npix) - c) * sample_spacing_m
    row = np.exp(-(x**2) / (2.0 * sigma_m**2))
    kernel[c, :] = row / row.sum()  # [row, col] = [y, x]: blur along x only
    return kernel
