"""Slant column length along a ray of known tangent radius (grazing geometry).

One computation, one module (Rule 19): the density-weighted path length

.. math::

    S(r_0;\\, h_{lo} \\to h_{hi};\\, H) \\;=\\;
        \\int \\exp\\!\\left(-\\frac{h(s) - 0}{H}\\right)\\, \\mathrm{d}s

along a straight ray whose closest approach to the Earth centre is ``r_0``,
between the two radii ``R_E + h_lo`` and ``R_E + h_hi``, for a species whose
density falls off exponentially with scale height ``H``.  The result has
units of length and is the exact spherical-geometry analogue of the
``_column_length_km × air_mass`` product the plane-parallel column model
uses — it is what the caller multiplies by a **sea-level** extinction
coefficient ``σ(λ, 0)`` [1/km] to get an optical depth.

Why a separate integral exists at all
-------------------------------------
:class:`~radiant.atmosphere.segments.ColumnSegmentSpec` refuses a
lower-endpoint zenith past ``ZENITH_CEILING_RAD`` (89.5°) because the
plane-parallel-with-spherical-correction air mass it multiplies loses
physical meaning there.  Two Phase-2 products live *entirely* inside that
forbidden band and cannot be expressed any other way:

* the **twilight solar transit** — a sunlit target with ``θ_s > π/2`` is fed
  by a ray that is tangent to the atmosphere by construction
  (:mod:`radiant.atmosphere.solar_transit`);
* the **level-topology sky background** — the LOS continuation past a level
  target leaves at zenith ``π/2 − φ/2`` and, for any arm shorter than
  ≈ 111 km, that is inside the ceiling band
  (:mod:`radiant.atmosphere.segment_grazing`).

Neither is a level arm either (the altitude is *not* constant along them), so
:mod:`radiant.atmosphere.level_arm` does not apply.  The honest answer is the
true integral, which is what this module computes.

Parameterisation
----------------
Substituting ``r = √(r_0² + s²)`` (``s`` = arc length measured from the
tangent point) turns the singular ``r/√(r² − r_0²)`` Jacobian into unity::

    S = ∫_{s_lo}^{s_hi} exp( −(√(r_0² + s²) − R_E) / H ) ds
    s(r) = √(r² − r_0²)

so the integrand is smooth, bounded, and maximal at the tangent end.  Near
``s = 0`` it behaves as ``exp(−(r_0 − R_E)/H)·exp(−s²/(2 r_0 H))`` — a
Gaussian of width ``√(r_0 H)`` (≈ 233 km for air, ≈ 113 km for water
vapour), which is what sets the quadrature resolution below.

Quadrature
----------
Composite Simpson on a uniform ``s`` grid of :data:`QUADRATURE_INTERVALS`
intervals.  Uniform is adequate precisely because the substitution removed the
singularity: with the narrowest physical width (water vapour, ``√(r_0 H)`` ≈
113 km) and the longest physical span (tangent → 100 km, ``s`` ≈ 1130 km) the
grid resolves the Gaussian core with ~400 points.  A Level-0 test checks the
result against a 16× finer grid (Richardson-style convergence) and against
the closed-form Chapman limit.

Truth anchor built into the formulation: as ``h_hi → ∞`` with ``h_lo`` at the
tangent point, ``S / H → √(π r_0 / (2 H))`` — Chapman's grazing-incidence
result (Chapman 1931, *Proc. Phys. Soc.* 43, 26; the ``ch(x, 90°) = √(πx/2)``
identity with ``x = r_0/H``).

Zero drift
----------
Nothing in this module is reachable from a down-looking evaluate path.
"""

from __future__ import annotations

import math

import numpy as np

from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError

__all__ = ["QUADRATURE_INTERVALS", "chapman_grazing_limit_km", "grazing_slant_column_km"]

#: Number of composite-Simpson intervals (must be even).  Chosen so the
#: narrowest physical Gaussian core (water vapour, width ≈ 113 km) is sampled
#: with several hundred points over the longest physical span (≈ 1130 km).
QUADRATURE_INTERVALS: int = 4000


def grazing_slant_column_km(
    r_tangent_m: float,
    h_low_m: float,
    h_high_m: float,
    scale_height_m: float,
) -> float:
    """Density-weighted slant path length between two altitudes [km].

    Parameters
    ----------
    r_tangent_m:
        Closest approach of the **infinite line** to the Earth centre [m],
        ``r · sin(ζ)`` for any point on it.  Must be ``≥ 0`` and
        ``≤ R_E + h_low_m`` (the traversed arc starts at or above the
        perigee).  A perigee *below* ``R_E`` is legal and simply means the
        perigee is not traversed: the arc runs upward from ``h_low_m ≥ 0``,
        so it never enters the solid Earth.  In that regime the integral
        degenerates continuously to the ordinary slant column, which is the
        cross-model check against ``column length × air mass``.
    h_low_m:
        Altitude of the near end of the arc [m], ``≥ 0``.  ``h_low_m ==
        r_tangent_m − R_E`` means the arc starts exactly at the tangent
        point, which is the ``s = 0`` end.
    h_high_m:
        Altitude of the far end of the arc [m].  Must be ``≥ h_low_m``;
        equality gives exactly ``0.0``.
    scale_height_m:
        Exponential scale height of the species [m], ``> 0``.

    Returns
    -------
    float
        ``∫ exp(−h/H) ds`` over the arc, in **kilometres** — the same unit
        and the same sea-level normalisation as
        ``SimpleAtmosphere._column_length_km``, so the two are
        interchangeable inputs to ``σ(λ, 0)``.

    Raises
    ------
    ParameterBoundsError
        On a non-finite input, a below-surface tangent radius, a tangent
        radius above the near end of the arc, an inverted altitude pair, or a
        non-positive scale height (Rule 16 — validate before compute).
    """
    for name, value in (
        ("r_tangent_m", r_tangent_m),
        ("h_low_m", h_low_m),
        ("h_high_m", h_high_m),
        ("scale_height_m", scale_height_m),
    ):
        if not math.isfinite(value):
            raise ParameterBoundsError(
                what=f"grazing_slant_column_km: {name} = {value} is not finite",
                why="A non-finite geometry input propagates NaN into every optical depth.",
                action=f"Supply a finite {name}.",
                context={name: value},
            )
    if scale_height_m <= 0.0:
        raise ParameterBoundsError(
            what=f"grazing_slant_column_km: scale_height_m = {scale_height_m} m is not positive",
            why="An exponential density profile needs a positive scale height.",
            action="Pass one of the SimpleAtmosphere H_MOL_M / H_AER_M / H_H2O_M constants.",
            context={"scale_height_m": scale_height_m},
        )
    if h_low_m < 0.0 or h_high_m < h_low_m:
        raise ParameterBoundsError(
            what=(
                f"grazing_slant_column_km: altitude pair (h_low_m = {h_low_m} m, "
                f"h_high_m = {h_high_m} m) is not an ordered non-negative interval"
            ),
            why="The arc runs from its near end upward; the endpoints must be ordered.",
            action="Swap the altitudes so 0 ≤ h_low_m ≤ h_high_m.",
            context={"h_low_m": h_low_m, "h_high_m": h_high_m},
        )
    if r_tangent_m < 0.0:
        raise ParameterBoundsError(
            what=f"grazing_slant_column_km: r_tangent_m = {r_tangent_m} m is negative",
            why="A perigee radius is a distance from the Earth centre.",
            action="Pass r_tangent_m = r · sin(ζ) ≥ 0 for the ray in question.",
            context={"r_tangent_m": r_tangent_m},
        )
    r_low = R_EARTH_M + h_low_m
    r_high = R_EARTH_M + h_high_m
    if r_tangent_m > r_low:
        # Tolerate one ULP of round-off from r_0 = r sin(ζ) with ζ ≈ π/2.
        if (r_tangent_m - r_low) / r_low <= 1e-12:
            r_tangent_m = r_low
        else:
            raise ParameterBoundsError(
                what=(
                    f"grazing_slant_column_km: r_tangent_m = {r_tangent_m} m exceeds the "
                    f"near-end radius {r_low} m (h_low_m = {h_low_m} m)"
                ),
                why=(
                    "The traversed arc starts at or above its own tangent point; a "
                    "tangent radius above the near end means the ray never reaches "
                    "that altitude."
                ),
                action="Recompute the tangent radius from the same ray that fixes h_low_m.",
                context={"r_tangent_m": r_tangent_m, "r_low_m": r_low},
            )

    if h_high_m == h_low_m:
        return 0.0

    # s = √(r² − r₀²), clamped at zero against round-off at the tangent end.
    s_low = math.sqrt(max(r_low * r_low - r_tangent_m * r_tangent_m, 0.0))
    s_high = math.sqrt(max(r_high * r_high - r_tangent_m * r_tangent_m, 0.0))
    if s_high <= s_low:
        return 0.0

    s = np.linspace(s_low, s_high, QUADRATURE_INTERVALS + 1, dtype=np.float64)
    h = np.sqrt(r_tangent_m * r_tangent_m + s * s) - R_EARTH_M
    f = np.exp(-h / scale_height_m)

    # Composite Simpson: (Δs/3)·[f₀ + 4·Σ_odd + 2·Σ_even + f_n].
    step = (s_high - s_low) / QUADRATURE_INTERVALS
    total = f[0] + f[-1] + 4.0 * float(np.sum(f[1:-1:2])) + 2.0 * float(np.sum(f[2:-1:2]))
    integral_m = step / 3.0 * total
    return float(integral_m / 1000.0)


def chapman_grazing_limit_km(r_tangent_m: float, scale_height_m: float) -> float:
    """Closed-form ``S`` for a full tangent ray out to infinity [km].

    Chapman's grazing-incidence result for an isothermal exponential
    atmosphere (Chapman 1931; the ``Ch(X, 90°) = √(πX/2)`` identity with
    ``X = r₀/H``), re-normalised to this module's sea-level convention::

        S(r₀ → ∞) = exp(−h₀/H) · √( π r₀ H / 2 ),    h₀ = r₀ − R_E

    i.e. the **one-sided** integral from the tangent point outward — which is
    what ``Ch(X, 90°)`` denotes, since an observer at zenith angle 90° sits at
    the tangent point.  A complete limb ray (both sides) is twice this.

    Provided as the analytic truth anchor :func:`grazing_slant_column_km` is
    validated against and as the documented asymptote of that quadrature; it
    is **not** used in the signal chain, because the real column terminates
    at ``h_atm_top``.  The identity is asymptotic in ``X = r₀/H`` (≈ 750 for
    air), so agreement is expected at the few-tenths-of-a-percent level, not
    to machine precision.
    """
    if scale_height_m <= 0.0 or r_tangent_m <= 0.0:
        raise ParameterBoundsError(
            what=(
                f"chapman_grazing_limit_km: r_tangent_m = {r_tangent_m} m and "
                f"scale_height_m = {scale_height_m} m must both be positive"
            ),
            why="The Chapman grazing limit √(π r₀ / 2H) needs positive arguments.",
            action="Pass a positive tangent radius and scale height.",
            context={"r_tangent_m": r_tangent_m, "scale_height_m": scale_height_m},
        )
    h_0 = r_tangent_m - R_EARTH_M
    return float(
        math.exp(-h_0 / scale_height_m)
        * math.sqrt(math.pi * r_tangent_m * scale_height_m / 2.0)
        / 1000.0
    )
