"""IIRS — Infrared Imagery Interpretability Rating Scale.

IIRS extends the NIIRS concept to infrared imagery. For RADIANT v1,
this uses the same GIQE-5 functional form but with IR-specific GSD
and the NEDT-adjusted SNR.

This is a simplified implementation — the full IIRS model involves
additional thermal contrast terms that are out of scope for v1.

See RADIANT_Metrics.md.
"""

from __future__ import annotations

from radiant.performance.giqe import GIQEResult, compute_giqe5


def compute_iirs(
    gsd_m_along: float,
    gsd_m_cross: float,
    rer_along: float,
    rer_cross: float,
    snr: float,
    h: float = 1.0,
    g: float = 1.0,
) -> GIQEResult:
    """Compute IIRS using the GIQE-5 functional form.

    For RADIANT v1, IIRS uses the same formula as GIQE-5. The
    distinction is in the inputs: IR GSD and thermal-contrast SNR.

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
        Signal-to-noise ratio (thermal contrast adjusted for IR).
    h:
        Overshoot parameter.
    g:
        Noise gain from MTF compensation.

    Returns
    -------
    GIQEResult
        IIRS value (via GIQE-5 formula) and supporting data.
    """
    return compute_giqe5(gsd_m_along, gsd_m_cross, rer_along, rer_cross, snr, h, g)
