"""Target-plane sample distance — the non-ground counterpart of GSD.

One computation, one module (Rule 19).

For a **ground** target the sample footprint is projected onto the ground plane
and the answer is GSD (:mod:`radiant.performance.gsd`), which divides the
along-track axis by ``cos(incidence)`` because the ground plane is tilted with
respect to the line of sight.  For an **air or space** target there is no
ground plane: the natural reference is the plane through the target *normal to
the line of sight*, and the sample distance there is simply the pixel's angular
subtense projected at the slant range::

    IFOV_x = pitch_x / f            [rad]
    d_x    = R · IFOV_x = pitch_x · R / f      [m]
    d_y    = R · IFOV_y = pitch_y · R / f      [m]
    d_mean = sqrt(d_x · d_y)                   [m]

i.e. GSD **without** the ``cos`` projection — the small-angle chord/arc
distinction is below any modelling fidelity here (``IFOV`` ≲ 1 mrad gives
``tan(IFOV)/IFOV − 1 < 3·10⁻⁷``).

Why no target-orientation term
------------------------------
GF-5 notes that the projection onto a *physical* target surface depends on the
target body's orientation, which lives in ``geometry.target.shape_*``.  That is
deliberately not modelled here: this metric answers "how far apart are two
adjacent pixel samples where the target is", which is an optics-and-range
question with a unique answer, not "how much of the target's skin does a pixel
cover", which needs an attitude the framework does not carry.  Naming it
*target-plane* rather than *target-surface* keeps that distinction visible.

The geometric mean is the axis-averaged sample distance, defined the same way
GIQE-5 averages GSD, so the two families are directly comparable across a
scene-class boundary (a target descending from air to ground swaps which
family is surfaced, and the numbers meet at ``incidence = 0``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from radiant.performance.errors import PerformanceValidationError

__all__ = ["TargetPlaneSampleDistance", "target_plane_sample_distance"]


@dataclass(frozen=True, slots=True)
class TargetPlaneSampleDistance:
    """Per-axis sample distance in the target plane [m]."""

    x_m: float
    """Sample distance along the cross-track (x) axis [m]."""

    y_m: float
    """Sample distance along the along-track (y) axis [m]."""

    @property
    def geometric_mean_m(self) -> float:
        """Geometric mean sample distance [m]: ``sqrt(x · y)``."""
        return math.sqrt(self.x_m * self.y_m)


def target_plane_sample_distance(
    pitch_x_m: float,
    pitch_y_m: float,
    focal_length_m: float,
    slant_range_m: float,
) -> TargetPlaneSampleDistance:
    """Sample distance at the target, in the plane normal to the line of sight.

    Parameters
    ----------
    pitch_x_m, pitch_y_m:
        Pixel pitch [m], cross-track / along-track.  Must be > 0.
    focal_length_m:
        Effective focal length [m].  Must be > 0.
    slant_range_m:
        Sensor-to-target slant range [m].  Must be > 0.

    Returns
    -------
    TargetPlaneSampleDistance
        Per-axis distances plus the ``geometric_mean_m`` property.

    Raises
    ------
    PerformanceValidationError
        If any input is non-positive or not finite (Rule 16: validate before
        compute; Rule 17: no silent NaN).
    """
    for name, value in (
        ("pitch_x_m", pitch_x_m),
        ("pitch_y_m", pitch_y_m),
        ("focal_length_m", focal_length_m),
        ("slant_range_m", slant_range_m),
    ):
        if not math.isfinite(value) or value <= 0.0:
            raise PerformanceValidationError(
                f"target_plane_sample_distance: {name} = {value} must be a finite "
                "positive length [m]. The target-plane sample distance is "
                "pitch × slant_range / focal_length; every factor must be a real "
                "positive length for the result to be a distance."
            )
    return TargetPlaneSampleDistance(
        x_m=pitch_x_m * slant_range_m / focal_length_m,
        y_m=pitch_y_m * slant_range_m / focal_length_m,
    )
