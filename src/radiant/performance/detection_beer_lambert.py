"""Point-source detection range — Beer-Lambert atmosphere model.

Implements §4.12 of ``docs/architecture/RADIANT_Metrics.md``.  Owns one signal
model::

    S(R) = S_ref · (R_ref / R)² · exp(−α · (R − R_ref))

and delegates the root finding and the detection criterion to
:func:`~radiant.performance.detection_generic.detection_range_generic`, so this
module and :mod:`radiant.performance.detection_path_aware` cannot drift apart in
how they define detection (Rule 19: one computation, one module — this one is
the constant-extinction *signal law*).

The criterion is shot-consistent (CU-263): the noise at range *R* is
:math:`\\sqrt{S(R) + N_0^2}` with :math:`N_0` the target-free floor derived from
the reference-range pair ``(noise_e, signal_e_at_ref)``, not the frozen
``noise_e``.  Freezing it made the answer depend on the range it was evaluated
from.

See also ``detection_generic.py`` for the solver and ``detection_noise_floor.py``
for the decomposition.
"""

from __future__ import annotations

import math

from radiant.performance.detection import DetectionRangeResult
from radiant.performance.detection_generic import detection_range_generic
from radiant.performance.detection_noise_floor import target_free_noise_floor_e

__all__ = ["detection_range_beer_lambert"]


def detection_range_beer_lambert(
    signal_e_at_ref: float,
    noise_e: float,
    ref_range_m: float,
    extinction_coeff: float,
    snr_threshold: float = 5.0,
    max_range_m: float = 1.0e7,
    tol_m: float = 1.0,
    max_iter: int = 100,
) -> DetectionRangeResult:
    """Compute point-source detection range using Beer-Lambert atmosphere.

    The signal at range R is::

        S(R) = S_ref · (R_ref / R)² · exp(−α · (R − R_ref))

    and detection occurs when ``S(R) / √(S(R) + N₀²) = snr_threshold``, with
    ``N₀² = noise_e² − signal_e_at_ref`` the target-free noise floor.

    Parameters
    ----------
    signal_e_at_ref:
        Signal electrons at the reference range [e-].
    noise_e:
        Total noise at the reference range [e- RMS], the target's own shot term
        included. Must be > 0.
    ref_range_m:
        Reference range at which signal_e_at_ref was computed [m].
    extinction_coeff:
        Atmospheric extinction coefficient α [1/m]. 0 = no atmosphere.
    snr_threshold:
        Required SNR for detection (default 5.0).
    max_range_m:
        Maximum search range [m] (default 10,000 km).
    tol_m:
        Convergence tolerance [m] (default 1 m).
    max_iter:
        Maximum bisection iterations (default 100).
    """
    if signal_e_at_ref <= 0.0:
        return DetectionRangeResult(
            range_m=float("nan"),
            snr_at_range=0.0,
            snr_threshold=snr_threshold,
            iterations=0,
            failure_reason=f"Signal at reference = {signal_e_at_ref} must be > 0.",
        )
    if noise_e <= 0.0:
        return DetectionRangeResult(
            range_m=float("nan"),
            snr_at_range=0.0,
            snr_threshold=snr_threshold,
            iterations=0,
            failure_reason=f"Noise = {noise_e} must be > 0.",
        )
    if ref_range_m <= 0.0:
        return DetectionRangeResult(
            range_m=float("nan"),
            snr_at_range=0.0,
            snr_threshold=snr_threshold,
            iterations=0,
            failure_reason=f"Reference range = {ref_range_m} must be > 0.",
        )
    if extinction_coeff < 0.0:
        return DetectionRangeResult(
            range_m=float("nan"),
            snr_at_range=0.0,
            snr_threshold=snr_threshold,
            iterations=0,
            failure_reason=f"Extinction coefficient = {extinction_coeff} must be >= 0.",
        )
    if noise_e * noise_e < signal_e_at_ref:
        return DetectionRangeResult(
            range_m=float("nan"),
            snr_at_range=0.0,
            snr_threshold=snr_threshold,
            iterations=0,
            failure_reason=(
                f"Signal at reference = {signal_e_at_ref} e- exceeds the total noise "
                f"variance {noise_e * noise_e} e-^2, so the target-free noise floor "
                "N0^2 = noise_e^2 - signal_e_at_ref is negative. Pass the signal and "
                "the total noise from the same chain evaluation."
            ),
        )

    noise_floor_e = target_free_noise_floor_e(noise_e, signal_e_at_ref)

    def signal_at_range(r: float) -> float:
        """Signal at range r [m], in electrons."""
        range_factor = (ref_range_m / r) ** 2
        atm_factor = math.exp(-extinction_coeff * (r - ref_range_m))
        return signal_e_at_ref * range_factor * atm_factor

    return detection_range_generic(
        signal_at_range_fn=signal_at_range,
        noise_floor_e=noise_floor_e,
        snr_threshold=snr_threshold,
        r_min_m=ref_range_m,
        r_max_m=max_range_m,
        tol_m=tol_m,
        max_iter=max_iter,
    )
