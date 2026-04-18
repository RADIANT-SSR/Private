"""Wavefront OPD map evaluation from Zernike coefficients.

Evaluates a weighted sum of Zernike polynomials on a pupil grid to
produce a 2-D optical path difference (OPD) map in waves.

Uses the same coordinate convention as
:func:`radiant.optics.pupil_amplitude.make_pupil_amplitude`:
coordinates in [-0.5, +0.5] with the pupil at radius 0.5.

See RADIANT_Spatial_Complete.md section 3.2.

WARNING: For obscuration_ratio > 0.30, standard Zernike polynomials are
NOT orthogonal on the annular aperture. The OPD map is still physically
valid, but individual Zernike coefficients lose their orthogonal
decomposition meaning.
"""

from __future__ import annotations

import warnings

import numpy as np
import numpy.typing as npt

from radiant.optics.zernike import zernike_polynomial


def evaluate_zernike_opd(
    coeffs: dict[int, float],
    npix: int,
    obscuration_ratio: float = 0.0,
) -> npt.NDArray[np.float64]:
    """Evaluate wavefront OPD from Zernike coefficients on a pupil grid.

    The pupil grid uses the same coordinate convention as
    :func:`radiant.optics.pupil_amplitude.make_pupil_amplitude`:
    coordinates in [-0.5, +0.5] with the pupil at radius 0.5.
    Internally, these are mapped to the unit circle (rho in [0, 1])
    for Zernike evaluation.

    Parameters
    ----------
    coeffs:
        Noll-indexed Zernike coefficients in waves.
        Keys are Noll indices (>= 1), values are coefficients.
    npix:
        Side length of the square pupil grid.
    obscuration_ratio:
        D_secondary / D_primary. Must be in [0, 1).

    Returns
    -------
    ndarray of shape (npix, npix)
        OPD in waves. Pixels outside the pupil aperture are 0.

    Raises
    ------
    ValueError
        If any Noll index < 1, or obscuration_ratio >= 1.
    """
    if not (0.0 <= obscuration_ratio < 1.0):
        raise ValueError(
            f"obscuration_ratio must be in [0, 1), got {obscuration_ratio}"
        )

    if obscuration_ratio > 0.30:
        warnings.warn(
            f"Obscuration ratio {obscuration_ratio:.2f} > 0.30: standard "
            "Zernike polynomials are NOT orthogonal on an annular pupil. "
            "Individual coefficient interpretations may be misleading. "
            "Annular Zernikes (Mahajan 1981) are not implemented.",
            UserWarning,
            stacklevel=2,
        )

    for j, c in coeffs.items():
        if j < 1:
            raise ValueError(f"Noll index must be >= 1, got {j}")
        if abs(c) > 10.0:
            warnings.warn(
                f"Zernike Z{j} coefficient = {c:.2f} waves exceeds 10 waves. "
                "PSF will be severely degraded; verify this is intentional.",
                UserWarning,
                stacklevel=2,
            )

    # Match make_pupil_amplitude coordinate convention: [-0.5, +0.5]
    x = np.linspace(-0.5, 0.5, npix, endpoint=False) + 0.5 / npix
    xx, yy = np.meshgrid(x, x, indexing="xy")
    r = np.sqrt(xx**2 + yy**2)

    # Map to unit circle for Zernike evaluation: rho = 2*r -> [0, 1]
    rho = 2.0 * r
    theta = np.arctan2(yy, xx)

    # Pupil mask (same logic as make_pupil_amplitude)
    mask = rho <= 1.0
    if obscuration_ratio > 0.0:
        mask &= rho >= obscuration_ratio

    opd = np.zeros((npix, npix), dtype=np.float64)
    for j, coeff in coeffs.items():
        if coeff == 0.0:
            continue
        Z = zernike_polynomial(j, rho, theta)
        opd += coeff * Z

    opd[~mask] = 0.0
    return opd
