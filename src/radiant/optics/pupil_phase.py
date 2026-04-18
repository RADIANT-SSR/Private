"""Wavefront phase screen generation — random and Zernike-based.

Generates the phase component ``phi(x, y)`` of the complex pupil
function ``P = A * exp(i * phi)``.  Two modes:

- ``make_pupil_phase``: random phase screen scaled to a given RMS
  (suitable for Strehl estimation, not for realistic aberration shapes).
- ``make_pupil_phase_zernike``: deterministic phase from Zernike
  polynomial coefficients (correct PSF shape per aberration type).

See RADIANT_Spatial_Complete.md section 3.1.
"""

from __future__ import annotations

import logging

import numpy as np
import numpy.typing as npt

from radiant.optics.zernike_opd import evaluate_zernike_opd

logger = logging.getLogger(__name__)


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
        Operating wavelength [m]. Used to convert waves -> radians.

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
