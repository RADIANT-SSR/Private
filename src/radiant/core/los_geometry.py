"""Line-of-sight geometry for the Source → Atmosphere boundary (Option C).

`LineOfSightGeometry` is a frozen data contract published by SourceStage and
consumed by AtmosphereStage (see ADR-0002).  It carries the target altitude,
the top-of-atmosphere altitude, and the three zenith/azimuth angles that the
assembly equation needs to compute two-leg attenuation (τ_sun on the down-leg,
τ_up on the up-leg) and single-scatter path radiance.

This file is deliberately isolated from `core/geometry.py` (which houses
`ObserverGeometry`, `TargetGeometry`, `SceneGeometry`) per Rule 19 — LOS
geometry for atmospheric path assembly is a distinct computation from
observer-kinematic rotation and flat-Earth slant range.

Notes
-----
- All angles are stored in radians.  All altitudes are stored in meters.
- Slant range and airmass are computed on a spherical Earth with a single
  secant-type correction; see docstrings for the exact formulas.
- Earth radius is imported from `radiant.core.constants.R_EARTH_M` (Rule 13).

Boundary converter
------------------
`theta_o_from_eta` is a module-level converter from the sensor-side off-nadir
look angle ``eta`` (which depends on ``h_sensor``) to the target-side observer
zenith ``theta_o`` (which does not).  **It is not wired into any stage yet.**
``h_sensor`` is a SensorDescriptor concern (deferred to a follow-on ADR per
matrix §4.4) and a Stage 7 no-atmosphere-space precondition.  Until those
land, this converter is exercised only by unit tests — it is a boundary
converter reserved for Stage 7 / SensorDescriptor follow-on use and is
**not dead code**.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError


@dataclass(frozen=True)
class LineOfSightGeometry:
    """Line-of-sight geometry for the atmosphere assembly equation.

    Parameters
    ----------
    h_tgt:
        Target altitude above mean sea level [m].  Must satisfy
        ``0 ≤ h_tgt ≤ h_atm_top``.  ``at_aperture`` descriptors set
        this to 0 by convention; the assembly arm ignores it.
    h_atm_top:
        Top of the atmospheric integration column [m] (v1 fixed default =
        Kármán line ≈ 100 km).  Must be strictly greater than ``h_tgt``
        when ``h_tgt`` is finite.
    theta_o:
        Observer zenith angle at the target [rad].  ``0`` = sensor at zenith
        (nadir view); must lie in the half-open interval ``[0, π/2)``.
    theta_s:
        Solar zenith angle at the target [rad], or ``None`` for pure-thermal
        scenarios where the sun is not used.  Must lie in ``[0, π]`` if set.
    delta_phi:
        Relative azimuth ``φ_s − φ_o`` [rad], or ``None``.  Must lie in
        ``[−π, π]`` if set.

    Derived properties
    ------------------
    slant_range_atm:
        Distance along the LOS from ``h_tgt`` to ``h_atm_top`` [m] on a
        spherical Earth.
    path_airmass_up:
        Dimensionless airmass factor for the sensor-up leg.  Reduces to
        ``sec(theta_o)`` in the plane-parallel limit and diverges
        smoothly as ``theta_o → π/2``.
    """

    h_tgt: float
    theta_o: float
    h_atm_top: float = 1.0e5
    theta_s: float | None = None
    delta_phi: float | None = None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        # h_atm_top must be physically plausible (positive)
        if self.h_atm_top <= 0.0:
            raise ParameterBoundsError(
                what=f"LineOfSightGeometry.h_atm_top = {self.h_atm_top} m is non-positive",
                why="Top of atmosphere must be a positive altitude above MSL.",
                action="Set h_atm_top to a positive value (v1 default: 1.0e5 m ≈ Kármán line).",
                context={"h_atm_top": self.h_atm_top},
            )

        if not (0.0 <= self.h_tgt <= self.h_atm_top):
            raise ParameterBoundsError(
                what=(
                    f"LineOfSightGeometry.h_tgt = {self.h_tgt} m is outside "
                    f"[0, h_atm_top = {self.h_atm_top}] m"
                ),
                why=(
                    "Target altitude must be non-negative (above MSL) and at or "
                    "below the top of the atmospheric integration column."
                ),
                action=(
                    "Set h_tgt to a non-negative value ≤ h_atm_top; if the target "
                    "is above the atmosphere, use target_location='no_atmosphere' "
                    "with sub-case 'space' instead."
                ),
                context={"h_tgt": self.h_tgt, "h_atm_top": self.h_atm_top},
            )

        if not (0.0 <= self.theta_o < math.pi / 2.0):
            raise ParameterBoundsError(
                what=(
                    f"LineOfSightGeometry.theta_o = {self.theta_o} rad "
                    f"({math.degrees(self.theta_o):.3f}°) is outside [0, π/2)"
                ),
                why=(
                    "Observer zenith at target must be between nadir (0) and "
                    "horizon (π/2, exclusive).  At or beyond horizon the "
                    "plane-parallel airmass diverges and v1 has no refraction model."
                ),
                action="Reduce theta_o below π/2 radians (90°).",
                context={"theta_o": self.theta_o},
            )

        if self.theta_s is not None and not (0.0 <= self.theta_s <= math.pi):
            raise ParameterBoundsError(
                what=(
                    f"LineOfSightGeometry.theta_s = {self.theta_s} rad "
                    f"({math.degrees(self.theta_s):.3f}°) is outside [0, π]"
                ),
                why="Solar zenith at target must lie in [0, π] when specified.",
                action="Set theta_s in [0, π] rad, or leave as None for pure-thermal scenarios.",
                context={"theta_s": self.theta_s},
            )

        if self.delta_phi is not None and not (-math.pi <= self.delta_phi <= math.pi):
            raise ParameterBoundsError(
                what=(f"LineOfSightGeometry.delta_phi = {self.delta_phi} rad is outside [−π, π]"),
                why="Relative azimuth φ_s − φ_o must be expressed in [−π, π].",
                action="Wrap delta_phi into [−π, π] before constructing the geometry.",
                context={"delta_phi": self.delta_phi},
            )

    # ------------------------------------------------------------------
    # Derived geometric properties
    # ------------------------------------------------------------------

    @property
    def slant_range_atm(self) -> float:
        """Slant range from h_tgt up to h_atm_top along theta_o [m].

        Uses ray-sphere intersection from the target point on a spherical
        Earth of radius R_E.  The LOS originates at radius (R_E + h_tgt)
        with zenith angle theta_o (measured from the local vertical) and
        intersects the sphere of radius (R_E + h_atm_top):

            slant = -r_t cos(θ_o) + √((r_t cos(θ_o))² + (r_top² − r_t²))

        where r_t = R_E + h_tgt and r_top = R_E + h_atm_top.

        At θ_o = 0 this reduces to ``h_atm_top − h_tgt`` exactly.
        """
        r_t = R_EARTH_M + self.h_tgt
        r_top = R_EARTH_M + self.h_atm_top
        cos_theta = math.cos(self.theta_o)
        # (r_t cos θ)² + (r_top² − r_t²) — always ≥ 0 for r_top ≥ r_t.
        disc = (r_t * cos_theta) ** 2 + (r_top * r_top - r_t * r_t)
        return float(-r_t * cos_theta + math.sqrt(disc))

    @property
    def path_airmass_up(self) -> float:
        """Dimensionless airmass along the sensor up-leg.

        Defined as ``slant_range_atm / (h_atm_top − h_tgt)`` (the ratio of
        the slant path to the vertical path through the same column).  In
        the plane-parallel limit, this equals sec(theta_o) exactly.
        Spherical-Earth curvature makes the airmass diverge slightly more
        slowly than sec(θ_o) as θ_o → π/2, matching the standard "Kasten"
        shape without explicit refraction.

        Raises
        ------
        ParameterBoundsError
            If h_tgt == h_atm_top (column has zero vertical extent).  This
            is caught by ``__post_init__`` during construction; the property
            guards against the degenerate post-construction state.
        """
        dz = self.h_atm_top - self.h_tgt
        if dz <= 0.0:
            raise ParameterBoundsError(
                what=(
                    f"LineOfSightGeometry.path_airmass_up: vertical column "
                    f"h_atm_top − h_tgt = {dz} m is non-positive"
                ),
                why="Airmass is undefined for a column of zero vertical extent.",
                action="Increase h_atm_top or decrease h_tgt.",
                context={"h_tgt": self.h_tgt, "h_atm_top": self.h_atm_top},
            )
        return float(self.slant_range_atm / dz)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "h_tgt": self.h_tgt,
            "h_atm_top": self.h_atm_top,
            "theta_o": self.theta_o,
            "theta_s": self.theta_s,
            "delta_phi": self.delta_phi,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LineOfSightGeometry:
        """Rebuild from a ``to_dict`` payload."""
        return cls(
            h_tgt=float(d["h_tgt"]),
            theta_o=float(d["theta_o"]),
            h_atm_top=float(d.get("h_atm_top", 1.0e5)),
            theta_s=None if d.get("theta_s") is None else float(d["theta_s"]),
            delta_phi=None if d.get("delta_phi") is None else float(d["delta_phi"]),
        )


# ---------------------------------------------------------------------------
# Boundary converters (reserved for Stage 7 / SensorDescriptor follow-on)
# ---------------------------------------------------------------------------
#
# `theta_o_from_eta` is the one-shot Rule-2 unit/coordinate converter from the
# sensor-referenced off-nadir angle η (which depends on h_sensor) to the
# target-referenced observer zenith θ_o (which LineOfSightGeometry carries).
# It is not invoked by any stage today.  Stage 7 of the Option C plan (and
# the SensorDescriptor follow-on ADR that will carry `h_sensor`) is the first
# consumer.  Keeping it in this module keeps the boundary conversion adjacent
# to the geometry it converts into, and avoids a cross-stage dependency on a
# future SensorDescriptor module.


def theta_o_from_eta(eta: float, h_sensor: float, h_tgt: float) -> float:
    """Convert off-nadir look angle η at the sensor to observer zenith θ_o at the target.

    Uses the spherical-Earth corrected sine rule (law of sines applied to the
    triangle formed by Earth centre, sensor, and target):

        sin(θ_o) = (R_E + h_sensor) / (R_E + h_tgt) · sin(η)

    This is the Rule-2 boundary conversion: the user provides ``η`` (sensor
    pointing), and the atmospheric assembly needs ``θ_o`` (LOS zenith as
    measured at the target, which is what ``LineOfSightGeometry.theta_o``
    carries).  The two are identical in the plane-parallel limit but differ
    by up to ~8° at LEO off-nadir geometries.

    Parameters
    ----------
    eta:
        Sensor off-nadir angle [rad].  Must satisfy the law of sines
        validity condition ``sin(η) · (R_E + h_sensor) ≤ (R_E + h_tgt)``
        (the LOS must actually intersect the target shell).
    h_sensor:
        Sensor altitude above MSL [m].  Must be non-negative.
    h_tgt:
        Target altitude above MSL [m].  Must be non-negative.

    Returns
    -------
    float
        Observer zenith at target [rad] in ``[0, π/2]``.

    Raises
    ------
    ParameterBoundsError
        If ``eta`` or the altitudes are invalid, or if the sine-rule ratio
        exceeds 1 (physically impossible LOS — the sensor-shell ray would
        not intersect the target shell at this azimuth).
    """
    if h_sensor < 0.0:
        raise ParameterBoundsError(
            what=f"theta_o_from_eta: h_sensor = {h_sensor} m is negative",
            why="Sensor altitude must be non-negative.",
            action="Set h_sensor ≥ 0.",
            context={"h_sensor": h_sensor},
        )
    if h_tgt < 0.0:
        raise ParameterBoundsError(
            what=f"theta_o_from_eta: h_tgt = {h_tgt} m is negative",
            why="Target altitude must be non-negative.",
            action="Set h_tgt ≥ 0.",
            context={"h_tgt": h_tgt},
        )
    if not (-math.pi / 2.0 <= eta <= math.pi / 2.0):
        raise ParameterBoundsError(
            what=(
                f"theta_o_from_eta: eta = {eta} rad "
                f"({math.degrees(eta):.3f}°) is outside [−π/2, π/2]"
            ),
            why="Sensor off-nadir angle must lie in [−π/2, π/2].",
            action="Reduce |eta| below π/2.",
            context={"eta": eta},
        )

    ratio = (R_EARTH_M + h_sensor) / (R_EARTH_M + h_tgt) * math.sin(eta)
    if abs(ratio) > 1.0:
        # Guard against floating-point overshoot right at the horizon tangent.
        if abs(ratio) - 1.0 < 1e-12:
            ratio = math.copysign(1.0, ratio)
        else:
            raise ParameterBoundsError(
                what=(f"theta_o_from_eta: sin(θ_o) ratio = {ratio:.6f} exceeds 1"),
                why=(
                    "Sine-rule inversion has no solution — the sensor LOS at "
                    "this η does not intersect the target altitude shell "
                    "(grazes past it)."
                ),
                action=("Reduce eta, raise h_tgt, or acknowledge the LOS misses the target shell."),
                context={
                    "eta": eta,
                    "h_sensor": h_sensor,
                    "h_tgt": h_tgt,
                    "sin_ratio": ratio,
                },
            )
    return float(math.asin(ratio))
