"""Monochromatic PSF via FFT of the complex pupil function.

Implements scalar Fraunhofer diffraction for a circular aperture with
optional central obscuration and wavefront error (WFE)::

    P(x, y) = A(x, y) · exp(i · 2π · OPD(x, y) / λ)
    PSF = |FFT(P)|² / Σ|FFT(P)|²

where ``A`` is the pupil amplitude mask (1 inside clear aperture,
0 outside) and ``OPD`` is the optical path difference in metres.

Assumptions:
- Scalar diffraction (polarization ignored)
- Paraxial approximation (valid for f/# > 2)
- Spatially coherent pupil

See RADIANT_Spatial_Complete.md §3.1 for the full derivation.
See also ``diffraction_poly.py`` for polychromatic PSF.
"""

from __future__ import annotations

import logging

import numpy as np
import numpy.typing as npt

from radiant.optics.sampling import PSFSamplingConfig
from radiant.optics.wavefront import WavefrontError, WfeMode
from radiant.optics.zernike import evaluate_zernike_opd

logger = logging.getLogger(__name__)


def make_pupil_amplitude(
    npix: int,
    obscuration_ratio: float = 0.0,
) -> npt.NDArray[np.float64]:
    """Generate a circular pupil amplitude mask.

    The aperture is centered on the grid and has unit radius (fills
    the grid from -0.5 to +0.5 in normalised coordinates). The central
    obscuration is a concentric circle of radius ``obscuration_ratio``.

    Parameters
    ----------
    npix:
        Side length of the square pupil grid.
    obscuration_ratio:
        D_secondary / D_primary. Must be in [0, 1).

    Returns
    -------
    ndarray of shape (npix, npix)
        Binary amplitude: 1.0 in clear aperture, 0.0 outside.
    """
    if not (0.0 <= obscuration_ratio < 1.0):
        raise ValueError(
            f"obscuration_ratio must be in [0, 1), got {obscuration_ratio}"
        )

    # Normalised coordinates: [-0.5, +0.5]
    x = np.linspace(-0.5, 0.5, npix, endpoint=False) + 0.5 / npix
    xx, yy = np.meshgrid(x, x, indexing="xy")
    r = np.sqrt(xx**2 + yy**2)

    mask = np.zeros((npix, npix), dtype=np.float64)
    mask[r <= 0.5] = 1.0
    if obscuration_ratio > 0.0:
        mask[r <= 0.5 * obscuration_ratio] = 0.0

    return mask


def make_pupil_phase(
    npix: int,
    wfe_rms_waves: float = 0.0,
    wavelength_m: float = 1.0,
) -> npt.NDArray[np.float64]:
    """Generate a wavefront phase screen.

    For ``wfe_rms_waves = 0``, returns a zero-phase array (perfect
    optics). For non-zero WFE, generates a random phase screen with
    the specified RMS in waves. The phase is uniform-random per pixel,
    scaled to the correct RMS — suitable for Strehl estimation but not
    for realistic aberration modelling.

    Parameters
    ----------
    npix:
        Side length of the square grid.
    wfe_rms_waves:
        Wavefront error RMS in waves at ``wavelength_m``.
    wavelength_m:
        Operating wavelength [m]. Used to convert waves → radians.

    Returns
    -------
    ndarray of shape (npix, npix)
        Phase in radians.
    """
    if wfe_rms_waves < 0.0:
        raise ValueError(f"wfe_rms_waves must be non-negative, got {wfe_rms_waves}")

    if wfe_rms_waves == 0.0:
        return np.zeros((npix, npix), dtype=np.float64)

    if wfe_rms_waves > 1.0:
        logger.warning(
            "WFE = %.2f waves exceeds 1 wave — PSF will be severely degraded. "
            "Check if this is intentional.",
            wfe_rms_waves,
        )

    # Random phase with correct RMS.
    rng = np.random.default_rng(seed=42)
    phase_raw = rng.standard_normal((npix, npix))
    phase_raw -= phase_raw.mean()
    phase_raw /= phase_raw.std()
    phase_rad = phase_raw * (2.0 * np.pi * wfe_rms_waves)
    return phase_rad


def make_pupil_phase_zernike(
    npix: int,
    coeffs: dict[int, float],
    reference_wavelength_m: float,
    operating_wavelength_m: float,
    obscuration_ratio: float = 0.0,
) -> npt.NDArray[np.float64]:
    """Generate a wavefront phase screen from Zernike coefficients.

    Evaluates the Zernike OPD map on the pupil grid, converts from
    waves (at reference wavelength) to radians (at operating wavelength)::

        phase_rad = 2*pi * OPD_waves * (lambda_ref / lambda_operating)

    Parameters
    ----------
    npix:
        Side length of the square grid (must match pupil amplitude grid).
    coeffs:
        Noll-indexed Zernike coefficients in waves at reference wavelength.
    reference_wavelength_m:
        Wavelength at which coefficients are defined [m].
    operating_wavelength_m:
        Wavelength at which the PSF is computed [m].
    obscuration_ratio:
        Central obscuration ratio (0 = unobscured).

    Returns
    -------
    ndarray of shape (npix, npix)
        Phase screen in radians. Zero outside the pupil.
    """
    opd_waves = evaluate_zernike_opd(coeffs, npix, obscuration_ratio)
    # OPD in meters = opd_waves * lambda_ref
    # Phase at operating lambda = 2*pi * OPD_m / lambda_operating
    scale = reference_wavelength_m / operating_wavelength_m
    return 2.0 * np.pi * opd_waves * scale


def compute_psf(
    config: PSFSamplingConfig,
    obscuration_ratio: float = 0.0,
    wfe: WavefrontError | None = None,
) -> npt.NDArray[np.float64]:
    """Compute the diffraction PSF via FFT of the complex pupil.

    Dispatches on ``wfe.mode``:

    - ``None`` or ``SCALAR_RMS`` with ``rms_waves=0``: diffraction-limited.
    - ``SCALAR_RMS``: random phase screen scaled to RMS (Strehl-correct
      but aberration-agnostic).
    - ``ZERNIKE``: deterministic phase from Zernike coefficients (correct
      PSF shape for each aberration type).

    Parameters
    ----------
    config:
        PSF sampling configuration from :func:`compute_sampling`.
    obscuration_ratio:
        Central obscuration ratio D_sec / D_pri.
    wfe:
        Wavefront error specification. ``None`` = perfect optics.

    Returns
    -------
    ndarray of shape (padded_npix, padded_npix)
        Normalised PSF (sums to 1.0).
    """
    npix = config.pupil_npix
    npad = config.padded_npix

    amplitude = make_pupil_amplitude(npix, obscuration_ratio)

    # --- Phase screen dispatch ---
    if wfe is None:
        phase = np.zeros((npix, npix), dtype=np.float64)
    elif wfe.mode == WfeMode.SCALAR_RMS:
        rms = wfe.rms_waves if wfe.rms_waves is not None else 0.0
        phase = make_pupil_phase(npix, rms, config.wavelength_m)
    elif wfe.mode == WfeMode.ZERNIKE:
        assert wfe.zernike_coeffs is not None
        ref_m = wfe.reference_wavelength_um * 1e-6
        phase = make_pupil_phase_zernike(
            npix,
            wfe.zernike_coeffs,
            reference_wavelength_m=ref_m,
            operating_wavelength_m=config.wavelength_m,
            obscuration_ratio=obscuration_ratio,
        )
    else:
        raise NotImplementedError(
            f"WFE mode {wfe.mode.value!r} is not supported in compute_psf. "
            f"Supported modes: scalar_rms, zernike."
        )

    # Complex pupil function.
    pupil = amplitude * np.exp(1j * phase)

    # Zero-pad to FFT size.
    padded = np.zeros((npad, npad), dtype=np.complex128)
    # Center the pupil in the padded grid.
    offset = (npad - npix) // 2
    padded[offset : offset + npix, offset : offset + npix] = pupil

    # FFT → PSF intensity.
    U = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(padded)))
    psf = np.abs(U) ** 2

    # Normalise to unit volume.
    total = psf.sum()
    if total > 0:
        psf /= total

    return psf
