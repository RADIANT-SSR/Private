"""NEDL — Noise-Equivalent Differential Radiance.

Implements §4.3 of ``docs/RADIANT_Metrics.md``::

    NEDL = L / SNR  [W/m²/sr/µm]
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class NEDLResult:
    """Result of an NEDL computation.

    Parameters
    ----------
    value:
        NEDL [W/m²/sr/µm]. ``float('nan')`` on failure.
    radiance:
        Signal radiance [W/m²/sr/µm].
    snr:
        Signal-to-noise ratio.
    failure_reason:
        ``None`` on success.
    """

    value: float
    radiance: float
    snr: float
    failure_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.failure_reason is None and math.isfinite(self.value)


def compute_nedl(radiance: float, snr: float) -> NEDLResult:
    """Compute NEDL = L / SNR.

    Parameters
    ----------
    radiance:
        In-band radiance [W/m²/sr/µm]. Must be > 0.
    snr:
        Signal-to-noise ratio. Must be > 0 and finite.
    """
    if radiance <= 0.0:
        return NEDLResult(
            value=float("nan"),
            radiance=radiance,
            snr=snr,
            failure_reason=f"Radiance = {radiance} must be > 0.",
        )
    if not math.isfinite(snr) or snr <= 0.0:
        return NEDLResult(
            value=float("nan"),
            radiance=radiance,
            snr=snr,
            failure_reason=f"SNR = {snr} must be positive and finite.",
        )
    return NEDLResult(value=radiance / snr, radiance=radiance, snr=snr)
