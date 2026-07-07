"""GIQE-5 sensitivity — analytic partial derivatives d(NIIRS)/d(input).

For the GIQE-5 form used in ``giqe.py``:

    NIIRS = c0 + c1·log10(GSD_inch) + c2·log10(RER) + c3·log10(SNR)
                + c4·H + c5·G

the partials are analytic:

    d(NIIRS)/d(GSD) = c1 / (GSD · ln 10)     [per meter or per inch —
                                              same form, GSD in the unit
                                              of the argument]
    d(NIIRS)/d(RER) = c2 / (RER · ln 10)
    d(NIIRS)/d(SNR) = c3 / (SNR · ln 10)
    d(NIIRS)/d(H)   = c4
    d(NIIRS)/d(G)   = c5

Note the log-argument unit cancels in the derivative's *form*: only the
unit of the increment matters (a derivative per meter of GSD uses GSD in
meters). See RADIANT_Metrics.md §4.6.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from radiant.core.exceptions import RadiantError
from radiant.performance.giqe import C1, C2, C3, C4, C5

_LN10 = math.log(10.0)


class GIQESensitivityError(RadiantError):
    """Raised when sensitivity inputs are outside the differentiable domain."""


@dataclass(frozen=True)
class GIQESensitivity:
    """Analytic GIQE-5 partial derivatives at an operating point.

    Attributes
    ----------
    dniirs_dgsd_per_m:
        d(NIIRS)/d(GSD) [1/m], GSD as geometric-mean ground sample
        distance in meters. Negative — larger GSD lowers NIIRS.
    dniirs_drer:
        d(NIIRS)/d(RER) [dimensionless]. Positive and steep at low RER.
    dniirs_dsnr:
        d(NIIRS)/d(SNR) [dimensionless].
    dniirs_dh:
        d(NIIRS)/d(H) — constant ``c4``.
    dniirs_dg:
        d(NIIRS)/d(G) — constant ``c5``.
    per_percent:
        dict mapping input name to the exact NIIRS change for a +1%
        change of that input (log terms: ``c·log10(1.01)``; linear
        terms: ``c·0.01·value``).
    """

    dniirs_dgsd_per_m: float
    dniirs_drer: float
    dniirs_dsnr: float
    dniirs_dh: float
    dniirs_dg: float
    per_percent: dict[str, float]


def giqe5_sensitivity(
    gsd_m: float,
    rer: float,
    snr: float,
    h: float = 1.0,
    g: float = 1.0,
) -> GIQESensitivity:
    """Analytic GIQE-5 sensitivities at the given operating point.

    Parameters
    ----------
    gsd_m:
        Geometric-mean GSD [m]. Must be positive.
    rer:
        Geometric-mean relative edge response. Must be positive.
    snr:
        Signal-to-noise ratio. Must be positive.
    h:
        Overshoot parameter (linear term).
    g:
        Noise gain from MTF compensation (linear term).

    Returns
    -------
    GIQESensitivity
        Partial derivatives and exact per-+1% NIIRS deltas.

    Raises
    ------
    GIQESensitivityError
        If any log-term input is non-positive (derivative undefined).
    """
    for label, value in (("gsd_m", gsd_m), ("rer", rer), ("snr", snr)):
        if value <= 0.0:
            raise GIQESensitivityError(
                f"giqe5_sensitivity: {label} = {value} must be positive — "
                "the GIQE-5 log terms are undefined at or below zero. "
                f"Provide a positive {label} at the operating point."
            )

    log_1p01 = math.log10(1.01)
    return GIQESensitivity(
        dniirs_dgsd_per_m=C1 / (gsd_m * _LN10),
        dniirs_drer=C2 / (rer * _LN10),
        dniirs_dsnr=C3 / (snr * _LN10),
        dniirs_dh=C4,
        dniirs_dg=C5,
        per_percent={
            "gsd": C1 * log_1p01,
            "rer": C2 * log_1p01,
            "snr": C3 * log_1p01,
            "h": C4 * 0.01 * h,
            "g": C5 * 0.01 * g,
        },
    )
