"""Sky radiance along a line of sight — the ``SkyBackground`` source term.

One computation, one module (Rule 19): the radiance a receiver at altitude
``h_start`` sees when it looks **up** along a ray of zenith ``ζ``, with
nothing behind the atmosphere but cold space.

Composition
-----------
The ray is exactly one path segment — the column from the receiver to the top
of the modelled atmosphere — read in the downward direction::

    L_sky(h_start, ζ) = SegmentQuantities(
        ColumnSegmentSpec(h_start, h_atm_top, ζ)
    ).L_toward_lower   +   τ_segment · L_beyond

and ``L_beyond ≡ 0``: above ``h_atm_top`` the LOS terminates on cold space
(2.7 K cosmic background contributes < 1e-9 W/m²/sr/µm anywhere in the
0.3–14 µm working range and is deliberately not modelled).  Composition is
therefore a no-op here, which is why this module is a thin, well-named wrapper
rather than a second physics implementation: all the physics lives in
:mod:`radiant.atmosphere.segment_simple`.

This is the Gap 108 product.  It is what a ground- or air-based sensor
looking upward sees behind an airborne target, and it is a **background
radiance** [W/m²/sr/µm], not the hemispheric downwelling irradiance
``AtmosphericQuantities.E_sky_thermal`` [W/m²/µm] that the existing
down-looking assembly uses for surface reflection.  The two are different
products with different units and different geometry; nothing here modifies
or replaces the existing one (zero drift).

Band gating (plan §8.3 answer 3)
--------------------------------
The **thermal** component is first-class at first delivery: it is anchored
directly against real MODTRAN up-looking runs.  The **scattered-solar**
component rests on a single-scatter approximation that is known to
under-predict the daytime VIS/NIR sky, where multiple scattering dominates.
A ``UserWarning`` is therefore emitted whenever the evaluation grid extends
below :data:`SCATTERED_SKY_PROVISIONAL_MAX_UM` (3 µm) **and** a solar geometry
is supplied with the sun above the local horizon — i.e. exactly when the
provisional component can contribute.  A pure-thermal MWIR/LWIR call warns
about nothing.
"""

from __future__ import annotations

import math
import warnings

import numpy as np

from radiant.atmosphere.segment_simple import DEFAULT_H_ATM_TOP_M, evaluate_column_segment
from radiant.atmosphere.segment_single_scatter import COS_HORIZON_TOLERANCE
from radiant.atmosphere.segments import ColumnSegmentSpec, validate_wavelength_grid
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.core.parameters import ParameterBoundsError

__all__ = [
    "SCATTERED_SKY_PROVISIONAL_MAX_UM",
    "sky_radiance_along_los",
    "warn_if_scattered_sky_provisional",
]

# Wavelengths below this carry the provisional-scattered-sky warning.  It is
# the MWIR band edge: at and above it the sky radiance the model returns is
# thermal-dominated and MODTRAN-anchored; below it the single-scatter solar
# term is the dominant contributor and is known to be low.
SCATTERED_SKY_PROVISIONAL_MAX_UM: float = 3.0


def sky_radiance_along_los(
    atmosphere: SimpleAtmosphere,
    wavelength_um: np.ndarray,
    h_start_m: float,
    zeta_rad: float,
    *,
    theta_s_rad: float | None = None,
    delta_phi_rad: float = 0.0,
    h_atm_top_m: float = DEFAULT_H_ATM_TOP_M,
) -> np.ndarray:
    """Sky radiance seen looking up from ``h_start_m`` along ``zeta_rad``.

    Parameters
    ----------
    atmosphere:
        The configured :class:`~radiant.atmosphere.simple.SimpleAtmosphere`.
    wavelength_um:
        1-D strictly-ascending, strictly-positive chain wavelength grid [µm].
    h_start_m:
        Altitude of the receiver above MSL [m], ``≥ 0``.  At or above
        ``h_atm_top_m`` the result is exactly zero (looking up from vacuum
        into vacuum).
    zeta_rad:
        Zenith angle of the ray at the receiver [rad], the segment's lower
        endpoint.  ``0`` is straight up.  Bounded by the column airmass
        ceiling (89.5°); a near-horizontal sky ray must be composed from a
        level arm plus a column, not requested here.
    theta_s_rad:
        Solar zenith at the receiver [rad], or ``None`` for a pure-thermal
        sky (no scattered-solar contribution at all, and no warning).
    delta_phi_rad:
        Relative azimuth ``φ_s − φ_o`` [rad].
    h_atm_top_m:
        Top of the modelled atmospheric column [m].

    Returns
    -------
    np.ndarray
        Downward sky radiance at the receiver [W/m²/sr/µm], non-negative.

    Warns
    -----
    UserWarning
        When the grid extends below 3 µm and a sun above the local horizon is
        supplied — the scattered-solar component is provisional there.

    Raises
    ------
    ParameterBoundsError
        On an invalid grid, a negative ``h_start_m``, or a ``zeta_rad``
        outside the column segment's domain (the error names the level-arm
        alternative).
    """
    lam = validate_wavelength_grid(wavelength_um, "sky_radiance_along_los")
    if not math.isfinite(h_start_m) or h_start_m < 0.0:
        raise ParameterBoundsError(
            what=f"sky_radiance_along_los: h_start_m = {h_start_m} m is not a finite altitude ≥ 0",
            why="The receiver altitude is measured above mean sea level.",
            action="Set h_start_m ≥ 0 m.",
            context={"h_start_m": h_start_m},
        )

    warn_if_scattered_sky_provisional(lam, theta_s_rad)

    if h_start_m >= h_atm_top_m:
        # Looking up from vacuum: no emitting or scattering material at all.
        return np.zeros_like(lam)

    spec = ColumnSegmentSpec(
        h_low_m=float(h_start_m),
        h_high_m=float(h_atm_top_m),
        zeta_low_rad=float(zeta_rad),
    )
    segment = evaluate_column_segment(
        atmosphere,
        lam,
        spec,
        theta_s_rad=theta_s_rad,
        delta_phi_rad=delta_phi_rad,
        h_atm_top_m=h_atm_top_m,
    )
    # + τ · L_beyond with L_beyond ≡ 0 (cold space).  Written out rather than
    # elided so the composition rule is visible at the call site.
    return np.asarray(segment.L_toward_lower, dtype=np.float64)


def warn_if_scattered_sky_provisional(
    lam: np.ndarray,
    theta_s_rad: float | None,
) -> None:
    """Emit the plan §8.3 provisional-scattered-sky warning when applicable.

    Public because the band-gating *policy* must be applied wherever a sky
    radiance is produced, not only where this module produces it (CU-260):
    :mod:`radiant.atmosphere.uplooking_quantities` calls it directly on the
    near-horizon branch, where the sky comes from
    :mod:`radiant.atmosphere.segment_grazing` and never passes through
    :func:`sky_radiance_along_los`.  Keeping the predicate here — rather than
    duplicating it at each production site — is what stops the two from
    drifting apart.

    Exactly one call fires per scene: the two production branches are
    mutually exclusive.
    """
    if theta_s_rad is None:
        return
    if math.cos(theta_s_rad) <= COS_HORIZON_TOLERANCE:
        return  # night: no scattered component to be provisional about
    if not bool(np.any(lam < SCATTERED_SKY_PROVISIONAL_MAX_UM)):
        return
    warnings.warn(
        "sky_radiance_along_los: the scattered-solar component of the sky "
        f"radiance below {SCATTERED_SKY_PROVISIONAL_MAX_UM:g} µm is provisional "
        "— the simple model's single-scatter source underestimates the daytime "
        "sky, where multiple scattering dominates. The thermal component "
        "(MWIR/LWIR) is MODTRAN-anchored and is not affected. Use a MODTRAN or "
        "interpolated backend for quantitative VIS/NIR sky-background work "
        "(Geometry Flexibility plan §8.3 answer 3).",
        UserWarning,
        stacklevel=3,
    )
