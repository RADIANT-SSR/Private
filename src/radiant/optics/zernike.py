"""Zernike polynomial evaluation on circular and annular pupil grids.

Uses the Noll (1976) indexing convention. Standard (non-annular) Zernike
polynomials are orthogonal on the unit circle but NOT on an annular pupil.
For central obscuration > 0.30, a UserWarning is emitted.

Reference: R.J. Noll, "Zernike polynomials and atmospheric turbulence",
J. Opt. Soc. Am. 66(3), 207-211 (1976).

WARNING: For obscuration_ratio > 0.30, standard Zernike polynomials are
NOT orthogonal on the annular aperture. The OPD map is still physically
valid (it represents a real wavefront shape), but individual Zernike
coefficients lose their orthogonal decomposition meaning. Annular Zernike
polynomials (Mahajan 1981) are NOT implemented.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import numpy.typing as npt


def noll_to_nm(j: int) -> tuple[int, int]:
    """Convert Noll index *j* to radial/azimuthal orders (n, m).

    Parameters
    ----------
    j:
        Noll index (starts at 1).

    Returns
    -------
    (n, m)
        Radial order *n* >= 0 and signed azimuthal order *m*.

    Raises
    ------
    ValueError
        If *j* < 1.
    """
    if j < 1:
        raise ValueError(f"Noll index must be >= 1, got {j}")

    # Find radial order n: cumulative count up to order n is n(n+1)/2
    n = int((-1 + math.sqrt(1 + 8 * (j - 1))) / 2)
    if (n + 1) * (n + 2) // 2 < j:
        n += 1

    # 0-based index within order n
    k = j - n * (n + 1) // 2 - 1

    # |m| follows a zigzag pattern within each order
    if n % 2 == 0:
        m_abs = 2 * ((k + 1) // 2)
    else:
        m_abs = 2 * (k // 2) + 1

    # Sign: even j -> positive m (cosine), odd j -> negative m (sine)
    if m_abs == 0:
        m = 0
    elif j % 2 == 0:
        m = m_abs
    else:
        m = -m_abs

    return n, m


def zernike_radial(
    n: int,
    m_abs: int,
    rho: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    r"""Evaluate the radial Zernike polynomial :math:`R_n^{|m|}(\rho)`.

    Parameters
    ----------
    n:
        Radial order (>= 0).
    m_abs:
        Absolute azimuthal order (>= 0, *n* - *m_abs* must be even).
    rho:
        Radial coordinate array, in [0, 1] for the unit circle.

    Returns
    -------
    ndarray
        :math:`R_n^{|m|}(\rho)` at each point.
    """
    if (n - m_abs) % 2 != 0:
        return np.zeros_like(rho)

    result = np.zeros_like(rho, dtype=np.float64)
    num_terms = (n - m_abs) // 2 + 1

    for s in range(num_terms):
        sign = (-1) ** s
        num = math.factorial(n - s)
        den = (
            math.factorial(s)
            * math.factorial((n + m_abs) // 2 - s)
            * math.factorial((n - m_abs) // 2 - s)
        )
        result = result + sign * (num / den) * rho ** (n - 2 * s)

    return result


def zernike_polynomial(
    j: int,
    rho: npt.NDArray[np.float64],
    theta: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    r"""Evaluate a single Noll-indexed Zernike polynomial :math:`Z_j(\rho, \theta)`.

    Uses the Noll normalization convention::

        N = sqrt(2(n+1))   for m != 0
        N = sqrt(n+1)      for m == 0

    This gives :math:`\int \int Z_j^2 \, dA = \pi` over the unit disk.

    Parameters
    ----------
    j:
        Noll index (>= 1).
    rho:
        Radial coordinate [0, 1].
    theta:
        Azimuthal coordinate [rad].

    Returns
    -------
    ndarray
        :math:`Z_j(\rho, \theta)` evaluated at each point.
    """
    n, m = noll_to_nm(j)
    m_abs = abs(m)

    R = zernike_radial(n, m_abs, rho)

    # Noll normalization
    if m == 0:
        norm = math.sqrt(n + 1)
    else:
        norm = math.sqrt(2 * (n + 1))

    if m > 0:
        return norm * R * np.cos(m_abs * theta)
    elif m < 0:
        return norm * R * np.sin(m_abs * theta)
    else:
        return norm * R


def evaluate_zernike_opd(
    coeffs: dict[int, float],
    npix: int,
    obscuration_ratio: float = 0.0,
) -> npt.NDArray[np.float64]:
    """Evaluate wavefront OPD from Zernike coefficients on a pupil grid.

    The pupil grid uses the same coordinate convention as
    :func:`radiant.optics.diffraction.make_pupil_amplitude`:
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
