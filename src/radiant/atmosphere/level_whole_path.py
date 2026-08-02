"""The whole traversed path of a level LOS, evaluated as **one** optical path.

One computation, one module (Rule 19): the optical path a level line of sight
actually runs through, from the sensor out to the top of the modelled column,
as a single segment — descending half-chord, ascending half-chord, then the
ascending continuation, all about one perigee.

Why this is not :mod:`radiant.atmosphere.level_arm`
---------------------------------------------------
Both describe a level geometry, but they are different paths and both are
needed (Rule 27 — neither supersedes the other):

===========================  ===================================  ==============
Path                         Endpoints                            Module
===========================  ===================================  ==============
Observer leg                 sensor ↔ target                      ``level_arm``
Whole traversed LOS          sensor → … → ``h_atm_top``           **this module**
===========================  ===================================  ==============

``level_arm`` supplies the τ that attenuates the target and the ``L_path`` that
adds to it; this module supplies the **sky background** — what the aperture
would measure if the target were not there.  They answer different questions
about the same geometry.

Why one segment rather than two (CU-224 / ex-CU-276)
----------------------------------------------------
The level sky used to be assembled as ``L_arm→sensor + τ_arm · L_continuation``
— the arm from :mod:`radiant.atmosphere.level_arm`, the continuation from
:mod:`radiant.atmosphere.segment_grazing`, joined at the **target plane**.  That
composition is exact radiative transfer, but the segment model being composed is
not additive: each segment emits ``(1 − τ_seg)·B(T_eff(h_seg))`` with its own
effective temperature and its own species weights, so putting the join at the
target replaces part of one graybody with two different ones.  CU-254 removed
exactly that join from the up-looking sky (a measured 12.3 % under-report, always
the same sign, so optimistic SCNR); the level branch kept it because nothing in
RADIANT could evaluate "constant-altitude arm then ascending arc" as one path.
This module is that evaluator.

Why the obvious fix was wrong
-----------------------------
Rooting a single ascending arc at the sensor (``r_tangent = R_E + h_sensor``),
the way the up-looking branch does, drops the constant-altitude arm entirely: a
level ray is tangent at the **chord midpoint**, not at the sensor, so the sensor
sits on its *descending* half.  Measured in sea-level-equivalent molecular
column, a sensor-rooted arc recovers only

=========  ==========  ================================
arm        altitude    sensor-rooted / true traversed
=========  ==========  ================================
8 km       0 m         1.014  (degenerate — see below)
100 km     3 km        0.830
150 km     10 km       0.751
=========  ==========  ================================

so it would have shed up to 25 % of the column to close a 12 % composition
error.  The correct path is the whole thing about the real perigee.  (The
sea-level row is the exception and inverts: its perigee is 1.3 m *below* the
ellipsoid, so the true path is the clamped one and the sensor-rooted arc comes
out marginally longer.  CU-276 filed 0.986 there from an unclamped integral and
corrected it to 1.014 on re-audit.)

Geometry
--------
For endpoints at radius ``r_arm = R_E + h_arm`` separated by a chord of length
``L``, the perpendicular from the Earth centre falls at the chord midpoint, so
the perigee radius is

.. math::  r_p = \\sqrt{r_{arm}^2 - (L/2)^2}

(equivalently ``r_arm − Δh`` with the familiar sag ``Δh ≈ L²/8r_arm``).  Arc
length measured from the perigee is ``s = √(r² − r_p²)``, so the sensor sits at
``s = L/2`` exactly.  Because the integrand is even in ``s``, the whole
traversed path's density-weighted column is, per species,

.. math::  S_i \\;=\\; 2\\,S(r_p;\\, h_p \\to h_{arm};\\, H_i)
                  \\;+\\; S(r_p;\\, h_{arm} \\to h_{top};\\, H_i)

which this module forms as ``S(h_p→h_arm) + S(h_p→h_top)``.  The optical depth
is then assembled with the same per-species effective air mass
(:mod:`radiant.atmosphere.near_horizon_air_mass`) the near-horizon column and
the grazing arc use, so all three agree by construction where they overlap — and
a zero-length arm reduces this module **exactly** to
:func:`radiant.atmosphere.segment_grazing.evaluate_grazing_segment` at ζ = π/2.

Sub-surface perigee
-------------------
A level path at low altitude dips below mean sea level: at ``h_arm = 0`` any
non-zero arm does.  The modelled column has no air below MSL, so the integration
floor is clamped there and a ``UserWarning`` names the depth (Rule 17 — no
silent clipping).  The clamp under-states the column by at most
``exp(|h_p| / H_h2o) − 1``; for the 8 km arm at sea level the perigee is 1.3 m
down and the effect is 0.07 %.  The Phase-1 horizon guard already bounds the sag
to 2 km, and raises beyond.
"""

from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np

from radiant.atmosphere.grazing_column import grazing_slant_column_km
from radiant.atmosphere.near_horizon_air_mass import SpeciesAirMass, apply_species_air_mass
from radiant.atmosphere.segment_simple import DEFAULT_H_ATM_TOP_M
from radiant.atmosphere.segment_single_scatter import (
    COS_HORIZON_TOLERANCE,
    cos_scattering_angle,
    segment_single_scatter_radiance,
)
from radiant.atmosphere.segment_thermal import segment_thermal_emission
from radiant.atmosphere.segments import SegmentQuantities, validate_wavelength_grid
from radiant.atmosphere.simple import H_AER_M, H_H2O_M, H_MOL_M, SimpleAtmosphere
from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError

__all__ = [
    "LEVEL_PATH_ZENITH_RAD",
    "evaluate_level_whole_path",
    "level_path_perigee_radius_m",
    "level_whole_path_optical_depth",
]

#: The local zenith of a level LOS at its endpoints, by definition.  Consumed
#: only by the single-scatter phase angle; the optical path comes from the
#: perigee radius, not from this angle.
LEVEL_PATH_ZENITH_RAD: float = math.pi / 2.0


def level_path_perigee_radius_m(altitude_m: float, arm_length_m: float) -> float:
    """Perigee radius of the chord between two points at *altitude_m* [m].

    ``r_p = √(r_arm² − (L/2)²)`` — the perpendicular from the Earth centre falls
    at the chord midpoint because the triangle is isoceles.

    Raises
    ------
    ParameterBoundsError
        On a non-finite input, a negative altitude, a negative arm, or an arm so
        long that the chord would pass through the Earth centre.
    """
    for name, value in (("altitude_m", altitude_m), ("arm_length_m", arm_length_m)):
        if not math.isfinite(value) or value < 0.0:
            raise ParameterBoundsError(
                what=f"level_path_perigee_radius_m: {name} = {value} is not a finite value >= 0",
                why="A level path has a non-negative altitude and a non-negative chord length.",
                action=f"Pass a finite, non-negative {name}.",
                context={name: value},
            )
    r_arm = R_EARTH_M + altitude_m
    half = 0.5 * arm_length_m
    if half >= r_arm:
        raise ParameterBoundsError(
            what=(
                f"level_path_perigee_radius_m: arm_length_m = {arm_length_m} m is at or past "
                f"twice the endpoint radius ({2.0 * r_arm} m)"
            ),
            why=(
                "The chord between two points on a sphere is shorter than the diameter; a "
                "longer one is not a path on this Earth."
            ),
            action="Reduce arm_length_m below 2*(R_E + altitude_m).",
            context={"arm_length_m": arm_length_m, "r_arm_m": r_arm},
        )
    return float(math.sqrt(r_arm * r_arm - half * half))


def level_whole_path_optical_depth(
    atmosphere: SimpleAtmosphere,
    wavelength_um: np.ndarray,
    *,
    altitude_m: float,
    arm_length_m: float,
    h_atm_top_m: float = DEFAULT_H_ATM_TOP_M,
) -> tuple[np.ndarray, SpeciesAirMass, dict[str, float]]:
    """Slant optical depth of the whole traversed level path [dimensionless].

    Returns ``(od_slant, masses, geometry)``.  See the module docstring for the
    ``2·S(h_p→h_arm) + S(h_arm→h_top)`` construction and for the sub-surface
    perigee clamp.

    Warns
    -----
    UserWarning
        When the chord's perigee falls below mean sea level, so the integration
        floor is clamped there.
    """
    lam = np.asarray(wavelength_um, dtype=np.float64)
    r_p = level_path_perigee_radius_m(altitude_m, arm_length_m)
    h_p = r_p - R_EARTH_M
    h_floor = h_p
    if h_p < 0.0:
        warnings.warn(
            f"level_whole_path: the chord between two points at {altitude_m:.1f} m MSL "
            f"{arm_length_m:.1f} m apart dips {-h_p:.2f} m BELOW mean sea level at its "
            "midpoint. The modelled atmosphere has no air below MSL, so the integration "
            "floor is clamped to 0 m; the sub-surface sliver is not counted, which "
            "under-states the column by at most "
            f"{math.expm1(-h_p / H_H2O_M) * 100.0:.3f} % (water vapour, the shallowest "
            "profile). Raise the endpoint altitude or shorten the path to avoid the clamp.",
            UserWarning,
            stacklevel=3,
        )
        h_floor = 0.0

    columns: dict[str, float] = {}
    slants: dict[str, float] = {}
    for key, scale_height in (("mol", H_MOL_M), ("aer", H_AER_M), ("h2o", H_H2O_M)):
        # S(h_floor -> h_arm) + S(h_floor -> h_top) == 2*S(h_floor -> h_arm)
        #                                              + S(h_arm -> h_top)
        near = grazing_slant_column_km(r_p, h_floor, altitude_m, scale_height)
        far = grazing_slant_column_km(r_p, h_floor, h_atm_top_m, scale_height)
        slants[key] = near + far
        columns[key] = atmosphere._column_length_km(h_floor, h_atm_top_m, scale_height)

    masses = SpeciesAirMass(
        m_mol=slants["mol"] / columns["mol"] if columns["mol"] > 0.0 else 1.0,
        m_aer=slants["aer"] / columns["aer"] if columns["aer"] > 0.0 else 1.0,
        m_h2o=slants["h2o"] / columns["h2o"] if columns["h2o"] > 0.0 else 1.0,
        r_tangent_m=r_p,
        slant_column_mol_km=slants["mol"],
        slant_column_aer_km=slants["aer"],
        slant_column_h2o_km=slants["h2o"],
    )
    od = apply_species_air_mass(
        masses,
        od_vert_mol=atmosphere._rayleigh_extinction_km(lam, 0.0) * columns["mol"],
        od_vert_aer=atmosphere._aerosol_extinction_km(lam, 0.0) * columns["aer"],
        od_vert_h2o=atmosphere._h2o_vertical_od(lam, columns["h2o"]),
        od_vert_gas=atmosphere._gas_floor_vertical_od(lam, columns["mol"]),
    )
    geometry = {
        "col_length_mol_km": columns["mol"],
        "col_length_aer_km": columns["aer"],
        "col_length_h2o_km": columns["h2o"],
        "perigee_altitude_m": h_p,
        "integration_floor_m": h_floor,
        "tangent_depression_m": altitude_m - h_p,
        **masses.as_provenance(),
    }
    return od, masses, geometry


def evaluate_level_whole_path(
    atmosphere: SimpleAtmosphere,
    wavelength_um: np.ndarray,
    *,
    altitude_m: float,
    arm_length_m: float,
    theta_s_rad: float | None = None,
    delta_phi_rad: float = 0.0,
    h_atm_top_m: float = DEFAULT_H_ATM_TOP_M,
) -> SegmentQuantities:
    """Evaluate the whole traversed level path into its directional products.

    Parameters
    ----------
    atmosphere:
        The configured :class:`~radiant.atmosphere.simple.SimpleAtmosphere`.
    wavelength_um:
        1-D strictly-ascending, strictly-positive chain wavelength grid [µm].
    altitude_m:
        Altitude of the two level endpoints [m] — the sensor and the target.
    arm_length_m:
        True chord length between them [m].  It fixes the ray: a level LOS has
        one perigee per range, so this is the ray parameter, not a split point.
    theta_s_rad:
        Solar zenith at the sensor [rad], or ``None`` for a pure-thermal
        evaluation.
    delta_phi_rad:
        Relative azimuth ``φ_s − φ_o`` in the **segment's** frame [rad], i.e.
        referenced to the sensor → space travel direction.
    h_atm_top_m:
        Top of the modelled column [m].

    Returns
    -------
    SegmentQuantities
        ``tau`` (reciprocal) plus the two directional radiance products
        [W/m²/sr/µm].  ``L_toward_lower`` is what the **sensor** sees — the
        radiance emerging at the near, lower-altitude end of the path.

    Raises
    ------
    ParameterBoundsError
        On an invalid wavelength grid, a non-positive ``h_atm_top_m``, or an
        unphysical level geometry (see :func:`level_path_perigee_radius_m`).
    """
    lam = validate_wavelength_grid(wavelength_um, "evaluate_level_whole_path")
    if not math.isfinite(h_atm_top_m) or h_atm_top_m <= 0.0:
        raise ParameterBoundsError(
            what=(
                f"evaluate_level_whole_path: h_atm_top_m = {h_atm_top_m} m is not positive-finite"
            ),
            why="The top of the modelled column is a positive altitude.",
            action=f"Pass a positive h_atm_top_m (default {DEFAULT_H_ATM_TOP_M:g} m).",
            context={"h_atm_top_m": h_atm_top_m},
        )

    provenance: dict[str, Any] = {
        "segment_kind": "level_whole_path",
        "altitude_m": altitude_m,
        "arm_length_m": arm_length_m,
        "h_atm_top_m": h_atm_top_m,
        "model": "simple",
        "visibility_km": atmosphere.visibility_km,
        "aerosol_type": atmosphere.aerosol_type,
        "precipitable_water_cm": atmosphere.precipitable_water_cm,
        "standard_atmosphere": atmosphere.standard_atmosphere,
    }

    if altitude_m >= h_atm_top_m:
        zeros = np.zeros_like(lam)
        provenance["vacuum_reason"] = "level path at or above h_atm_top"
        return SegmentQuantities(
            wavelength_um=lam,
            tau=np.ones_like(lam),
            L_toward_upper=zeros,
            L_toward_lower=zeros.copy(),
            provenance=provenance,
        )

    od, masses, geometry = level_whole_path_optical_depth(
        atmosphere,
        lam,
        altitude_m=altitude_m,
        arm_length_m=arm_length_m,
        h_atm_top_m=h_atm_top_m,
    )
    tau = np.exp(-od)
    provenance.update(geometry)

    # One graybody for the whole path — this is the point of the module.  The
    # emission-height temperature is keyed to the sensor end, where the radiance
    # emerges and where the CU-155 fit is referenced.
    t_eff_K = atmosphere._downwelling_effective_temperature_K(altitude_m)
    provenance["t_eff_K"] = t_eff_K
    thermal = segment_thermal_emission(lam, tau, t_eff_K)

    scat_up, scat_dn, scatter_prov = _whole_path_single_scatter_terms(
        atmosphere,
        lam,
        tau,
        masses,
        altitude_m=altitude_m,
        theta_s_rad=theta_s_rad,
        delta_phi_rad=delta_phi_rad,
    )
    provenance.update(scatter_prov)

    return SegmentQuantities(
        wavelength_um=lam,
        tau=tau,
        L_toward_upper=thermal + scat_up,
        L_toward_lower=thermal + scat_dn,
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _whole_path_single_scatter_terms(
    atmosphere: SimpleAtmosphere,
    lam: np.ndarray,
    tau: np.ndarray,
    masses: SpeciesAirMass,
    *,
    altitude_m: float,
    theta_s_rad: float | None,
    delta_phi_rad: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Directional scattered-solar radiances for the whole path, plus provenance.

    Species weights sit at the path's endpoint altitude — the lower-endpoint
    convention every evaluator now shares (CU-260) — and the scattering angle
    uses the level zenith π/2, because the ``(1 − τ)`` source is dominated by
    the dense air along the arm rather than by the thin continuation above it.

    The CU-161 water and gas terms are linearised against the path's own
    **slant** columns, which since CU-320 is the convention all three path
    evaluators share — :mod:`radiant.atmosphere.segment_grazing` and
    :mod:`radiant.atmosphere.segment_simple`.  That choice is what makes a
    zero-length arm reduce to the grazing evaluator array-for-array, i.e. what
    makes the level and ascending sky topologies join without a step; it differs
    from :mod:`radiant.atmosphere.level_arm`, which linearises against the
    vertical column above the arm because it describes a *different* path (the
    observer leg) whose weights must be a property of altitude alone.
    """
    prov: dict[str, Any] = {"theta_s_rad": theta_s_rad, "delta_phi_rad": delta_phi_rad}
    if theta_s_rad is None:
        prov["scattered_solar"] = "omitted (no solar geometry supplied)"
        zeros = np.zeros_like(lam)
        return zeros, zeros.copy(), prov

    cos_theta_sun = math.cos(theta_s_rad)
    prov["cos_theta_sun"] = cos_theta_sun
    if cos_theta_sun <= COS_HORIZON_TOLERANCE:
        prov["scattered_solar"] = "zero (sun at or below the local horizon)"
        zeros = np.zeros_like(lam)
        return zeros, zeros.copy(), prov

    s_mol = masses.slant_column_mol_km
    s_h2o = masses.slant_column_h2o_km
    sigma_mol = atmosphere._rayleigh_extinction_km(lam, altitude_m)
    sigma_aer = atmosphere._aerosol_extinction_km(lam, altitude_m)
    sigma_h2o = (atmosphere._h2o_vertical_od(lam, s_h2o) / max(s_h2o, 1e-12)) * math.exp(
        -altitude_m / H_H2O_M
    )
    sigma_gas = (atmosphere._gas_floor_vertical_od(lam, s_mol) / max(s_mol, 1e-12)) * math.exp(
        -altitude_m / H_MOL_M
    )
    prov["weight_altitude_m"] = altitude_m

    omega0 = atmosphere._single_scattering_albedo(sigma_mol, sigma_aer, sigma_h2o, sigma_gas)
    cos_up = cos_scattering_angle(LEVEL_PATH_ZENITH_RAD, theta_s_rad, delta_phi_rad, "toward_upper")
    cos_dn = cos_scattering_angle(LEVEL_PATH_ZENITH_RAD, theta_s_rad, delta_phi_rad, "toward_lower")
    prov["cos_scatter_toward_upper"] = cos_up
    prov["cos_scatter_toward_lower"] = cos_dn

    phase_up = atmosphere._single_scatter_phase_function(cos_up, sigma_mol, sigma_aer)
    phase_dn = atmosphere._single_scatter_phase_function(cos_dn, sigma_mol, sigma_aer)
    scat_up = segment_single_scatter_radiance(lam, tau, omega0, phase_up, cos_theta_sun)
    scat_dn = segment_single_scatter_radiance(lam, tau, omega0, phase_dn, cos_theta_sun)
    return scat_up, scat_dn, prov
