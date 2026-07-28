"""In-band optical depth as a function of range along the actual line of sight.

One computation, one module (Rule 19): given the line of sight a run actually
has, and the band-mean optical depth the atmosphere stage actually produced
over it, express :math:`\\mathrm{OD}(R)` for a hypothetical target placed at
range *R* along the **same ray** — the input the detection-range solver needs
(finding GF-15).

Why this exists
---------------
``detection_range_beer_lambert`` models the whole path with one constant
extinction :math:`\\alpha = -\\ln\\bar\\tau / R_{ref}` and integrates
:math:`e^{-\\alpha R}`.  For a down-looking scene that is the shipped,
golden-baselined model and is **not** touched.  For the topologies Phases 1–2
opened it is the wrong shape: an up-looking ray leaves the modelled column
entirely at a finite range, past which *no* further extinction accrues, so a
constant-:math:`\\alpha` extrapolation under-estimates the detection range
without bound.

The profile here is piecewise in exactly the way the path is:

============================  ==================================================
Piece                         Optical-depth law
============================  ==================================================
``[0, R_ref]``                measured — :math:`\\mathrm{OD}_{ref}` is what the
                              chain computed for the real path
``(R_ref, R_exit]``           still inside the modelled column
``(R_exit, ∞)``               vacuum: :math:`\\mathrm{OD}` constant
============================  ==================================================

Which topologies are solvable here
----------------------------------
The middle piece needs the extinction *profile* along the continuation, which
only the atmosphere backend knows and which a metric-layer module may not
import (Rule 11).  So this module builds a profile only when that piece is
either empty or exactly constant:

``level``
    A constant-altitude arm has constant density by construction — that is the
    level-arm model's own assumption (``atmosphere/level_arm.py`` evaluates a
    local extinction at the endpoint altitude).  The local extinction is
    therefore exactly :math:`-\\ln\\bar\\tau / R_{ref}` and the middle piece is
    a genuine Beer-Lambert law rather than an approximation of one.  Validity
    is bounded by the chord sag: the arm dips
    :math:`\\Delta h \\approx L^2 / 8R_E` below its endpoints, and beyond the
    ratified 2 km raise threshold (ADR-0011 §8.3 addendum) the path is a
    limb-like transit the model refuses — hence
    :data:`LEVEL_ARM_MAX_RANGE_M`.

``up`` with the target at or above the column top
    The ray has already left the atmosphere at the reference range, so the
    middle piece is empty and the tail is exact vacuum.  This covers
    ground-to-space, air-to-space and space-to-space (the SST and LEO→GEO
    classes).

``up`` through a transparent path (:math:`\\bar\\tau = 1`)
    Vacuum everywhere; :math:`\\mathrm{OD} \\equiv 0` exactly.

``up`` with an attenuating continuation still inside the column
    **Refused** — :func:`resolve_path_optical_depth` returns a resolution with
    a ``failure_reason`` naming the missing input.  Rule 17: silently reusing
    the constant-:math:`\\alpha` model here would be the very error GF-15
    reports, dressed as an answer.  Closing it needs the atmosphere stage to
    publish the segment-resolved extinction profile along the LOS; that is
    tracked as a CU, not papered over here.

Down-looking lines of sight never reach this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from radiant.core.constants import R_EARTH_M
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.viewing_triangle import eta_from_theta_o
from radiant.performance.errors import PerformanceValidationError

__all__ = [
    "LEVEL_ARM_MAX_RANGE_M",
    "LEVEL_ARM_SAG_CEILING_M",
    "PathOpticalDepthProfile",
    "PathOpticalDepthResolution",
    "column_exit_range_m",
    "resolve_path_optical_depth",
]

#: Tangent-height depression at which a level arm becomes a limb-like transit
#: the geometry layer refuses [m] — the ratified 2 km raise threshold of the
#: ADR-0011 §8.3 horizon-guard addendum.
LEVEL_ARM_SAG_CEILING_M: Final[float] = 2.0e3

#: Longest level arm whose chord sag stays inside :data:`LEVEL_ARM_SAG_CEILING_M`
#: [m], from :math:`\Delta h \approx L^2 / 8 R_E` ⇒
#: :math:`L = \sqrt{8 R_E \Delta h}` ≈ 319 km.  The detection-range search for a
#: level scene is capped here: a reported range beyond it would run through a
#: path the horizon guard rejects.
LEVEL_ARM_MAX_RANGE_M: Final[float] = math.sqrt(8.0 * R_EARTH_M * LEVEL_ARM_SAG_CEILING_M)


@dataclass(frozen=True, slots=True)
class PathOpticalDepthProfile:
    """Piecewise in-band optical depth along one line of sight.

    Attributes
    ----------
    ref_range_m:
        The real sensor-to-target slant range [m] — where ``ref_optical_depth``
        was measured.
    ref_optical_depth:
        Band-mean in-band optical depth over ``[0, ref_range_m]``
        (:math:`-\\ln\\bar\\tau`, ≥ 0).
    extinction_per_m:
        Local extinction applied on the in-column continuation [1/m].  Zero for
        every profile whose continuation is vacuum.
    column_exit_range_m:
        Range at which the ray crosses ``h_atm_top`` [m], or ``None`` when the
        continuation never leaves the column within the profile's validity
        (the level arm).  Clamped to ``ref_range_m`` when the ray has already
        exited at the reference point.
    max_valid_range_m:
        Upper bound of the profile's validity [m] — the geometry beyond it is
        outside the modelled topology (level-arm sag ceiling), or ``inf``.
    topology:
        ``"level"`` | ``"up_vacuum_tail"`` | ``"vacuum"`` — which of the cases
        in the module docstring produced this profile.
    """

    ref_range_m: float
    ref_optical_depth: float
    extinction_per_m: float
    column_exit_range_m: float | None
    max_valid_range_m: float
    topology: str

    def optical_depth_at(self, range_m: float) -> float:
        """Optical depth from the sensor out to *range_m* [m], dimensionless.

        Monotone non-decreasing in *range_m* by construction.

        Raises
        ------
        PerformanceValidationError
            If *range_m* is not a finite positive length, or is short of the
            reference range (the profile carries no information about the
            interior of the measured leg — only its total).
        """
        if not math.isfinite(range_m) or range_m <= 0.0:
            raise PerformanceValidationError(
                f"PathOpticalDepthProfile.optical_depth_at: range_m = {range_m} must "
                "be a finite positive length [m]."
            )
        if range_m < self.ref_range_m:
            raise PerformanceValidationError(
                f"PathOpticalDepthProfile.optical_depth_at: range_m = {range_m} m is "
                f"inside the measured leg (reference range {self.ref_range_m} m). The "
                "profile carries the leg's total optical depth, not its interior "
                "distribution; evaluate at or beyond the reference range."
            )
        attenuating_end = range_m
        if self.column_exit_range_m is not None:
            attenuating_end = min(range_m, self.column_exit_range_m)
        extra_m = max(0.0, attenuating_end - self.ref_range_m)
        return self.ref_optical_depth + self.extinction_per_m * extra_m

    def transmittance_ratio(self, range_m: float) -> float:
        """:math:`\\tau(R)/\\tau(R_{ref})` — the extra attenuation past the reference.

        This is the factor the detection solver multiplies onto the
        inverse-square law; it is 1.0 at the reference range and decreases
        monotonically outward.
        """
        return math.exp(-(self.optical_depth_at(range_m) - self.ref_optical_depth))


@dataclass(frozen=True, slots=True)
class PathOpticalDepthResolution:
    """A profile, or a named reason there is none (ADR-B result-typed failure)."""

    profile: PathOpticalDepthProfile | None
    failure_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.profile is not None and self.failure_reason is None


def column_exit_range_m(los: LineOfSightGeometry) -> float:
    """Range from the **sensor** at which an up-looking ray crosses ``h_atm_top`` [m].

    On a spherical Earth the radius along the ray at arc-free distance *s* from
    the lower endpoint (radius :math:`r_0`, local zenith :math:`\\zeta_0`) is

    .. math:: r(s)^2 = r_0^2 + s^2 + 2 r_0 s \\cos\\zeta_0

    so the crossing of :math:`r = r_{top}` is the positive root

    .. math:: s = -r_0\\cos\\zeta_0
              + \\sqrt{r_0^2\\cos^2\\zeta_0 + r_{top}^2 - r_0^2}.

    For an up-looking line of sight the sensor **is** the lower endpoint
    (ADR-0011 decision 3) and its look-direction zenith is
    :math:`\\zeta_0 = \\pi - \\eta`, with :math:`\\eta` the sensor-side interior
    angle measured from nadir (the convention
    :mod:`radiant.atmosphere.observer_leg` also uses).  At :math:`\\theta_o=\\pi`
    (straight up) this reduces to ``h_atm_top - h_sensor`` exactly.

    Raises
    ------
    PerformanceValidationError
        If *los* is not up-looking, or carries no sensor altitude.
    """
    if los.los_direction != "up":
        raise PerformanceValidationError(
            f"column_exit_range_m: line of sight is {los.los_direction!r}; the "
            "column-exit range is defined for an up-looking ray, whose lower "
            "endpoint is the sensor."
        )
    if los.h_sensor is None:
        raise PerformanceValidationError(
            "column_exit_range_m: the line of sight carries no sensor altitude "
            "(h_sensor is None), so the ray's lower endpoint is unknown."
        )
    r_0 = R_EARTH_M + los.h_sensor
    r_top = R_EARTH_M + los.h_atm_top
    if r_0 >= r_top:
        return 0.0
    eta = eta_from_theta_o(los.theta_o, los.h_sensor, los.h_tgt)
    cos_zeta = math.cos(math.pi - eta)
    disc = (r_0 * cos_zeta) ** 2 + r_top**2 - r_0**2
    # disc > 0 whenever r_top > r_0, which the guard above has established.
    return -r_0 * cos_zeta + math.sqrt(disc)


def resolve_path_optical_depth(
    los: LineOfSightGeometry,
    ref_range_m: float,
    ref_optical_depth: float,
) -> PathOpticalDepthResolution:
    """Build the path optical-depth profile for an up-looking or level LOS.

    Parameters
    ----------
    los:
        The line of sight ``GeometryStage`` published.  Must be ``"up"`` or
        ``"level"``; a down-looking path keeps the shipped constant-extinction
        solver and never arrives here.
    ref_range_m:
        Slant range at which ``ref_optical_depth`` was measured [m], > 0.
    ref_optical_depth:
        Band-mean in-band optical depth over the real path, :math:`-\\ln\\bar\\tau`
        ≥ 0.

    Returns
    -------
    PathOpticalDepthResolution
        Carrying either a profile or a ``failure_reason``.

    Raises
    ------
    PerformanceValidationError
        On a down-looking LOS or non-physical arguments — those are caller
        errors, not un-modellable physics.
    """
    if los.los_direction == "down":
        raise PerformanceValidationError(
            "resolve_path_optical_depth: the down-looking topology keeps the "
            "shipped constant-extinction solver (detection_beer_lambert); "
            "migrating it is an owner decision because it moves golden results."
        )
    if not math.isfinite(ref_range_m) or ref_range_m <= 0.0:
        raise PerformanceValidationError(
            f"resolve_path_optical_depth: ref_range_m = {ref_range_m} must be a "
            "finite positive length [m]."
        )
    if not math.isfinite(ref_optical_depth) or ref_optical_depth < 0.0:
        raise PerformanceValidationError(
            f"resolve_path_optical_depth: ref_optical_depth = {ref_optical_depth} "
            "must be finite and >= 0 (it is -ln of an in-band transmittance in (0, 1])."
        )

    alpha = ref_optical_depth / ref_range_m

    if los.los_direction == "level":
        # Constant-altitude arm ⇒ constant density ⇒ constant extinction. This
        # is the level-arm model's own assumption, so alpha is exact here, not
        # a first-order stand-in. The continuation never leaves the column.
        return PathOpticalDepthResolution(
            profile=PathOpticalDepthProfile(
                ref_range_m=ref_range_m,
                ref_optical_depth=ref_optical_depth,
                extinction_per_m=alpha,
                column_exit_range_m=None,
                max_valid_range_m=LEVEL_ARM_MAX_RANGE_M,
                topology="level",
            )
        )

    # Up-looking.
    if ref_optical_depth == 0.0:
        return PathOpticalDepthResolution(
            profile=PathOpticalDepthProfile(
                ref_range_m=ref_range_m,
                ref_optical_depth=0.0,
                extinction_per_m=0.0,
                column_exit_range_m=ref_range_m,
                max_valid_range_m=math.inf,
                topology="vacuum",
            )
        )

    exit_range_m = column_exit_range_m(los)
    if exit_range_m <= ref_range_m:
        # The ray is already outside the modelled column at the target: every
        # further metre is vacuum, so the optical depth is frozen. Exact.
        return PathOpticalDepthResolution(
            profile=PathOpticalDepthProfile(
                ref_range_m=ref_range_m,
                ref_optical_depth=ref_optical_depth,
                extinction_per_m=0.0,
                column_exit_range_m=ref_range_m,
                max_valid_range_m=math.inf,
                topology="up_vacuum_tail",
            )
        )

    return PathOpticalDepthResolution(
        profile=None,
        failure_reason=(
            "Detection range is not available for an up-looking path whose "
            f"continuation is still inside the atmosphere: the target sits at "
            f"{los.h_tgt:.0f} m and the ray leaves the modelled column "
            f"(h_atm_top = {los.h_atm_top:.0f} m) only at "
            f"{exit_range_m:.0f} m, past the {ref_range_m:.0f} m reference "
            "range. Extinction along that continuation varies with altitude, "
            "and the metric layer has no altitude-resolved extinction profile "
            "to integrate — reusing the constant-extinction model here is "
            "exactly the error finding GF-15 reports. Place the target at or "
            "above h_atm_top, use a level or down-looking geometry, or read "
            "SNR/SCNR directly."
        ),
    )
