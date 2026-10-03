"""The range bracket a detection solve searches, inward or outward (Gap 136).

Detection range is the range at which contrast SNR falls to the threshold.
Signal falls with range — inverse-square, times a transmittance that only
decreases outward — so SNR is monotonic in range and the root is unique. The
question this module answers is *which side of the reference range it lies on*.

Both solvers used to bracket **outward only**, from the reference range up to
the vacuum solution. That is right when the target is detectable where it
currently is. When it is **not** — when SNR at the reference range is already
below threshold — the root lies *inward*, and the outward bracket collapses to
a point: the old code clamped the vacuum factor at ``max(…, 1.0)`` and then
returned "no interval to search".

So the metric was declined in exactly the case an analyst most wants it. The
external review put it plainly: detection *range* is the natural headline of a
point-source model, and "how close would I have to be?" is the question a
below-threshold result raises. Returning nothing there is answerable-but-unanswered.

Why the vacuum solution brackets the root on both sides
------------------------------------------------------
In vacuum ``S ∝ 1/R²``, so the range at which the signal reaches the threshold
value ``S*`` is ``R_vac = R_ref · √(S_ref/S*)``.

*Outward* (``S_ref > S*``, so ``R_vac > R_ref``): the real path only attenuates
more than vacuum, ``τ(R)/τ(R_ref) ≤ 1``, so the real detection range cannot
exceed ``R_vac`` — an exact upper bound. This is the bound the original code
documented.

*Inward* (``S_ref < S*``, so ``R_vac < R_ref``): the path is **shorter**, so
``τ(R)/τ(R_ref) ≥ 1`` and the real signal at ``R_vac`` is at least the vacuum
signal, which is ``S*``. So the real root lies at or beyond ``R_vac`` going in —
an exact *lower* bound, by the mirror of the same argument.

Either way the vacuum solution and the reference range enclose the root, which
is what a bisection needs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from radiant.performance.errors import PerformanceValidationError

__all__ = ["DetectionBracket", "vacuum_bracket"]

#: Relative margin pushing each bound a hair past the root, so the bracket is
#: strictly enclosing even when the path really is vacuum and the bound is exact.
_MARGIN: float = 1.0e-9


@dataclass(frozen=True, slots=True)
class DetectionBracket:
    """The interval to search, and which way it points.

    ``inward`` is True when the target is already below threshold at the
    reference range, so the answer is "you would have to be this close".
    """

    r_min_m: float
    r_max_m: float
    inward: bool


def vacuum_bracket(
    *, signal_e_at_ref: float, signal_at_threshold_e: float, ref_range_m: float
) -> DetectionBracket:
    """Bracket the detection range using the vacuum inverse-square solution."""
    if not math.isfinite(signal_e_at_ref) or signal_e_at_ref <= 0.0:
        raise PerformanceValidationError(
            f"vacuum_bracket: signal_e_at_ref = {signal_e_at_ref} must be a "
            f"positive finite charge in electrons."
        )
    if not math.isfinite(signal_at_threshold_e) or signal_at_threshold_e <= 0.0:
        raise PerformanceValidationError(
            f"vacuum_bracket: signal_at_threshold_e = {signal_at_threshold_e} "
            f"must be a positive finite charge in electrons."
        )
    if not math.isfinite(ref_range_m) or ref_range_m <= 0.0:
        raise PerformanceValidationError(
            f"vacuum_bracket: ref_range_m = {ref_range_m} must be a positive "
            f"finite range in metres."
        )

    factor = math.sqrt(signal_e_at_ref / signal_at_threshold_e)
    r_vacuum_m = ref_range_m * factor
    if factor >= 1.0:
        return DetectionBracket(
            r_min_m=ref_range_m,
            r_max_m=r_vacuum_m * (1.0 + _MARGIN),
            inward=False,
        )
    return DetectionBracket(
        r_min_m=r_vacuum_m * (1.0 - _MARGIN),
        r_max_m=ref_range_m,
        inward=True,
    )
