"""Shot-consistent detection criterion — SNR(S) = S/√(S + N₀²) and its inverse.

One computation, one module (Rule 19).  This module owns the criterion the
detection-range solvers root-find on, in both directions:

* the **forward** model :func:`shot_consistent_snr` — the SNR a signal *S*
  achieves against a target-free floor :math:`N_0`
  (:mod:`radiant.performance.detection_noise_floor`);
* its **analytic inverse** :func:`threshold_signal_e` — the signal a detection
  threshold *T* demands.

The two are one model expressed twice, not two computations: the inverse is
meaningless without the forward criterion it inverts, and every solver that uses
one uses the other (the inverse supplies the analytic search bound, the forward
supplies the value the bisection compares).  Keeping them apart would fork one
definition across two files, which Rule 19's coupling clause exists to prevent.

Why the criterion is shot-consistent
------------------------------------
The shipped solvers held the *total* noise at its reference-range value while
scaling the signal outward, which made the reported detection range depend on
the range it was evaluated from — 123.4 km referenced at 25 km versus 182.5 km
referenced at 100 km for one unchanged configuration (CU-263).  The target's own
shot noise is not a constant of the scene: it falls with the target.  Writing the
variance as :math:`\\sigma^2(R) = S(R) + N_0^2` removes the reference range from
the answer entirely — the criterion depends only on the signal at the range being
tested and on a floor that is, by construction, target-free.

Both forms agree exactly at the reference range (:math:`\\sigma_{ref}^2 = S_{ref}
+ N_0^2` is the definition of :math:`N_0`), so the correction is zero there and
grows outward; it always *lengthens* the reported range, and vanishes as
:math:`S_{ref}/N_0^2 \\to 0` (a background-limited chain, where freezing the
noise was exact all along).

Closed form
-----------
Solving :math:`S/\\sqrt{S + N_0^2} = T` for *S* gives the positive root of
:math:`S^2 - T^2 S - T^2 N_0^2 = 0`:

.. math:: S^* = \\tfrac{1}{2}\\left(T^2 + \\sqrt{T^4 + 4 T^2 N_0^2}\\right)

evaluated here as :math:`\\tfrac{1}{2}T\\,(T + \\mathrm{hypot}(T, 2N_0))`, which
is the same quantity without forming :math:`T^4`.
"""

from __future__ import annotations

import math

from radiant.performance.errors import PerformanceValidationError

__all__ = ["shot_consistent_snr", "threshold_signal_e"]


def _validate_floor(noise_floor_e: float, caller: str) -> None:
    if not math.isfinite(noise_floor_e) or noise_floor_e < 0.0:
        raise PerformanceValidationError(
            f"{caller}: noise_floor_e = {noise_floor_e} must be a finite non-negative "
            "target-free noise floor [e- RMS] (see detection_noise_floor)."
        )


def shot_consistent_snr(signal_e: float, noise_floor_e: float) -> float:
    """SNR of *signal_e* against a target-free floor, with the target's own shot noise.

    Parameters
    ----------
    signal_e:
        Signal at the range under test [e-], >= 0.
    noise_floor_e:
        Target-free noise floor [e- RMS], >= 0.

    Returns
    -------
    float
        :math:`S/\\sqrt{S + N_0^2}` [dimensionless].

    Raises
    ------
    PerformanceValidationError
        On non-finite or negative inputs, or when both are zero (0/0 — an
        undefined criterion, not a zero SNR).
    """
    if not math.isfinite(signal_e) or signal_e < 0.0:
        raise PerformanceValidationError(
            f"shot_consistent_snr: signal_e = {signal_e} must be a finite non-negative signal [e-]."
        )
    _validate_floor(noise_floor_e, "shot_consistent_snr")
    variance = signal_e + noise_floor_e * noise_floor_e
    if variance <= 0.0:
        raise PerformanceValidationError(
            "shot_consistent_snr: signal_e = 0 e- and noise_floor_e = 0 e- RMS leave "
            "the criterion S/sqrt(S + N0^2) undefined (0/0). A noiseless, signal-free "
            "chain has no detection threshold to solve against."
        )
    return signal_e / math.sqrt(variance)


def threshold_signal_e(snr_threshold: float, noise_floor_e: float) -> float:
    """Signal required to reach *snr_threshold* against a target-free floor [e-].

    The analytic inverse of :func:`shot_consistent_snr`.

    Parameters
    ----------
    snr_threshold:
        Detection threshold *T* [dimensionless], > 0.
    noise_floor_e:
        Target-free noise floor [e- RMS], >= 0.

    Returns
    -------
    float
        :math:`S^* = \\tfrac{1}{2}(T^2 + \\sqrt{T^4 + 4T^2N_0^2})` [e-].  Equals
        :math:`T^2` for a shot-limited chain and tends to :math:`T N_0` when the
        floor dominates.

    Raises
    ------
    PerformanceValidationError
        On a non-positive or non-finite threshold, or a non-physical floor.
    """
    if not math.isfinite(snr_threshold) or snr_threshold <= 0.0:
        raise PerformanceValidationError(
            f"threshold_signal_e: snr_threshold = {snr_threshold} must be a finite positive SNR."
        )
    _validate_floor(noise_floor_e, "threshold_signal_e")
    return 0.5 * snr_threshold * (snr_threshold + math.hypot(snr_threshold, 2.0 * noise_floor_e))
