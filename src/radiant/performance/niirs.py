"""NIIRS dispatcher — routes to GIQE-5 or IIRS based on band.

See RADIANT_Metrics.md §4.6.
"""

from __future__ import annotations

from radiant.performance.giqe import GIQEResult, compute_giqe5
from radiant.performance.iirs import compute_iirs


def compute_niirs(
    gsd_m_along: float,
    gsd_m_cross: float,
    rer_along: float,
    rer_cross: float,
    snr: float,
    band: str = "vis",
    h: float = 1.0,
    g: float = 1.0,
) -> GIQEResult:
    """Compute NIIRS or IIRS based on spectral band.

    Parameters
    ----------
    gsd_m_along:
        GSD along-track [m].
    gsd_m_cross:
        GSD cross-track [m].
    rer_along:
        Relative edge response along-track.
    rer_cross:
        Relative edge response cross-track.
    snr:
        Signal-to-noise ratio.
    band:
        Spectral band: ``"vis"`` or ``"nir"`` for GIQE-5,
        ``"mwir"`` or ``"lwir"`` for IIRS.
    h:
        Overshoot parameter.
    g:
        Noise gain from MTF compensation.

    Returns
    -------
    GIQEResult
        NIIRS/IIRS value and supporting data.
    """
    if band in ("mwir", "lwir"):
        return compute_iirs(gsd_m_along, gsd_m_cross, rer_along, rer_cross, snr, h, g)
    return compute_giqe5(gsd_m_along, gsd_m_cross, rer_along, rer_cross, snr, h, g)
