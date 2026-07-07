"""Point-source detection range — shared types and re-exports.

Implements §4.12 of ``docs/architecture/RADIANT_Metrics.md``.

Individual solvers have been moved to their own modules (Rule 19):
- ``detection_beer_lambert.py`` — Beer-Lambert atmosphere model
- ``detection_generic.py`` — generic callback-based solver
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class DetectionRangeResult:
    """Result of a detection range computation.

    Parameters
    ----------
    range_m:
        Detection range [m]. ``float('nan')`` on failure.
    snr_at_range:
        SNR at the computed range (should be ≈ threshold).
    snr_threshold:
        Detection threshold used.
    iterations:
        Number of bisection iterations.
    failure_reason:
        ``None`` on success.
    """

    range_m: float
    snr_at_range: float
    snr_threshold: float
    iterations: int
    failure_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.failure_reason is None and math.isfinite(self.range_m)
