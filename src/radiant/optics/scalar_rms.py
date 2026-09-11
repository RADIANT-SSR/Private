"""Scalar-RMS WFE → deterministic low-order Zernike expansion (CU-355).

A ``scalar_rms`` wavefront-error budget carries one number: the RMS OPD in
waves at the reference wavelength. Real fabrication/alignment WFE is
dominated by low-order aberrations, so the budget is expanded over the
eight image-degrading low-order Noll terms Z4–Z11 (defocus, astigmatism
×2, coma ×2, trefoil ×2, primary spherical) with **equal RMS per term** —
the honest reading of a one-number input. Piston/tip/tilt (Z1–Z3) are
excluded: they shift or offset the image without degrading it.

The expansion is fully deterministic — the coefficients are a fixed,
documented constant set (all positive, equal magnitude), not a realization
of a random process. Noll normalization makes each term unit-RMS on the
unobscured unit disk, so ``c_j = rms / sqrt(8)`` gives a total
piston-removed pupil RMS of exactly ``rms`` there. On an annular pupil the
standard Zernikes lose orthonormality, so the set is renormalized
numerically (on a fixed internal quadrature grid, independent of the
caller's pupil sampling) to make the realized piston-removed RMS over the
transmitting annulus equal the budget.

Replaces the pre-CU-355 per-pixel white-noise phase screen, whose variance
sat entirely at the pupil-grid sample scale — scattering energy into a far
halo (wrong in-band MTF shape) with a correlation length set by
``pupil_npix`` (a discretization artifact), and which ignored the
reference wavelength entirely.

See RADIANT_Optics.md §4 and RADIANT_Spatial_Complete.md §3.3.
"""

from __future__ import annotations

import math
import warnings
from functools import lru_cache

import numpy as np

from radiant.optics.errors import OpticsValidationError
from radiant.optics.zernike_opd import evaluate_zernike_opd

#: The fixed low-order term set (Noll indices) the scalar budget spans.
SCALAR_RMS_NOLL_TERMS: tuple[int, ...] = (4, 5, 6, 7, 8, 9, 10, 11)

# Fixed quadrature grid for the annular renormalization — deliberately
# independent of the caller's pupil sampling so the returned coefficients
# depend only on (rms_waves, obscuration_ratio) and both Rule 4 paths get
# identical values regardless of their grid sizes.
_NORMALIZATION_NPIX = 512


@lru_cache(maxsize=64)
def _unit_budget_pupil_rms(obscuration_ratio: float) -> float:
    """Realized piston-removed pupil RMS of the unit-budget set.

    Evaluates the equal-coefficient set with ``sum(c^2) = 1`` on the
    (possibly obscured) pupil and returns its piston-removed RMS over the
    transmitting region. Exactly 1.0 on the unobscured disk (up to grid
    sampling error); drifts from 1.0 on an annulus, where standard
    Zernikes are not orthonormal.
    """
    c = 1.0 / math.sqrt(len(SCALAR_RMS_NOLL_TERMS))
    coeffs = dict.fromkeys(SCALAR_RMS_NOLL_TERMS, c)
    with warnings.catch_warnings():
        # This internal pass would duplicate evaluate_zernike_opd's
        # annular-orthogonality warning; the actual pupil-phase evaluation
        # downstream still emits it once for the user.
        warnings.simplefilter("ignore", UserWarning)
        opd = evaluate_zernike_opd(coeffs, _NORMALIZATION_NPIX, obscuration_ratio)
        # Canonical pupil mask via the piston polynomial: 1 inside, 0 outside.
        mask = evaluate_zernike_opd({1: 1.0}, _NORMALIZATION_NPIX, obscuration_ratio) > 0.5
    return float(np.std(opd[mask]))


def scalar_rms_zernike_coeffs(rms_waves: float, obscuration_ratio: float = 0.0) -> dict[int, float]:
    """Expand a scalar RMS WFE budget into Noll Zernike coefficients.

    Parameters
    ----------
    rms_waves:
        Piston-removed RMS wavefront error budget in waves (at the
        reference wavelength of the owning
        :class:`~radiant.optics.wavefront.WavefrontError`).
    obscuration_ratio:
        Central obscuration ratio D_sec / D_pri, in [0, 1). The set is
        renormalized so the realized RMS over the annulus equals the budget.

    Returns
    -------
    dict[int, float]
        Noll-indexed coefficients in waves, equal magnitude across
        ``SCALAR_RMS_NOLL_TERMS``; empty for a zero budget.
    """
    if rms_waves < 0.0:
        raise OpticsValidationError(
            f"scalar_rms_zernike_coeffs: rms_waves must be >= 0, got {rms_waves}. "
            f"An RMS wavefront error is a magnitude; set optics.wfe_rms_waves >= 0."
        )
    if rms_waves == 0.0:
        return {}

    scale = rms_waves / _unit_budget_pupil_rms(obscuration_ratio)
    c = scale / math.sqrt(len(SCALAR_RMS_NOLL_TERMS))
    return dict.fromkeys(SCALAR_RMS_NOLL_TERMS, c)
