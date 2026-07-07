"""Surface-roughness scatter — total integrated scatter (TIS) model (Gap 31).

Micro-roughness on optical surfaces scatters a fraction of the specular
beam into a wide-angle halo. In the smooth-surface (Rayleigh–Rice)
limit at normal incidence the scattered fraction is

    TIS = 1 − exp(−(4π σ_s / λ)²)   ≈ (4π σ_s / λ)²  for σ_s ≪ λ

(Bennett & Porteus 1961; Stover, *Optical Scattering*, 3rd ed. §4).

v1 model: the scattered energy lands in an isotropic Gaussian halo of
configurable focal-plane width. The PSF-path kernel and the analytic
MTF term are exact Fourier pairs, so the term enters BOTH spatial paths
(Rule 4) and participates in the dual-path consistency check:

    kernel(r)  = (1 − TIS)·δ(r) + TIS·G(r; σ_halo)
    MTF(f)     = (1 − TIS) + TIS·exp(−2π² σ_halo² f²)

Full Harvey–Shack BRDF modelling is out of scope for v1 (see gap entry).
"""

from __future__ import annotations

import logging
import math

import numpy as np
import numpy.typing as npt

logger = logging.getLogger(__name__)

# Above this TIS the smooth-surface approximation degrades badly.
_TIS_VALIDITY_LIMIT = 0.3


def total_integrated_scatter(roughness_m: float, wavelength_m: float) -> float:
    """TIS at normal incidence: ``1 − exp(−(4π σ_s / λ)²)``.

    Parameters
    ----------
    roughness_m:
        RMS surface roughness σ_s [m] (effective, combined over the train).
    wavelength_m:
        Wavelength [m].

    Returns
    -------
    float
        Scattered fraction in [0, 1).

    Raises
    ------
    ValueError
        On non-positive wavelength or negative roughness.
    """
    if wavelength_m <= 0.0:
        raise ValueError(f"total_integrated_scatter: wavelength must be positive, got {wavelength_m} m.")
    if roughness_m < 0.0:
        raise ValueError(f"total_integrated_scatter: roughness must be non-negative, got {roughness_m} m.")
    tis = 1.0 - math.exp(-((4.0 * math.pi * roughness_m / wavelength_m) ** 2))
    if tis > _TIS_VALIDITY_LIMIT:
        logger.warning(
            "TIS = %.3f exceeds the smooth-surface validity limit (~%.1f): "
            "sigma_s = %.3g m is not << lambda = %.3g m. The Rayleigh-Rice "
            "TIS formula is inaccurate here; treat results as qualitative.",
            tis,
            _TIS_VALIDITY_LIMIT,
            roughness_m,
            wavelength_m,
        )
    return tis


def scatter_mtf_1d(
    freq_cycles_per_m: npt.NDArray[np.float64],
    sigma_halo_m: float,
    tis: float,
) -> npt.NDArray[np.float64]:
    """Analytic scatter MTF: ``(1 − TIS) + TIS·exp(−2π² σ_halo² f²)``."""
    if not 0.0 <= tis < 1.0:
        raise ValueError(f"scatter_mtf_1d: tis must be in [0, 1), got {tis}.")
    if sigma_halo_m <= 0.0:
        raise ValueError(f"scatter_mtf_1d: sigma_halo_m must be positive, got {sigma_halo_m}.")
    return (1.0 - tis) + tis * np.exp(-2.0 * np.pi**2 * sigma_halo_m**2 * freq_cycles_per_m**2)


def scatter_kernel_2d(
    npix: int,
    sample_spacing_m: float,
    sigma_halo_m: float,
    tis: float,
) -> npt.NDArray[np.float64]:
    """Mixed kernel: ``(1 − TIS)·δ + TIS·Gaussian(σ_halo)``, unit volume.

    Energy-conserving by construction — scatter redistributes energy
    from the specular core into the halo; nothing is absorbed.
    """
    if npix < 1 or npix % 2 == 0:
        raise ValueError(f"npix must be a positive odd integer, got {npix}")
    if sample_spacing_m <= 0.0:
        raise ValueError(f"sample_spacing_m must be positive, got {sample_spacing_m}")
    if not 0.0 <= tis < 1.0:
        raise ValueError(f"scatter_kernel_2d: tis must be in [0, 1), got {tis}.")
    if sigma_halo_m <= 0.0:
        raise ValueError(f"scatter_kernel_2d: sigma_halo_m must be positive, got {sigma_halo_m}.")

    c = npix // 2
    kernel = np.zeros((npix, npix), dtype=np.float64)
    if tis == 0.0:
        kernel[c, c] = 1.0
        return kernel

    x = (np.arange(npix) - c) * sample_spacing_m
    xx, yy = np.meshgrid(x, x, indexing="xy")
    halo = np.exp(-(xx**2 + yy**2) / (2.0 * sigma_halo_m**2))
    halo /= halo.sum()

    kernel = tis * halo
    kernel[c, c] += 1.0 - tis
    return kernel
