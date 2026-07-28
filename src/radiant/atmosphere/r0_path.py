r"""Path-weighted Fried parameter $r_0$ from a $C_n^2$ profile.

One computation, one module (Rule 19): the weighted path integral of
$C_n^2$ along the line of sight and its reduction to a coherence diameter.
The profiles themselves live in :mod:`radiant.atmosphere.cn2_hufnagel_valley`
and :mod:`radiant.atmosphere.cn2_tabulated`; the parameter-resolution policy
(direct $r_0$ vs profile, the agreement raise) lives in
:mod:`radiant.atmosphere.r0_resolution`.

The equation
------------
.. math::

    r_0 = \left[\,0.423\, k^2 \sec\zeta \int_{h_{low}}^{h_{high}}
                 C_n^2(h)\, W(h)\, \mathrm{d}h \right]^{-3/5},
    \qquad k = \frac{2\pi}{\lambda}

with $\zeta$ the zenith angle at the segment's **lower endpoint** (ADR-0011
decision 3 — the same convention
:class:`~radiant.atmosphere.segments.ColumnSegmentSpec` uses), and $W$ the
wave-type weighting below.  $\sec\zeta$ converts vertical thickness
$\mathrm{d}h$ into path length; the profile is evaluated against altitude, so
the integral is plane-parallel over the atmospheric slab.

Units: $C_n^2$ [m^(-2/3)] × dh [m] = [m^(1/3)]; $k^2$ [m^(-2)] × [m^(1/3)] =
[m^(-5/3)]; raised to $-3/5$ gives **metres**.  ✓

Wave-type weighting — the convention, precisely
-----------------------------------------------
Parameterize the line of sight by the fraction of the way from the **target**
(the source, $u = 0$) to the **sensor aperture** ($u = 1$).  Under the
plane-parallel assumption above, distance along the path is proportional to
altitude difference, so

.. math::  u(h) = \frac{h - h_{tgt}}{h_{sen} - h_{tgt}} \in [0, 1]

for either travel direction (the ratio is signed-consistent because both
numerator and denominator flip sign together).

``"plane"`` (default)
    $W = 1$.  The source is effectively at infinity — the astronomical /
    imaging case, and the convention every published $r_0$ value for a
    standard $C_n^2$ profile uses (HV-5/7 → 5 cm at 0.5 µm, zenith).

``"spherical"``
    $W(h) = u(h)^{5/3}$ — **maximum at the aperture, zero at the target**.
    This is the finite-range point-source (spherical-wave) coherence radius.
    The direction follows from tracing two rays that arrive at the aperture
    separated by $\rho$: they converge to a point at the source, so at a
    fraction $u$ of the way from the source their separation is $\rho u$, and
    the wave structure function picks up $(\rho u)^{5/3}$.  **Turbulence near
    the sensor therefore dominates** — which is why a ground-based telescope's
    seeing is set by the surface layer, and why a ground point source viewed
    from space is barely degraded at all.

    Equivalently, with $z$ measured **from the aperture**,
    $W = (1 - z/L)^{5/3}$; with $z$ measured from the source, $W = (z/L)^{5/3}$.
    Both are the same function; $u$ is used here because it is exactly bounded
    in $[0, 1]$ under the plane-parallel parameterization, whereas mixing a
    plane-parallel arc length with a true spherical chord is not.

Level (constant-altitude) paths
-------------------------------
$\sec\zeta$ diverges at $\zeta = \pi/2$, so a level arm is *not* a column: it
is integrated directly along its length $L$ at the constant altitude $h$,
matching :class:`~radiant.atmosphere.segments.LevelArmSpec`:

.. math::

    \int C_n^2 W\,\mathrm{d}s = C_n^2(h)\, L \times
        \begin{cases} 1 & \text{plane} \\ 3/8 & \text{spherical} \end{cases}

since $\int_0^1 u^{5/3}\,\mathrm{d}u = 3/8$ exactly.

Direction-aware integration limits
----------------------------------
The integral runs over the part of the LOS **inside the atmosphere**, i.e.
the endpoint altitudes clipped to ``[0, los.h_atm_top]``:

* **ground sensor, target above** — the full column above the sensor
  (0 → ``h_tgt``, or 0 → ``h_atm_top`` for a space target: the SST case);
* **airborne sensor** — a partial column (``h_sensor`` → target/top);
* **space sensor** — the residual column above ``h_atm_top`` is empty, so the
  integral is zero (or, for a sensor at 20–40 km, tiny).  This is **not an
  error**: the result is a finite, huge $r_0$ saturated at
  :data:`R0_NEGLIGIBLE_M` with ``negligible = True``.  This behaviour
  *replaces* the documented "the parameter resolver rejects turbulence for a
  space observer with a ScopeError" rule (guardrail G4 / Rule 27 — the
  generalization retires the carve-out).

Where ``negligible`` is set, the caller omits the turbulence term entirely
rather than multiplying by a unity MTF (RADIANT_Atmosphere.md §8 item 5).
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.atmosphere.cn2_profiles import Cn2Profile
from radiant.atmosphere.observer_leg import observer_leg_from_los
from radiant.atmosphere.protocol import ZENITH_CEILING_RAD
from radiant.atmosphere.segments import ColumnSegmentSpec, LevelArmSpec
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError

__all__ = [
    "FRIED_COEFFICIENT",
    "R0_NEGLIGIBLE_M",
    "SPHERICAL_LEVEL_WEIGHT",
    "WAVE_TYPES",
    "PathFriedParameter",
    "fried_parameter_from_integral_m",
    "path_fried_parameter_from_los",
]

#: The 0.423 in ``r0 = [0.423 k² sec ζ ∫ Cn² W dh]^(-3/5)``.  It is
#: ``(2.914 / 6.88)^(-3/5)``-equivalent bookkeeping of the Kolmogorov wave
#: structure function normalization; see Fried (1966) / Andrews & Phillips
#: (2005) §12.2.  A model constant, not a physical constant (Rule 13 covers
#: the latter, which live in ``core/constants.py``).
FRIED_COEFFICIENT: float = 0.423

#: ``∫₀¹ u^(5/3) du`` — the mean spherical-wave weight over a level arm.
SPHERICAL_LEVEL_WEIGHT: float = 3.0 / 8.0

#: Legal ``wave_type`` values.
WAVE_TYPES: tuple[str, ...] = ("plane", "spherical")

#: Saturation value for a vacuum / near-vacuum path [m].  At r0 = 1 km the
#: Kolmogorov MTF at the diffraction cutoff of a **10 m** aperture is
#: ``exp(-3.44·(10/1000)^(5/3)) = 0.9984`` — indistinguishable from unity for
#: any sensor RADIANT models.  Reporting this finite number (with
#: ``negligible = True``) rather than ``inf`` keeps Rule 16 (no silent inf)
#: and Rule 17 (the saturation is named in the result, not hidden).
R0_NEGLIGIBLE_M: float = 1.0e3

# Quadrature control.  The integrand is smooth and positive; convergence is
# checked by grid doubling rather than assumed.
_QUAD_START_NODES: int = 256
_QUAD_MAX_DOUBLINGS: int = 12
_QUAD_RTOL: float = 1.0e-6

# Fraction of the integration span that may lie outside a tabulated profile's
# coverage before the user is warned (Rule 17 — no silent extrapolation).
_COVERAGE_WARN_FRACTION: float = 1.0e-3


@dataclass(frozen=True)
class PathFriedParameter:
    """Result of the path-weighted Fried-parameter computation.

    Parameters
    ----------
    r0_m:
        Fried coherence diameter [m] at :attr:`wavelength_m`.  Always finite
        and positive; saturated at :data:`R0_NEGLIGIBLE_M` when
        :attr:`negligible` is ``True``.
    cn2_path_integral_m13:
        The weighted integral ``sec ζ ∫ Cn² W dh`` [m^(1/3)] — the quantity
        that actually carries the turbulence strength, exposed for Rule 16
        inspectability and for wavelength rescaling.
    wavelength_m:
        Wavelength the coherence diameter is quoted at [m].  ``r0 ∝ λ^(6/5)``
        exactly, so a value at another wavelength is a pure rescale.
    wave_type:
        ``"plane"`` or ``"spherical"``.
    zeta_low_rad:
        Zenith angle at the segment's lower endpoint [rad].  ``π/2`` for a
        level arm (where no ``sec`` factor is applied).
    h_low_m, h_high_m:
        Integration limits actually used [m MSL] — the endpoint altitudes
        clipped into the atmosphere.  Equal for a level arm.
    negligible:
        ``True`` when the path carries so little turbulence that ``r0_m`` was
        saturated at :data:`R0_NEGLIGIBLE_M`.  Callers omit the turbulence
        term entirely in that case.
    detail:
        Human-readable one-liner for provenance and log messages.
    """

    r0_m: float
    cn2_path_integral_m13: float
    wavelength_m: float
    wave_type: str
    zeta_low_rad: float
    h_low_m: float
    h_high_m: float
    negligible: bool
    detail: str


def fried_parameter_from_integral_m(integral_m13: float, wavelength_m: float) -> float:
    """Reduce a weighted path integral [m^(1/3)] to ``r0`` [m].

    ``r0 = [0.423 k² I]^(-3/5)`` with ``k = 2π/λ``.  Returns
    :data:`R0_NEGLIGIBLE_M` when ``I`` is zero or small enough that the exact
    value would exceed it (see :data:`R0_NEGLIGIBLE_M` for why that is a
    physical saturation, not a silent clip).
    """
    if wavelength_m <= 0.0 or not math.isfinite(wavelength_m):
        raise ParameterBoundsError(
            what=f"fried_parameter_from_integral_m: wavelength_m = {wavelength_m} m",
            why="The Fried parameter is defined at a positive, finite wavelength.",
            action="Pass a positive wavelength in metres.",
            context={"wavelength_m": wavelength_m},
        )
    if integral_m13 < 0.0 or not math.isfinite(integral_m13):
        raise ParameterBoundsError(
            what=(
                f"fried_parameter_from_integral_m: integral = {integral_m13} m^(1/3) "
                "is negative or non-finite"
            ),
            why="Cn² is non-negative and the weight is non-negative, so the "
            "weighted path integral cannot be negative — this indicates a "
            "corrupt profile or quadrature.",
            action="Check the Cn² profile for negative samples.",
            context={"integral_m13": integral_m13},
        )
    if integral_m13 == 0.0:
        return R0_NEGLIGIBLE_M
    k = 2.0 * math.pi / wavelength_m
    r0 = (FRIED_COEFFICIENT * k * k * integral_m13) ** (-3.0 / 5.0)
    return min(r0, R0_NEGLIGIBLE_M)


def path_fried_parameter_from_los(
    los: LineOfSightGeometry,
    profile: Cn2Profile,
    wavelength_m: float,
    wave_type: str = "plane",
) -> PathFriedParameter:
    """Compute the path-weighted Fried parameter for *los* through *profile*.

    Parameters
    ----------
    los:
        Scene line of sight.  Must carry ``h_sensor`` (guardrail G2: the
        sensor endpoint has exactly one home — the LOS contract).
    profile:
        A :class:`~radiant.atmosphere.cn2_profiles.Cn2Profile`.
    wavelength_m:
        Wavelength to quote ``r0`` at [m].
    wave_type:
        ``"plane"`` (default) or ``"spherical"``; see the module docstring
        for the exact weighting convention.

    Raises
    ------
    ParameterBoundsError
        Missing ``h_sensor``, a non-positive wavelength, an unknown
        ``wave_type``, or a lower-endpoint zenith past the column airmass
        ceiling (89.5°) on a non-level path.
    """
    if wave_type not in WAVE_TYPES:
        raise ParameterBoundsError(
            what=f"path_fried_parameter_from_los: wave_type = {wave_type!r} is unknown",
            why=(
                "The path weighting is either plane-wave (source at infinity, the "
                "imaging case) or spherical-wave (finite-range point source)."
            ),
            action=f"Set wave_type to one of {', '.join(WAVE_TYPES)}.",
            context={"wave_type": wave_type},
        )
    if wavelength_m <= 0.0 or not math.isfinite(wavelength_m):
        raise ParameterBoundsError(
            what=f"path_fried_parameter_from_los: wavelength_m = {wavelength_m} m",
            why="The Fried parameter is defined at a positive, finite wavelength.",
            action="Pass a positive wavelength in metres.",
            context={"wavelength_m": wavelength_m},
        )
    if los.h_sensor is None:
        raise ParameterBoundsError(
            what=(
                "path_fried_parameter_from_los: the LineOfSightGeometry does not "
                f"carry the sensor endpoint (h_sensor is None; h_tgt = {los.h_tgt} m)"
            ),
            why=(
                "The turbulence path is the segment between the two endpoints; "
                "without the sensor endpoint there is no segment.  Reading "
                "geometry.sensor_altitude_m from the ParameterSet instead is what "
                "guardrail G2 (plan §3.5) deletes."
            ),
            action=(
                "Run the chain through GeometryStage, or pass h_sensor explicitly on "
                "a hand-built LineOfSightGeometry."
            ),
            context={"h_tgt": los.h_tgt, "theta_o": los.theta_o},
        )

    h_sensor = float(los.h_sensor)
    h_tgt = float(los.h_tgt)
    h_top = float(los.h_atm_top)
    direction = los.los_direction

    if direction == "level":
        return _level_arm_result(los, profile, wavelength_m, wave_type, h_sensor, h_top)

    if direction == "up":
        leg = observer_leg_from_los(los)
        spec = leg.spec
        assert isinstance(spec, ColumnSegmentSpec)  # level handled above
        zeta_low = spec.zeta_low_rad
        h_low_raw, h_high_raw = spec.h_low_m, spec.h_high_m
    else:  # "down" — the target is the lower endpoint, θ_o is its zenith.
        zeta_low = float(los.theta_o)
        h_low_raw, h_high_raw = h_tgt, h_sensor

    if zeta_low > ZENITH_CEILING_RAD:
        raise ParameterBoundsError(
            what=(
                f"path_fried_parameter_from_los: lower-endpoint zenith "
                f"{math.degrees(zeta_low):.4f}° exceeds the column airmass ceiling of "
                f"{math.degrees(ZENITH_CEILING_RAD):.1f}°"
            ),
            why=(
                "The path integral converts vertical thickness to path length with "
                "sec(ζ), which diverges at the horizon and stops describing a real "
                "path well before it.  Returning a plausible-looking number there "
                "would be a silent physics failure (Rule 17)."
            ),
            action=(
                "Move the line of sight away from the horizon, or express a "
                "constant-altitude path as a level scene (h_sensor == h_tgt), which "
                "integrates along the true arm length and needs no airmass."
            ),
            context={
                "zeta_low_rad": zeta_low,
                "zenith_ceiling_rad": ZENITH_CEILING_RAD,
                "los_direction": direction,
            },
        )

    # Clip the segment to the atmosphere.  Above h_atm_top the profile
    # contributes nothing that RADIANT models (and the Cn² profiles have
    # decayed by 10+ decades there anyway).
    h_low = max(h_low_raw, 0.0)
    h_high = min(h_high_raw, h_top)

    if h_high <= h_low:
        # The whole segment sits above the atmosphere: the space-observer
        # vacuum limit.  Finite huge r0, not an error (G4).
        return PathFriedParameter(
            r0_m=R0_NEGLIGIBLE_M,
            cn2_path_integral_m13=0.0,
            wavelength_m=wavelength_m,
            wave_type=wave_type,
            zeta_low_rad=zeta_low,
            h_low_m=h_low_raw,
            h_high_m=h_high_raw,
            negligible=True,
            detail=(
                f"{direction}-looking path {h_low_raw:.1f} → {h_high_raw:.1f} m MSL "
                f"lies entirely above h_atm_top = {h_top:.1f} m: vacuum, "
                f"r0 saturated at {R0_NEGLIGIBLE_M:g} m"
            ),
        )

    _warn_if_outside_coverage(profile, h_low, h_high)

    weight = _weight_function(wave_type, h_tgt=h_tgt, h_sensor=h_sensor)

    def integrand(h: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        return profile.cn2(h) * weight(h)

    raw = _converged_integral(integrand, h_low, h_high, profile.breakpoints_m)
    integral = raw / math.cos(zeta_low)

    r0 = fried_parameter_from_integral_m(integral, wavelength_m)
    negligible = r0 >= R0_NEGLIGIBLE_M
    return PathFriedParameter(
        r0_m=r0,
        cn2_path_integral_m13=integral,
        wavelength_m=wavelength_m,
        wave_type=wave_type,
        zeta_low_rad=zeta_low,
        h_low_m=h_low,
        h_high_m=h_high,
        negligible=negligible,
        detail=(
            f"{direction}-looking {wave_type}-wave r0 = {r0:.4g} m at "
            f"{wavelength_m * 1e6:.3f} µm over {h_low:.1f}–{h_high:.1f} m MSL, "
            f"lower-endpoint zenith {math.degrees(zeta_low):.4f}°, "
            f"∫Cn²W ds = {integral:.4g} m^(1/3) [{profile.describe()}]"
        ),
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _level_arm_result(
    los: LineOfSightGeometry,
    profile: Cn2Profile,
    wavelength_m: float,
    wave_type: str,
    altitude_m: float,
    h_top: float,
) -> PathFriedParameter:
    """Constant-altitude arm: integrate along the arm, no airmass factor."""
    leg = observer_leg_from_los(los)
    spec = leg.spec
    assert isinstance(spec, LevelArmSpec)
    length_m = float(spec.length_m)

    if altitude_m >= h_top:
        integral = 0.0
    else:
        _warn_if_outside_coverage(profile, altitude_m, altitude_m)
        cn2_here = float(profile.cn2(np.array([altitude_m], dtype=np.float64))[0])
        mean_weight = 1.0 if wave_type == "plane" else SPHERICAL_LEVEL_WEIGHT
        integral = cn2_here * length_m * mean_weight

    r0 = fried_parameter_from_integral_m(integral, wavelength_m)
    negligible = r0 >= R0_NEGLIGIBLE_M
    return PathFriedParameter(
        r0_m=r0,
        cn2_path_integral_m13=integral,
        wavelength_m=wavelength_m,
        wave_type=wave_type,
        zeta_low_rad=math.pi / 2.0,
        h_low_m=altitude_m,
        h_high_m=altitude_m,
        negligible=negligible,
        detail=(
            f"level {wave_type}-wave r0 = {r0:.4g} m at {wavelength_m * 1e6:.3f} µm "
            f"over a {length_m:.1f} m arm at {altitude_m:.1f} m MSL, "
            f"∫Cn²W ds = {integral:.4g} m^(1/3) [{profile.describe()}]"
        ),
    )


def _weight_function(
    wave_type: str,
    *,
    h_tgt: float,
    h_sensor: float,
) -> Callable[[npt.NDArray[np.float64]], npt.NDArray[np.float64]]:
    """Return ``W(h)`` for the requested wave type (see the module docstring)."""
    if wave_type == "plane":
        return lambda h: np.ones_like(h)

    span = h_sensor - h_tgt  # non-zero: level paths never reach here
    return lambda h: np.clip((h - h_tgt) / span, 0.0, 1.0) ** (5.0 / 3.0)


def _warn_if_outside_coverage(profile: Cn2Profile, h_low: float, h_high: float) -> None:
    """Rule 17: a tabulated profile that does not span the path says so."""
    coverage = profile.coverage_m
    if coverage is None:
        return
    c_low, c_high = coverage
    span = max(h_high - h_low, 0.0)
    uncovered = max(c_low - h_low, 0.0) + max(h_high - c_high, 0.0)
    if span > 0.0 and uncovered <= _COVERAGE_WARN_FRACTION * span:
        return
    if span == 0.0 and c_low <= h_low <= c_high:
        return
    warnings.warn(
        f"Cn² profile covers {c_low:.1f}–{c_high:.1f} m MSL but the turbulence path "
        f"spans {h_low:.1f}–{h_high:.1f} m MSL; {uncovered:.1f} m of vertical extent "
        "is outside the table and contributes ZERO Cn² (RADIANT does not extrapolate "
        "a tabulated profile). The reported r0 is therefore an upper bound on the "
        "true coherence diameter. Extend the table to cover the path to remove this "
        "warning.",
        UserWarning,
        stacklevel=3,
    )


def _converged_integral(
    integrand: Callable[[npt.NDArray[np.float64]], npt.NDArray[np.float64]],
    a: float,
    b: float,
    breakpoints_m: tuple[float, ...],
) -> float:
    """Trapezoidal quadrature on a graded grid, refined until it converges.

    The grid is the union of a uniform grid, a cubically-graded grid packed
    toward the lower endpoint (where the 100 m surface-layer scale height
    lives), and any profile breakpoints inside ``[a, b]``.  Grid density is
    doubled until the relative change falls below ``1e-6``; failure to
    converge raises rather than returning an unvalidated number (Rule 17).
    """
    inside = tuple(x for x in breakpoints_m if a < x < b)

    def evaluate(n: int) -> float:
        u = np.linspace(0.0, 1.0, n)
        nodes = np.concatenate(
            [
                a + (b - a) * u,
                a + (b - a) * u**3,
                np.asarray(inside, dtype=np.float64),
            ]
        )
        grid = np.unique(nodes)
        return float(np.trapezoid(integrand(grid), grid))

    n_nodes = _QUAD_START_NODES
    previous = evaluate(n_nodes)
    for _ in range(_QUAD_MAX_DOUBLINGS):
        n_nodes *= 2
        current = evaluate(n_nodes)
        # Both-zero (a vacuum span) satisfies this test exactly: 0 <= 0.
        if abs(current - previous) <= _QUAD_RTOL * max(abs(current), abs(previous)):
            return current
        previous = current
    raise ParameterBoundsError(
        what=(
            f"_converged_integral: the Cn² path integral over [{a}, {b}] m did not "
            f"converge to {_QUAD_RTOL:g} relative after {_QUAD_MAX_DOUBLINGS} grid "
            f"doublings (last estimate {previous:.6g} m^(1/3))"
        ),
        why=(
            "The quadrature refines until successive estimates agree; failing that "
            "test means the Cn² profile has structure finer than the grid can "
            "resolve (e.g. a table with near-duplicate altitudes, or a "
            "many-decade jump between adjacent samples).  Returning the "
            "unconverged number would be a silent accuracy failure (Rule 17)."
        ),
        action=(
            "Smooth or re-sample the Cn² profile so adjacent samples differ by less "
            "than a few decades, or reduce the altitude span of the path."
        ),
        context={"h_low_m": a, "h_high_m": b, "rtol": _QUAD_RTOL},
    )
