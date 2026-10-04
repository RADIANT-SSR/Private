"""Point-source detection range — generic signal-model root finder.

Bisects a user-supplied **signal**-vs-range function against the shot-consistent
detection criterion
:func:`~radiant.performance.detection_shot_consistent_snr.shot_consistent_snr`,
returning the range at which SNR equals the detection threshold.

The callback supplies the signal, not the SNR, because the noise is not a
constant of the scene: the target's own shot noise falls with the target
(CU-263).  This module owns the root finding and the criterion evaluation; each
solver that wraps it owns one signal model —
:mod:`radiant.performance.detection_beer_lambert` (constant extinction) and
:mod:`radiant.performance.detection_path_aware` (path-resolved extinction).
"""

from __future__ import annotations

import math
from collections.abc import Callable

from radiant.performance.detection import DetectionRangeResult
from radiant.performance.detection_shot_consistent_snr import shot_consistent_snr

__all__ = ["detection_range_generic"]


#: Relative half-width at which the bisection stops, in addition to the caller's
#: absolute ``tol_m``. 1e-9 is ~30 bisections from any bracket, well inside the
#: default iteration budget, and keeps the reported SNR-at-range at the threshold
#: to the precision the metric is quoted in.
_REL_TOL: float = 1.0e-9


def detection_range_generic(
    signal_at_range_fn: Callable[[float], float],
    noise_floor_e: float,
    snr_threshold: float = 5.0,
    r_min_m: float = 100.0,
    r_max_m: float = 1.0e7,
    tol_m: float = 1.0,
    max_iter: int = 100,
) -> DetectionRangeResult:
    """Range at which ``S(R)/√(S(R) + N₀²)`` falls to *snr_threshold*.

    Parameters
    ----------
    signal_at_range_fn:
        Callable mapping range [m] → signal [e-].  Must be monotonically
        decreasing (or at least cross the threshold once).
    noise_floor_e:
        Target-free noise floor [e- RMS] — every noise term that does *not*
        vanish with the target, from
        :func:`~radiant.performance.detection_noise_floor.target_free_noise_floor_e`.
        Zero for a purely shot-limited chain.
    snr_threshold:
        Required SNR for detection.
    r_min_m:
        Minimum search range [m].
    r_max_m:
        Maximum search range [m].
    tol_m:
        Absolute convergence tolerance [m]. The bracket also stops at a
        *relative* width of ``_REL_TOL`` of the current answer, so precision no
        longer depends on the answer's magnitude: 1 m is a fine tolerance on a
        200 km range and a ~2 % error on a 44 m one, which Gap 136's inward
        solving can return.
    max_iter:
        Maximum bisection iterations.

    Returns
    -------
    DetectionRangeResult
        Result-typed failure (ADR-B; Rule 17 metric-layer carve-out) when the
        target is already below threshold at *r_min_m*, or still above it at
        *r_max_m*.
    """
    if not math.isfinite(noise_floor_e) or noise_floor_e < 0.0:
        return DetectionRangeResult(
            range_m=float("nan"),
            snr_at_range=0.0,
            snr_threshold=snr_threshold,
            iterations=0,
            failure_reason=(
                f"Target-free noise floor = {noise_floor_e} must be a finite "
                "non-negative noise [e- RMS]."
            ),
        )

    def snr_at_range(r: float) -> float:
        return shot_consistent_snr(signal_at_range_fn(r), noise_floor_e)

    snr_lo = snr_at_range(r_min_m)
    snr_hi = snr_at_range(r_max_m)

    if snr_lo < snr_threshold:
        return DetectionRangeResult(
            range_m=float("nan"),
            snr_at_range=snr_lo,
            snr_threshold=snr_threshold,
            iterations=0,
            failure_reason=(
                f"Target not detectable at minimum range {r_min_m:.0f} m: "
                f"SNR = {snr_lo:.2f} < {snr_threshold}."
            ),
        )

    if snr_hi >= snr_threshold:
        return DetectionRangeResult(
            range_m=r_max_m,
            snr_at_range=snr_hi,
            snr_threshold=snr_threshold,
            iterations=0,
            failure_reason=(
                f"Detection range exceeds r_max_m = {r_max_m:.0f} m (SNR at max = {snr_hi:.2f})."
            ),
        )

    r_lo = r_min_m
    r_hi = r_max_m
    n_iter = 0
    for _ in range(max_iter):
        n_iter += 1
        r_mid = 0.5 * (r_lo + r_hi)
        snr_mid = snr_at_range(r_mid)
        if snr_mid > snr_threshold:
            r_lo = r_mid
        else:
            r_hi = r_mid
        # Relative AND absolute: an absolute-only test is as coarse as the answer
        # is small. Measured before this was added — a 44 m answer converged at
        # SNR 4.898 against a 5.0 threshold, a ~2 % miss, while a 200 km answer
        # at the same tol_m is exact to parts per billion. Taking the *stricter*
        # of the two makes precision track the answer's magnitude and can only
        # tighten an existing result, never loosen one: on a multi-Gm range the
        # relative bound is the looser, so `tol_m` still governs there.
        if (r_hi - r_lo) < min(tol_m, _REL_TOL * r_hi):
            break

    r_final = 0.5 * (r_lo + r_hi)
    snr_final = snr_at_range(r_final)

    return DetectionRangeResult(
        range_m=r_final,
        snr_at_range=snr_final,
        snr_threshold=snr_threshold,
        iterations=n_iter,
    )
