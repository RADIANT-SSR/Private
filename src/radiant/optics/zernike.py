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
    if m < 0:
        return norm * R * np.sin(m_abs * theta)
    return norm * R


