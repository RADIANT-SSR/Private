"""Point-source detection range solver.

Implements §4.12 of ``docs/RADIANT_Metrics.md``.

For a point source of known intensity I [W/sr], the signal at range R
decays as 1/R². The detection range is the range at which the contrast
SNR equals a specified threshold (typically SNR_threshold = 5 for
Pd ≈ 0.9 at Pfa ≈ 1e-6 in Gaussian noise).

The solver uses bisection on R to find the crossing point.

Signal model (simplified, after atmosphere)::

    S(R) ∝ I · τ_atm(R) · A_collect / R²

For the iterative solver we use a user-supplied callback or the
simpler Beer-Lambert approximation::

    τ_atm(R) = exp(−α · R)

where α is the extinction coefficient [1/m].
"""

from __future__ import annotations

import math
from collections.abc import Callable
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

    and detection occurs when S(R) / σ_noise = snr_threshold.

    Parameters
    ----------
    signal_e_at_ref:
        Signal electrons at the reference range [e-].
    noise_e:
        Total noise [e- RMS]. Must be > 0.
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

    def snr_at_range(r: float) -> float:
        """Compute SNR at range r."""
        range_factor = (ref_range_m / r) ** 2
        atm_factor = math.exp(-extinction_coeff * (r - ref_range_m))
        signal = signal_e_at_ref * range_factor * atm_factor
        return signal / noise_e

    # Check if target is detectable at reference range.
    snr_ref = snr_at_range(ref_range_m)
    if snr_ref < snr_threshold:
        return DetectionRangeResult(
            range_m=float("nan"),
            snr_at_range=snr_ref,
            snr_threshold=snr_threshold,
            iterations=0,
            failure_reason=(
                f"Target not detectable even at reference range "
                f"({ref_range_m:.0f} m): SNR = {snr_ref:.2f} < {snr_threshold}."
            ),
        )

    # Check if detectable at max range (if so, return max_range).
    snr_max = snr_at_range(max_range_m)
    if snr_max >= snr_threshold:
        return DetectionRangeResult(
            range_m=max_range_m,
            snr_at_range=snr_max,
            snr_threshold=snr_threshold,
            iterations=0,
            failure_reason=(
                f"Detection range exceeds max_range_m = {max_range_m:.0f} m "
                f"(SNR at max = {snr_max:.2f})."
            ),
        )

    # Bisection: find R where SNR = threshold.
    r_lo = ref_range_m
    r_hi = max_range_m
    n_iter = 0
    for _ in range(max_iter):
        n_iter += 1
        r_mid = 0.5 * (r_lo + r_hi)
        snr_mid = snr_at_range(r_mid)
        if snr_mid > snr_threshold:
            r_lo = r_mid
        else:
            r_hi = r_mid
        if (r_hi - r_lo) < tol_m:
            break

    r_final = 0.5 * (r_lo + r_hi)
    snr_final = snr_at_range(r_final)

    return DetectionRangeResult(
        range_m=r_final,
        snr_at_range=snr_final,
        snr_threshold=snr_threshold,
        iterations=n_iter,
    )


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
