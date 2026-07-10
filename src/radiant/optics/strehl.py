"""Strehl ratio from PSF peak comparison.

Computes the Strehl ratio as the ratio of the aberrated PSF peak
to the diffraction-limited reference PSF peak.

See also ``wavefront.py`` for the Marechal Strehl approximation.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from radiant.optics.errors import OpticsValidationError


def compute_strehl(psf: npt.NDArray[np.float64], psf_ref: npt.NDArray[np.float64]) -> float:
    """Compute the Strehl ratio.

    Parameters
    ----------
    psf:
        Aberrated PSF (unit-volume normalised).
    psf_ref:
        Diffraction-limited reference PSF (unit-volume normalised,
        same grid).

    Returns
    -------
    float
        Strehl ratio = peak(psf) / peak(psf_ref).
    """
    ref_peak = psf_ref.max()
    if ref_peak == 0.0:
        raise OpticsValidationError("Reference PSF peak is zero — cannot compute Strehl.")
    return float(psf.max() / ref_peak)
