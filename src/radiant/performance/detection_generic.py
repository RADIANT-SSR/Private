"""Point-source detection range — generic callback-based solver.

Uses bisection on a user-supplied SNR-vs-range function to find the
range at which SNR equals the detection threshold.

See also ``detection_beer_lambert.py`` for the parametric model.
"""

from __future__ import annotations

from collections.abc import Callable

from radiant.performance.detection import DetectionRangeResult


def detection_range_generic(
    snr_at_range_fn: Callable[[float], float],
    snr_threshold: float = 5.0,
    r_min_m: float = 100.0,
    r_max_m: float = 1.0e7,
    tol_m: float = 1.0,
    max_iter: int = 100,
) -> DetectionRangeResult:
    """Compute detection range using a user-supplied SNR-vs-range function.

    Uses bisection to find R where ``snr_at_range_fn(R) = snr_threshold``.

    Parameters
    ----------
    snr_at_range_fn:
        Callable mapping range [m] → SNR. Must be monotonically
        decreasing (or at least cross the threshold once).
    snr_threshold:
        Required SNR for detection.
    r_min_m:
        Minimum search range [m].
    r_max_m:
        Maximum search range [m].
    tol_m:
        Convergence tolerance [m].
    max_iter:
        Maximum bisection iterations.
    """
    snr_lo = snr_at_range_fn(r_min_m)
    snr_hi = snr_at_range_fn(r_max_m)

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
        snr_mid = snr_at_range_fn(r_mid)
        if snr_mid > snr_threshold:
            r_lo = r_mid
        else:
            r_hi = r_mid
        if (r_hi - r_lo) < tol_m:
            break

    r_final = 0.5 * (r_lo + r_hi)
    snr_final = snr_at_range_fn(r_final)

    return DetectionRangeResult(
        range_m=r_final,
        snr_at_range=snr_final,
        snr_threshold=snr_threshold,
        iterations=n_iter,
    )
