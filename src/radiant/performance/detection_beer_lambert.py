"""Point-source detection range — Beer-Lambert atmosphere model.

Implements §4.12 of ``docs/RADIANT_Metrics.md``. Uses bisection to
find the range at which contrast SNR equals the detection threshold.

Signal model::

    S(R) = S_ref · (R_ref / R)² · exp(−α · (R − R_ref))

See also ``detection_generic.py`` for the callback-based solver.
"""

from __future__ import annotations

import math

from radiant.performance.detection import DetectionRangeResult


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
