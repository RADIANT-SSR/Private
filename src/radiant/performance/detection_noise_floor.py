"""Target-free noise floor — the part of the noise that does not vanish with the target.

One computation, one module (Rule 19).  A detection-range solve extrapolates the
signal away from the range at which the chain measured it, so it needs to know
which part of the measured noise travels with the target and which part stays put.

For a Poisson detection chain the total variance at the reference range splits
exactly two ways:

.. math:: \\sigma_{ref}^2 = S_{ref} + N_0^2

The first term is the target's **own** shot variance — in electrons it *is* the
signal, which is why it falls as the target dims.  Everything else — background
shot, dark, read, kTC, quantisation, clutter — is the range-independent floor
:math:`N_0`.  RADIANT's readout stage scales signal and its shot term together
through TDI and on-chip binning, so the identity holds after those, not only per
pixel (verified against the chain's own ``signal_shot`` term in CU-263).

This module owns that decomposition and nothing else; the criterion built on top
of it lives in :mod:`radiant.performance.detection_shot_consistent_snr`.
"""

from __future__ import annotations

import math

from radiant.performance.errors import PerformanceValidationError

__all__ = ["target_free_noise_floor_e"]


def target_free_noise_floor_e(total_noise_e: float, signal_e: float) -> float:
    """The target-free noise floor :math:`N_0 = \\sqrt{\\sigma^2 - S}` [e- RMS].

    Parameters
    ----------
    total_noise_e:
        Total noise measured at the reference range [e- RMS], > 0.  This is the
        RSS of every noise term, the target's own shot noise included.
    signal_e:
        Signal at the same reference range [e-], >= 0.  Its shot variance in
        electrons² is numerically equal to it.

    Returns
    -------
    float
        The range-independent noise floor [e- RMS].  Zero for a purely
        shot-limited chain.

    Raises
    ------
    PerformanceValidationError
        If either argument is non-finite or out of range, or if the signal
        exceeds the total variance — that is an inconsistent noise budget, not
        a decomposition, and silently clamping it would hide the inconsistency
        (Rule 17).
    """
    if not math.isfinite(total_noise_e) or total_noise_e <= 0.0:
        raise PerformanceValidationError(
            f"target_free_noise_floor_e: total_noise_e = {total_noise_e} must be a "
            "finite positive noise [e- RMS]."
        )
    if not math.isfinite(signal_e) or signal_e < 0.0:
        raise PerformanceValidationError(
            f"target_free_noise_floor_e: signal_e = {signal_e} must be a finite "
            "non-negative signal [e-]."
        )
    floor_variance = total_noise_e * total_noise_e - signal_e
    if floor_variance < 0.0:
        raise PerformanceValidationError(
            f"target_free_noise_floor_e: signal_e = {signal_e} e- exceeds the total "
            f"noise variance {total_noise_e * total_noise_e} e-^2 (total_noise_e = "
            f"{total_noise_e} e- RMS), so sigma^2 = S + N0^2 has no non-negative "
            "solution for N0. The signal and the noise budget come from different "
            "operating points, or the budget omits the target's own shot term. Pass "
            "the total noise and the signal from the same chain evaluation."
        )
    return math.sqrt(floor_variance)
