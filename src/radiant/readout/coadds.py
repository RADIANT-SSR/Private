"""Coadd modes — sum, average, median.

Per ``docs/architecture/RADIANT_Detector_Complete.md`` §9:

| Mode    | Signal      | Temporal noise | FPN         |
|---------|-------------|----------------|-------------|
| SUM     | × K         | × √K           | × K         |
| AVERAGE | unchanged   | / √K           | unchanged   |
| MEDIAN  | unchanged   | × √(π/(2K))    | unchanged   |

The median noise factor ``√(π/(2K))`` is the asymptotic efficiency
of the sample median relative to the sample mean for Gaussian noise.
"""

from __future__ import annotations

import enum
import math

from radiant.readout.errors import ReadoutValidationError


class CoaddMode(enum.Enum):
    """Coadd combination modes."""

    SUM = "sum"
    AVERAGE = "average"
    MEDIAN = "median"


def _validate_k(n_coadds: int) -> None:
    if n_coadds < 1:
        raise ReadoutValidationError(f"n_coadds = {n_coadds} must be >= 1.")


def coadd_scale_signal(signal: float, n_coadds: int, mode: CoaddMode) -> float:
    """Scale signal for the given coadd mode and count.

    SUM: × K. AVERAGE/MEDIAN: unchanged (reported as per-frame).
    """
    _validate_k(n_coadds)
    if mode == CoaddMode.SUM:
        return signal * n_coadds
    return signal


def coadd_scale_temporal_noise(
    noise_e: float,
    n_coadds: int,
    mode: CoaddMode,
) -> float:
    """Scale temporal noise for the given coadd mode.

    SUM: × √K.  AVERAGE: / √K.  MEDIAN: × √(π/(2K)).
    """
    _validate_k(n_coadds)
    if n_coadds == 1:
        return noise_e
    if mode == CoaddMode.SUM:
        return noise_e * math.sqrt(n_coadds)
    if mode == CoaddMode.AVERAGE:
        return noise_e / math.sqrt(n_coadds)
    # MEDIAN: for K=2, median = average, so use average scaling.
    # For K >= 3, use asymptotic factor √(π/(2K)).
    if n_coadds == 2:
        return noise_e / math.sqrt(2.0)
    return noise_e * math.sqrt(math.pi / (2.0 * n_coadds))


def coadd_scale_fpn(
    noise_e: float,
    n_coadds: int,
    mode: CoaddMode,
) -> float:
    """Scale fixed-pattern noise for the given coadd mode.

    SUM: × K (FPN is the same systematic in every frame).
    AVERAGE/MEDIAN: unchanged (FPN is correlated, doesn't average down).
    """
    _validate_k(n_coadds)
    if mode == CoaddMode.SUM:
        return noise_e * n_coadds
    return noise_e
