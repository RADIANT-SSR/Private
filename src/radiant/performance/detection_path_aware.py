"""Point-source detection range — path-aware extinction (finding GF-15).

One computation, one module (Rule 19).  Same detection criterion as
:mod:`radiant.performance.detection_beer_lambert` — the range at which contrast
SNR falls to the threshold — but the attenuation term comes from the actual
line of sight instead of one constant extinction coefficient::

    S(R) = S_ref · (R_ref / R)² · τ(R)/τ(R_ref)

with ``τ(R)/τ(R_ref)`` supplied by a
:class:`~radiant.performance.path_optical_depth.PathOpticalDepthProfile`, which
knows where the ray leaves the modelled atmospheric column and stops accruing
optical depth there.

Scope
-----
**Up-looking and level topologies only.**  The down-looking solver is
deliberately untouched: swapping it would move every existing point-source
golden result, which is an owner decision, not a refactor (see the CU draft in
the Phase 3 task report).  For a level arm this solver and the constant-α one
agree to machine precision — the level-arm model *is* constant-extinction — so
routing level scenes through here costs nothing and buys the shared validity
bound.

Root finding is delegated to
:func:`~radiant.performance.detection_generic.detection_range_generic`: this
module owns the signal model, not another copy of a bisection.
"""

from __future__ import annotations

import math

from radiant.performance.detection import DetectionRangeResult
from radiant.performance.detection_generic import detection_range_generic
from radiant.performance.path_optical_depth import PathOpticalDepthProfile

__all__ = ["detection_range_path_aware"]


def detection_range_path_aware(
    signal_e_at_ref: float,
    noise_e: float,
    profile: PathOpticalDepthProfile,
    snr_threshold: float = 5.0,
    max_range_m: float | None = None,
    tol_m: float = 1.0,
    max_iter: int = 100,
) -> DetectionRangeResult:
    """Detection range along the profile's actual path.

    Parameters
    ----------
    signal_e_at_ref:
        Signal electrons at the profile's reference range [e-].  Must be > 0.
    noise_e:
        Total noise [e- RMS].  Must be > 0.
    profile:
        The path optical-depth profile; its ``ref_range_m`` is the reference
        range and the lower bound of the search.
    snr_threshold:
        Required SNR for detection (default 5.0).
    max_range_m:
        Upper bound of the search [m].  ``None`` (the default) uses the
        **analytic** bound: attenuation only ever removes signal, so
        :math:`\\tau(R)/\\tau(R_{ref}) \\le 1` and the detection range can never
        exceed the vacuum inverse-square answer
        :math:`R_{ref}\\sqrt{\\mathrm{SNR}_{ref}/\\mathrm{threshold}}`.  That
        makes the bracket ``[R_ref, R_vac]`` provably root-containing whenever
        the target is detectable at the reference range, so no arbitrary search
        ceiling is needed and no scene is silently truncated by one.  Whatever
        the source, the bound is reduced to the profile's ``max_valid_range_m``
        when that is smaller — the solver never reports a range through
        geometry the profile does not model.
    tol_m:
        Convergence tolerance [m].
    max_iter:
        Maximum bisection iterations.

    Returns
    -------
    DetectionRangeResult
        ``ok`` is False (with ``failure_reason``) when the target is already
        below threshold at the reference range, or when the search hits the
        upper bound — the same result-typed contract the other solvers use
        (ADR-B; Rule 17 metric-layer carve-out).
    """
    if not math.isfinite(signal_e_at_ref) or signal_e_at_ref <= 0.0:
        return DetectionRangeResult(
            range_m=float("nan"),
            snr_at_range=0.0,
            snr_threshold=snr_threshold,
            iterations=0,
            failure_reason=f"Signal at reference = {signal_e_at_ref} must be > 0.",
        )
    if not math.isfinite(noise_e) or noise_e <= 0.0:
        return DetectionRangeResult(
            range_m=float("nan"),
            snr_at_range=0.0,
            snr_threshold=snr_threshold,
            iterations=0,
            failure_reason=f"Noise = {noise_e} must be > 0.",
        )
    if not math.isfinite(snr_threshold) or snr_threshold <= 0.0:
        return DetectionRangeResult(
            range_m=float("nan"),
            snr_at_range=signal_e_at_ref / noise_e,
            snr_threshold=snr_threshold,
            iterations=0,
            failure_reason=f"Detection SNR threshold = {snr_threshold} must be > 0.",
        )

    ref_range_m = profile.ref_range_m
    if max_range_m is None:
        # Exact upper bound: τ(R)/τ(R_ref) ≤ 1, so the range can never exceed
        # the vacuum inverse-square solution. A hair of margin keeps the
        # bracket strictly enclosing when the path really is vacuum.
        # ``max(..., 1.0)`` keeps the bracket non-degenerate when the target is
        # already below threshold at the reference range, so the solver reports
        # "not detectable at the reference range" rather than "empty interval".
        snr_ref = signal_e_at_ref / noise_e
        vacuum_factor = max(math.sqrt(snr_ref / snr_threshold), 1.0)
        max_range_m = ref_range_m * vacuum_factor * (1.0 + 1.0e-9)
    search_max_m = min(max_range_m, profile.max_valid_range_m)
    if search_max_m <= ref_range_m:
        return DetectionRangeResult(
            range_m=float("nan"),
            snr_at_range=signal_e_at_ref / noise_e,
            snr_threshold=snr_threshold,
            iterations=0,
            failure_reason=(
                f"Search upper bound {search_max_m:.0f} m is not beyond the "
                f"reference range {ref_range_m:.0f} m, so there is no interval "
                f"to search. The bound is the lesser of the requested "
                f"max_range_m ({max_range_m:.0f} m) and the {profile.topology} "
                f"profile's validity limit ({profile.max_valid_range_m:.0f} m). "
                "Raise max_range_m, or shorten the scene's path so the "
                "profile's validity limit lies beyond it."
            ),
        )

    def snr_at_range(r: float) -> float:
        """Contrast SNR at range *r* [m]: inverse-square × path transmittance."""
        range_factor = (ref_range_m / r) ** 2
        atm_factor = profile.transmittance_ratio(r)
        return signal_e_at_ref * range_factor * atm_factor / noise_e

    return detection_range_generic(
        snr_at_range_fn=snr_at_range,
        snr_threshold=snr_threshold,
        r_min_m=ref_range_m,
        r_max_m=search_max_m,
        tol_m=tol_m,
        max_iter=max_iter,
    )
