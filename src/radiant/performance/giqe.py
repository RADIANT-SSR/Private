"""GIQE-5 (General Image Quality Equation, version 5).

Computes NIIRS from GSD, RER, SNR, and optional MTF compensation
parameters (H, G).

NIIRS = c0 + c1·log10(GSD_inch) + c2·log10(RER) + c3·log10(SNR)
            + c4·H + c5·G

Coefficients from:
  Leachtenauer, J.C. et al., "General Image-Quality Equation: GIQE,"
  Applied Optics, Vol. 36, No. 32, 1997, pp. 8322-8328.
  Updated GIQE-5 coefficients per standard practice.

See RADIANT_Metrics.md §4.6.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# GIQE-5 coefficients (published).
C0 = 9.57
C1 = -3.32
C2 = 3.32
C3 = 1.559
C4 = -0.334
C5 = -0.01


@dataclass(frozen=True)
class GIQEResult:
    """Result of a GIQE-5 computation.

    Parameters
    ----------
    niirs:
        Predicted NIIRS value.
    gsd_inch:
        Geometric mean GSD in inches (input to formula).
    rer:
        Geometric mean RER (input to formula).
    snr:
        Signal-to-noise ratio (input to formula).
    h:
        Overshoot parameter.
    g:
        Noise gain from MTF compensation.
    warnings:
        Any warnings about input validity.
    """

    niirs: float
    gsd_inch: float
    rer: float
    snr: float
    h: float
    g: float
    warnings: tuple[str, ...]


def compute_giqe5(
    gsd_m_along: float,
    gsd_m_cross: float,
    rer_along: float,
    rer_cross: float,
    snr: float,
    h: float = 1.0,
    g: float = 1.0,
) -> GIQEResult:
    """Compute NIIRS via GIQE-5.

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
    h:
        Overshoot parameter (default 1.0 = no MTFC).
    g:
        Noise gain from MTF compensation (default 1.0).

    Returns
    -------
    GIQEResult
        NIIRS and supporting data.

    Raises
    ------
    ValueError
        If GSD, RER, or SNR are non-positive.
    """
    warnings: list[str] = []

    if gsd_m_along <= 0.0 or gsd_m_cross <= 0.0:
        raise ValueError(f"GSD must be positive, got along={gsd_m_along}, cross={gsd_m_cross}")
    if snr <= 0.0:
        raise ValueError(f"SNR must be positive, got {snr}")

    # Geometric mean GSD in inches.
    gsd_geom_m = math.sqrt(gsd_m_along * gsd_m_cross)
    gsd_inch = gsd_geom_m * 39.37  # m → inches

    # Geometric mean RER.
    if rer_along <= 0.0 or rer_cross <= 0.0:
        raise ValueError(f"RER must be positive, got along={rer_along}, cross={rer_cross}")
    rer = math.sqrt(rer_along * rer_cross)

    # Validity warnings.
    if snr < 5.0:
        warnings.append("SNR below GIQE-5 calibration range (SNR < 5)")
        logger.warning("SNR = %.1f is below GIQE-5 calibration range", snr)

    if rer < 0.2:
        warnings.append("RER below GIQE-5 calibration range (RER < 0.2)")
        logger.warning("RER = %.3f is below GIQE-5 calibration range", rer)

    # GIQE-5 formula.
    niirs = (
        C0
        + C1 * math.log10(gsd_inch)
        + C2 * math.log10(rer)
        + C3 * math.log10(snr)
        + C4 * h
        + C5 * g
    )

    return GIQEResult(
        niirs=niirs,
        gsd_inch=gsd_inch,
        rer=rer,
        snr=snr,
        h=h,
        g=g,
        warnings=tuple(warnings),
    )
