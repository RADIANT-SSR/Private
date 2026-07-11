"""Bin-average resampling from RADIS's native fine grid to the output grid.

RADIS computes on a line-width-limited fine grid (often << 1 cm-1
spacing) to resolve individual HITRAN lines accurately; the CSV's
declared output resolution (dv_cm1/fwhm_cm1, typically 1.0 cm-1)
matches a MODTRAN "SCN" slit-convolved file, not the raw per-line
grid. Bin-averaging transmittance into the coarser output grid is a
boxcar-slit approximation of that convolution -- simpler than
MODTRAN's usual triangular slit, but adequate for a synthetic dataset
and it keeps memory bounded (every layer/species is resampled down
immediately after computing it, never held at full fine-grid
resolution simultaneously).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import binned_statistic


def bin_average_transmittance(
    w_fine_cm1: np.ndarray,
    transmittance_fine: np.ndarray,
    v1_cm1: float,
    v2_cm1: float,
    dv_cm1: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (w_grid, transmittance_grid) on a uniform ascending grid.

    ``w_grid`` are bin centres spaced by ``dv_cm1`` from ``v1_cm1`` to
    ``v2_cm1``. Empty bins (no fine-grid samples -- only possible if
    the fine grid is coarser than dv_cm1, which should not happen
    given RADIS's line-width-limited grid) are filled by linear
    interpolation from neighbouring bins.
    """
    n_bins = int(round((v2_cm1 - v1_cm1) / dv_cm1))
    edges = v1_cm1 + dv_cm1 * np.arange(n_bins + 1)
    centres = (edges[:-1] + edges[1:]) / 2.0

    means, _, _ = binned_statistic(w_fine_cm1, transmittance_fine, statistic="mean", bins=edges)
    nan_mask = np.isnan(means)
    if np.any(nan_mask) and not np.all(nan_mask):
        means[nan_mask] = np.interp(centres[nan_mask], centres[~nan_mask], means[~nan_mask])
    elif np.all(nan_mask):
        means[:] = 1.0  # no fine-grid coverage at all in this band -> transparent
    return centres, means
