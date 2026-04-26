"""Circular pupil amplitude mask generation.

Generates the binary amplitude function ``A(x, y)`` for a circular
aperture with optional central obscuration.  The mask is centered on
a square grid with normalised coordinates ``[-0.5, +0.5]``.

See RADIANT_Spatial_Complete.md section 3.1.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


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
        raise ValueError(f"obscuration_ratio must be in [0, 1), got {obscuration_ratio}")

    # Normalised coordinates: [-0.5, +0.5]
    x = np.linspace(-0.5, 0.5, npix, endpoint=False) + 0.5 / npix
    xx, yy = np.meshgrid(x, x, indexing="xy")
    r = np.sqrt(xx**2 + yy**2)

    mask = np.zeros((npix, npix), dtype=np.float64)
    mask[r <= 0.5] = 1.0
    if obscuration_ratio > 0.0:
        mask[r <= 0.5 * obscuration_ratio] = 0.0

    return mask
