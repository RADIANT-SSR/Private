"""Per-altitude solar illumination — the terminator shadow-height test (GF-9).

One computation, one module (Rule 19): decide whether a point at altitude
``h`` with local solar zenith ``θ_s`` is in direct sunlight or inside the
Earth's geometric shadow.

Why this exists
---------------
Before ADR-0011 decision 10 the whole framework carried a **global** bound
``θ_s < π/2``: the sun had to be above the horizon *everywhere in the scene*
(``geometry.solar_zenith_rad`` was bounded at 1.5707 rad and
:class:`~radiant.atmosphere.protocol.AtmosphericGeometry` raised at or beyond
π/2).  That made the entire sunlit-target-over-dark-ground family
inexpressible — a booster at 60 km over ground that is already in twilight is
the canonical case.  Ratified decision 21 replaces the global bound with this
per-altitude test.

The test
--------
For ``θ_s ≤ π/2`` the sun is above the local horizontal: the point is sunlit,
unconditionally, and no geometry is needed.

For ``θ_s > π/2`` the sun is below the local horizontal.  The ray from the
point toward the sun leaves at zenith ``θ_s``, descends to a perigee of radius
``(R_E + h)·sin(θ_s)`` and then climbs away.  The point is sunlit iff that
perigee clears the solid Earth::

    (R_E + h) · sin(θ_s) ≥ R_E

Equivalently, with the solar depression ``δ = θ_s − π/2``, the shadow height
is ``h_shadow(δ) = R_E · (sec δ − 1)`` and the point is sunlit iff
``h ≥ h_shadow``.  Both forms are implemented (:func:`sunlit`,
:func:`shadow_height_m`) and a Level-0 test asserts they agree.

Assumptions
-----------
*Sharp terminator.*  The Earth is an opaque sphere of radius ``R_E`` and the
Sun is a point source, so the transition from shadow to sunlight is a step.
Reality has two smearing effects, neither modelled:

* **Penumbra** — the Sun subtends ≈ 0.53°, so the umbra/penumbra transition
  spans roughly ``R_E · tan(0.53°) ≈ 59 km`` of horizontal distance, which
  at the terminator maps to a few hundred metres of altitude blur (≈ 200 m at
  typical grazing geometry).
* **Refraction** — v1.x models no refraction (ADR-0011 decision 5), which
  lifts the true terminator by roughly half a degree of ray bending and would
  *raise* the sunlit fraction slightly.

Both are far below the fidelity of everything downstream of them (the
transmittance along a grazing solar path is uncertain by tens of percent —
see :mod:`radiant.atmosphere.solar_transit`), so the step is documented
rather than smoothed.  A smoothed terminator would also hide the transition
from the user, which Rule 17 disfavours.

Zero drift
----------
For ``θ_s ≤ π/2`` — every scene expressible before this module existed —
:func:`sunlit` returns ``True`` with no arithmetic at all, so no existing
result can move.
"""

from __future__ import annotations

import math

from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError

__all__ = ["shadow_height_m", "solar_tangent_radius_m", "sunlit"]

# Below this ``sin θ_s`` the sun is treated as exactly antisolar (shadow height
# +inf).  Mirrors the package-wide 1e-12 trigonometric tolerance; it is
# floating-point slop, not a physics parameter.
_SIN_ANTISOLAR_TOLERANCE: float = 1.0e-12


def _validate(h_m: float, theta_s_rad: float, where: str) -> None:
    """Rule 16 input validation shared by the three public functions."""
    if not math.isfinite(h_m) or h_m < 0.0:
        raise ParameterBoundsError(
            what=f"{where}: h_m = {h_m} m is not a finite altitude ≥ 0",
            why="Altitudes are measured above mean sea level on a spherical Earth.",
            action="Set h_m ≥ 0 m.",
            context={"h_m": h_m},
        )
    if not math.isfinite(theta_s_rad) or not (0.0 <= theta_s_rad <= math.pi):
        raise ParameterBoundsError(
            what=(
                f"{where}: theta_s_rad = {theta_s_rad} rad "
                f"({math.degrees(theta_s_rad) if math.isfinite(theta_s_rad) else theta_s_rad}°) "
                "is outside [0, π]"
            ),
            why=(
                "Solar zenith is a zenith angle: 0 is overhead, π/2 the local "
                "horizontal, π directly underfoot.  Since ADR-0011 decision 10 the "
                "domain is the full closed interval so twilight and night geometry "
                "are expressible; nothing outside it is a zenith angle."
            ),
            action="Wrap theta_s_rad into [0, π] rad (0–180°).",
            context={"theta_s_rad": theta_s_rad},
        )


def sunlit(h_m: float, theta_s_rad: float) -> bool:
    """Is a point at ``h_m`` with solar zenith ``theta_s_rad`` in direct sunlight?

    Parameters
    ----------
    h_m:
        Altitude above mean sea level [m], ``≥ 0``.
    theta_s_rad:
        Local solar zenith angle [rad] in ``[0, π]``.

    Returns
    -------
    bool
        ``True`` when the sun is above the local horizontal (``θ_s ≤ π/2``),
        or when the sun-ward ray clears the solid Earth
        (``(R_E + h)·sin θ_s ≥ R_E``).  ``False`` inside the geometric shadow.

    Notes
    -----
    Exactly at the terminator the ray is tangent to the surface and the point
    counts as sunlit (``≥``, not ``>``): a grazing ray is not blocked, and the
    inclusive comparison keeps ``sunlit(0, π/2) is True`` continuous with the
    above-horizon branch.
    """
    _validate(h_m, theta_s_rad, "solar_shadow.sunlit")
    if theta_s_rad <= math.pi / 2.0:
        return True
    return (R_EARTH_M + h_m) * math.sin(theta_s_rad) >= R_EARTH_M


def shadow_height_m(theta_s_rad: float) -> float:
    """Altitude of the Earth's shadow boundary for a given solar zenith [m].

    ``h_shadow = R_E · (sec δ − 1)`` with ``δ = θ_s − π/2`` the solar
    depression.  Returns ``0.0`` for a sun at or above the horizontal (there
    is no shadow to be under) and ``+inf`` as ``θ_s → π`` (the anti-solar
    point, where nothing at any finite altitude is lit).

    This is the inverse reading of :func:`sunlit`: a point is sunlit iff
    ``h ≥ shadow_height_m(θ_s)``.
    """
    if not math.isfinite(theta_s_rad) or not (0.0 <= theta_s_rad <= math.pi):
        raise ParameterBoundsError(
            what=f"solar_shadow.shadow_height_m: theta_s_rad = {theta_s_rad} rad is outside [0, π]",
            why="Solar zenith is a zenith angle in the closed interval [0, π].",
            action="Wrap theta_s_rad into [0, π] rad.",
            context={"theta_s_rad": theta_s_rad},
        )
    if theta_s_rad <= math.pi / 2.0:
        return 0.0
    sin_ts = math.sin(theta_s_rad)
    # sin(π) evaluates to ~1.2e-16 rather than 0 in IEEE-754, which would give
    # a finite-but-absurd 5e22 m instead of "nothing is ever lit".  The same
    # 1e-12 trigonometric tolerance the rest of the package uses
    # (``segment_single_scatter.COS_HORIZON_TOLERANCE``) snaps it.
    if sin_ts <= _SIN_ANTISOLAR_TOLERANCE:
        return math.inf
    return R_EARTH_M * (1.0 / sin_ts - 1.0)


def solar_tangent_radius_m(h_m: float, theta_s_rad: float) -> float:
    """Perigee radius of the point→sun ray, from the Earth centre [m].

    ``r_0 = (R_E + h)·sin(θ_s)``.  For ``θ_s ≤ π/2`` the ray ascends from the
    start point, so the perigee *of the traversed arc* is the start point
    itself and this function returns ``R_E + h`` rather than the geometric
    perigee of the infinite line — the traversed-arc convention is what
    :mod:`radiant.atmosphere.solar_transit` needs.

    Raises when the point is in shadow: there is no unobstructed solar path
    to decompose, and returning a below-surface tangent radius would let a
    caller integrate a column through the Earth (Rule 17).
    """
    _validate(h_m, theta_s_rad, "solar_shadow.solar_tangent_radius_m")
    r = R_EARTH_M + h_m
    if theta_s_rad <= math.pi / 2.0:
        return r
    r_0 = r * math.sin(theta_s_rad)
    if r_0 < R_EARTH_M:
        raise ParameterBoundsError(
            what=(
                f"solar_shadow.solar_tangent_radius_m: the point at h = {h_m} m with "
                f"theta_s = {theta_s_rad} rad ({math.degrees(theta_s_rad):.4f}°) is in "
                f"the Earth's shadow — the sun-ward ray's perigee is "
                f"{r_0 - R_EARTH_M:.1f} m MSL, below the surface"
            ),
            why=(
                "A shadowed point has no unobstructed solar path, so there is no "
                "two-arm transit to decompose.  Returning the geometric perigee "
                "anyway would let the caller integrate an optical column straight "
                "through the Earth (Rule 17 — no silently wrong answer)."
            ),
            action=(
                f"Test with solar_shadow.sunlit() first: this point needs "
                f"h ≥ {shadow_height_m(theta_s_rad):.1f} m to be lit at this solar "
                "zenith.  A shadowed target carries no direct-solar term at all."
            ),
            context={
                "h_m": h_m,
                "theta_s_rad": theta_s_rad,
                "tangent_altitude_m": r_0 - R_EARTH_M,
                "shadow_height_m": shadow_height_m(theta_s_rad),
            },
        )
    return r_0
