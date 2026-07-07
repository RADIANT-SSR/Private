"""NEDR — Noise-Equivalent Reflectance Difference.

Implements §4.4 of ``docs/architecture/RADIANT_Metrics.md``::

    NEΔρ = ρ / SNR  [dimensionless]
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class NEDRResult:
    """Result of an NEDR (NEΔρ) computation.

    Parameters
    ----------
    value:
        Noise-equivalent reflectance difference [dimensionless].
    reflectance:
        Target reflectance (fractional).
    snr:
        Signal-to-noise ratio.
    failure_reason:
        ``None`` on success.
    """

    value: float
    reflectance: float
    snr: float
    failure_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.failure_reason is None and math.isfinite(self.value)


def compute_nedr(reflectance: float, snr: float) -> NEDRResult:
    """Compute NEΔρ = ρ / SNR.

    Parameters
    ----------
    reflectance:
        Target reflectance (0, 1]. Must be > 0.
    snr:
        Signal-to-noise ratio. Must be > 0 and finite.
    """
    if reflectance <= 0.0:
        return NEDRResult(
            value=float("nan"),
            reflectance=reflectance,
            snr=snr,
            failure_reason=f"Reflectance = {reflectance} must be > 0.",
        )
    if not math.isfinite(snr) or snr <= 0.0:
        return NEDRResult(
            value=float("nan"),
            reflectance=reflectance,
            snr=snr,
            failure_reason=f"SNR = {snr} must be positive and finite.",
        )
    return NEDRResult(value=reflectance / snr, reflectance=reflectance, snr=snr)
