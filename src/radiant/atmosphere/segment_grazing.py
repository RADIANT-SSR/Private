"""Grazing (near-tangent) ascending path segment — the beyond-the-ceiling arm.

One computation, one module (Rule 19): evaluate an ascending path segment
whose lower-endpoint zenith lies **past** ``ZENITH_CEILING_RAD`` (89.5°) into
a :class:`~radiant.atmosphere.segments.SegmentQuantities`.

Relationship to the other two segment evaluators
------------------------------------------------
============================  =============================  ==================
Topology                      Optical path                   Module
============================  =============================  ==================
Slant column, ζ ≤ 89.5°       vertical column × air mass     ``segment_simple``
Constant altitude             local extinction × chord       ``level_arm``
Ascending, ζ > 89.5°          true spherical slant integral  **this module**
============================  =============================  ==================

The three are genuinely different computations of the optical path (Rule 19),
which is why they are three modules rather than one with branches.  Everything
*downstream* of the optical path — the Kirchhoff thermal emission
(:mod:`radiant.atmosphere.segment_thermal`), the directional single-scatter
source (:mod:`radiant.atmosphere.segment_single_scatter`), and the CU-161
species model on :class:`~radiant.atmosphere.simple.SimpleAtmosphere` — is
shared verbatim, so the three agree by construction wherever their validity
windows overlap.

Optical depth
-------------
Structurally identical to
:func:`radiant.atmosphere.segment_simple.column_segment_optical_depth`, with
the single plane-parallel air mass replaced by a **per-species effective air
mass** derived from the exact spherical slant column
:func:`radiant.atmosphere.grazing_column.grazing_slant_column_km` —
see :func:`grazing_segment_optical_depth` for the formula and the reason the
CU-161 curve of growth stays on the vertical column.  A cross-model test
asserts that for a *non*-grazing geometry (ζ well inside the ceiling) this
module and ``segment_simple`` agree to better than a percent, which is the
statement that the spherical integral and the air-mass approximation describe
the same path.

Validity
--------
The segment must **ascend monotonically**: its tangent point is at or below
its lower endpoint, and the arc runs upward from there.  That covers both
Phase-2 consumers — the outward arm of a twilight solar transit and the LOS
continuation past a level target.  A path that descends through a tangent
point *inside* the segment is a limb transit, declined for v1.x (ADR-0011
decision 5), and the caller must reject it before getting here.

Zero drift
----------
Not reachable from any pre-existing evaluate path.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from radiant.atmosphere.near_horizon_air_mass import (
    apply_species_air_mass,
    near_horizon_species_air_mass,
)
from radiant.atmosphere.segment_simple import DEFAULT_H_ATM_TOP_M
from radiant.atmosphere.segment_single_scatter import (
    COS_HORIZON_TOLERANCE,
    cos_scattering_angle,
    segment_single_scatter_radiance,
)
from radiant.atmosphere.segment_thermal import segment_thermal_emission
from radiant.atmosphere.segments import (
    SegmentQuantities,
    validate_wavelength_grid,
)
from radiant.atmosphere.simple import (
    H_AER_M,
    H_H2O_M,
    H_MOL_M,
    SimpleAtmosphere,
)
from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError

__all__ = ["evaluate_grazing_segment", "grazing_segment_optical_depth"]


def grazing_segment_optical_depth(
    atmosphere: SimpleAtmosphere,
    wavelength_um: np.ndarray,
    r_tangent_m: float,
    h_low_m: float,
    h_high_m: float,
) -> tuple[np.ndarray, dict[str, float]]:
    """Slant optical depth of an ascending grazing arc [dimensionless].

    Returns ``(od_slant, geometry)`` where ``geometry`` carries the per-species
    vertical columns, spherical slant columns and the effective air masses
    that relate them (provenance).

    Construction — deliberately the *same* one
    :func:`radiant.atmosphere.segment_simple.column_segment_optical_depth`
    uses, with one generalisation::

        od = σ_mol(λ,0)·col_mol·m_mol
           + σ_aer(λ,0)·col_aer·m_aer
           + OD_h2o(λ, col_h2o)·m_h2o
           + OD_gas(λ, col_mol)·m_mol

    The vertical columns ``col_i`` and the CU-161 water curve-of-growth /
    well-mixed-gas floor are evaluated exactly as the plane-parallel model
    evaluates them — the curve of growth is applied to the **vertical** water
    column and then scaled, because that is the convention it was calibrated
    in.  The generalisation is that each species carries its **own** effective
    air mass

    .. math::  m_i = S_i(r_0;\\, h_{lo} \\to h_{hi};\\, H_i) \\;/\\; col_i

    instead of one shared plane-parallel factor.  On a spherical path species
    with different scale heights genuinely see different curvature — a 2 km
    water profile hugs the tangent point far more tightly than an 8 km
    molecular one — and collapsing them to a single air mass is precisely the
    approximation that fails past the 89.5° ceiling.  For a non-grazing
    geometry every ``m_i`` converges on the plane-parallel air mass and this
    reduces to the column model (asserted in ``test_segment_grazing.py``).

    Known limitation, shared with :mod:`radiant.atmosphere.level_arm`: scaling
    a curve-of-growth optical depth linearly in air mass under-states band
    saturation on very long paths.  The alternative (evaluating the curve of
    growth at the slant amount) is a *different* model from the calibrated
    one, and mixing the two would make the sky background jump discontinuously
    at the 89.5° hand-over.  Consistency with the calibration wins; the size
    of the residual is a MODTRAN batch-2 question.
    """
    lam = np.asarray(wavelength_um, dtype=np.float64)
    col_mol = atmosphere._column_length_km(h_low_m, h_high_m, H_MOL_M)
    col_aer = atmosphere._column_length_km(h_low_m, h_high_m, H_AER_M)
    col_h2o = atmosphere._column_length_km(h_low_m, h_high_m, H_H2O_M)

    masses = near_horizon_species_air_mass(
        r_tangent_m,
        h_low_m,
        h_high_m,
        col_mol_km=col_mol,
        col_aer_km=col_aer,
        col_h2o_km=col_h2o,
        scale_height_mol_m=H_MOL_M,
        scale_height_aer_m=H_AER_M,
        scale_height_h2o_m=H_H2O_M,
    )
    od = apply_species_air_mass(
        masses,
        od_vert_mol=atmosphere._rayleigh_extinction_km(lam, 0.0) * col_mol,
        od_vert_aer=atmosphere._aerosol_extinction_km(lam, 0.0) * col_aer,
        od_vert_h2o=atmosphere._h2o_vertical_od(lam, col_h2o),
        od_vert_gas=atmosphere._gas_floor_vertical_od(lam, col_mol),
    )
    geometry = {
        "col_length_mol_km": col_mol,
        "col_length_aer_km": col_aer,
        "col_length_h2o_km": col_h2o,
        **masses.as_provenance(),
    }
    return od, geometry


def evaluate_grazing_segment(
    atmosphere: SimpleAtmosphere,
    wavelength_um: np.ndarray,
    *,
    r_tangent_m: float,
    h_low_m: float,
    h_high_m: float,
    zeta_low_rad: float,
    theta_s_rad: float | None = None,
    delta_phi_rad: float = 0.0,
    h_atm_top_m: float = DEFAULT_H_ATM_TOP_M,
) -> SegmentQuantities:
    """Evaluate one ascending grazing arc into its directional products.

    Parameters
    ----------
    atmosphere:
        The configured :class:`~radiant.atmosphere.simple.SimpleAtmosphere`.
    wavelength_um:
        1-D strictly-ascending, strictly-positive chain wavelength grid [µm].
    r_tangent_m:
        Closest approach of the ray to the Earth centre [m].
    h_low_m, h_high_m:
        Altitudes of the near and far ends of the arc [m], ordered.
    zeta_low_rad:
        Zenith angle of the ray at ``h_low_m`` [rad].  Consumed **only** by
        the single-scatter phase angle — the optical path comes from the
        tangent radius, not from this angle — so it is legal here right up to
        π/2, unlike on a :class:`~radiant.atmosphere.segments.ColumnSegmentSpec`.
    theta_s_rad:
        Solar zenith at the arc's near end [rad], or ``None`` for a
        pure-thermal evaluation.
    delta_phi_rad:
        Relative azimuth ``φ_s − φ_o`` [rad] between the sun and the arc's
        lower-to-upper travel direction.
    h_atm_top_m:
        Top of the modelled column [m]; an arc starting at or above it is
        exact vacuum.

    Returns
    -------
    SegmentQuantities
        ``tau`` (reciprocal) plus the two directional radiance products.
    """
    lam = validate_wavelength_grid(wavelength_um, "evaluate_grazing_segment")
    if not math.isfinite(h_atm_top_m) or h_atm_top_m <= 0.0:
        raise ParameterBoundsError(
            what=f"evaluate_grazing_segment: h_atm_top_m = {h_atm_top_m} m is not positive-finite",
            why="The top of the modelled column is a positive altitude.",
            action=f"Pass a positive h_atm_top_m (default {DEFAULT_H_ATM_TOP_M:g} m).",
            context={"h_atm_top_m": h_atm_top_m},
        )
    if not math.isfinite(zeta_low_rad) or not (0.0 <= zeta_low_rad <= math.pi / 2.0):
        raise ParameterBoundsError(
            what=(
                f"evaluate_grazing_segment: zeta_low_rad = {zeta_low_rad} rad is outside [0, π/2]"
            ),
            why=(
                "This evaluator serves ascending arcs only: a lower-endpoint zenith "
                "past π/2 points downward, which is a descending (limb-transit) "
                "topology, declined for v1.x (ADR-0011 decision 5)."
            ),
            action=(
                "Pass the zenith of the ray at its lower endpoint measured from the "
                "local vertical, in [0, π/2]; reject limb transits upstream."
            ),
            context={"zeta_low_rad": zeta_low_rad},
        )

    provenance: dict[str, Any] = {
        "segment_kind": "grazing",
        "r_tangent_m": r_tangent_m,
        "tangent_altitude_m": r_tangent_m - R_EARTH_M,
        "h_low_m": h_low_m,
        "h_high_m": h_high_m,
        "zeta_low_rad": zeta_low_rad,
        "h_atm_top_m": h_atm_top_m,
        "model": "simple",
        "visibility_km": atmosphere.visibility_km,
        "aerosol_type": atmosphere.aerosol_type,
        "precipitable_water_cm": atmosphere.precipitable_water_cm,
        "standard_atmosphere": atmosphere.standard_atmosphere,
    }

    if h_low_m >= h_atm_top_m or h_high_m <= h_low_m:
        zeros = np.zeros_like(lam)
        provenance["vacuum_reason"] = (
            "arc at or above h_atm_top" if h_low_m >= h_atm_top_m else "zero-length arc"
        )
        return SegmentQuantities(
            wavelength_um=lam,
            tau=np.ones_like(lam),
            L_toward_upper=zeros,
            L_toward_lower=zeros.copy(),
            provenance=provenance,
        )

    od, columns = grazing_segment_optical_depth(atmosphere, lam, r_tangent_m, h_low_m, h_high_m)
    tau = np.exp(-od)
    provenance.update(columns)

    t_eff_K = atmosphere._downwelling_effective_temperature_K(h_low_m)
    provenance["t_eff_K"] = t_eff_K
    thermal = segment_thermal_emission(lam, tau, t_eff_K)

    scat_up, scat_dn, scatter_prov = _grazing_single_scatter_terms(
        atmosphere,
        lam,
        tau,
        columns,
        h_low_m=h_low_m,
        h_high_m=h_high_m,
        zeta_low_rad=zeta_low_rad,
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


def _grazing_single_scatter_terms(
    atmosphere: SimpleAtmosphere,
    lam: np.ndarray,
    tau: np.ndarray,
    columns: dict[str, float],
    *,
    h_low_m: float,
    h_high_m: float,
    zeta_low_rad: float,
    theta_s_rad: float | None,
    delta_phi_rad: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Directional scattered-solar radiances for the arc, plus provenance.

    Species weights are taken at the arc's **lower** end rather than at its
    mean altitude: a grazing arc is dominated by the densest air it passes
    through, which sits at the near end, and the single-scatter source
    ``(1 − τ)`` is generated there too.  (``segment_simple`` uses the mean
    altitude because a non-grazing column is spread far more evenly.)
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

    s_mol = columns["slant_column_mol_km"]
    s_h2o = columns["slant_column_h2o_km"]
    sigma_mol = atmosphere._rayleigh_extinction_km(lam, h_low_m)
    sigma_aer = atmosphere._aerosol_extinction_km(lam, h_low_m)
    sigma_h2o = (atmosphere._h2o_vertical_od(lam, s_h2o) / max(s_h2o, 1e-12)) * math.exp(
        -h_low_m / H_H2O_M
    )
    sigma_gas = (atmosphere._gas_floor_vertical_od(lam, s_mol) / max(s_mol, 1e-12)) * math.exp(
        -h_low_m / H_MOL_M
    )
    prov["weight_altitude_m"] = h_low_m
    prov["arc_top_altitude_m"] = h_high_m

    omega0 = atmosphere._single_scattering_albedo(sigma_mol, sigma_aer, sigma_h2o, sigma_gas)
    cos_up = cos_scattering_angle(zeta_low_rad, theta_s_rad, delta_phi_rad, "toward_upper")
    cos_dn = cos_scattering_angle(zeta_low_rad, theta_s_rad, delta_phi_rad, "toward_lower")
    prov["cos_scatter_toward_upper"] = cos_up
    prov["cos_scatter_toward_lower"] = cos_dn

    phase_up = atmosphere._single_scatter_phase_function(cos_up, sigma_mol, sigma_aer)
    phase_dn = atmosphere._single_scatter_phase_function(cos_dn, sigma_mol, sigma_aer)
    scat_up = segment_single_scatter_radiance(lam, tau, omega0, phase_up, cos_theta_sun)
    scat_dn = segment_single_scatter_radiance(lam, tau, omega0, phase_dn, cos_theta_sun)
    return scat_up, scat_dn, prov
