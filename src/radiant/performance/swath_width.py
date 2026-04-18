"""Swath width — ground footprint of the detector cross-track extent.

    swath = n_pixels_cross × GSD_cross
"""

from __future__ import annotations


def compute_swath_width_m(gsd_cross_m: float, n_pixels_cross: int) -> float:
    """Swath width at ground [m].

    Parameters
    ----------
    gsd_cross_m : float
        Cross-track ground sample distance [m].
    n_pixels_cross : int
        Number of detector pixels in the cross-track direction.

    Returns
    -------
    float
        Swath width in meters.
    """
    return gsd_cross_m * n_pixels_cross
