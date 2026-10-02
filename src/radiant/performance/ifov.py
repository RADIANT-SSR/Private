"""Instantaneous field of view — the angular subtense of one pixel (Gap 134).

``IFOV = p / f`` for a pixel of pitch ``p`` at focal length ``f``, in the
small-angle limit that every RADIANT consumer of it already assumes.

This is published rather than merely computable because RADIANT already *uses*
it — :mod:`radiant.performance.johnson_criteria` takes ``ifov_rad`` as an
argument, and the GSD metrics are IFOV times slant range — while never putting
it in the output. That is the Gap 134 pattern exactly: the quantity an external
model will disagree about is the one RADIANT derives silently.

The small-angle form is exact to the pixel's own angular size: at a 20 µm pixel
on a 50 mm lens the IFOV is 400 µrad, where ``arctan(p/f)`` differs from ``p/f``
by 2e-8 relative. The arctan form is not used because the pixel is a chord on
the focal plane, not an arc, so ``p/f`` is the physically correct ratio for the
*sampling* interval the consumers want.
"""

from __future__ import annotations

import math

from radiant.performance.errors import PerformanceValidationError

__all__ = ["ifov_rad"]


def ifov_rad(pixel_pitch_m: float, focal_length_m: float) -> float:
    """Angular subtense of one pixel [rad]."""
    if not math.isfinite(pixel_pitch_m) or pixel_pitch_m <= 0.0:
        raise PerformanceValidationError(
            f"ifov_rad: pixel_pitch_m = {pixel_pitch_m} must be a positive finite length in metres."
        )
    if not math.isfinite(focal_length_m) or focal_length_m <= 0.0:
        raise PerformanceValidationError(
            f"ifov_rad: focal_length_m = {focal_length_m} must be a positive "
            f"finite length in metres."
        )
    return pixel_pitch_m / focal_length_m
