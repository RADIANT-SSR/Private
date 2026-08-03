"""Constant-altitude (horizontal) path arm — analytic Beer-Lambert at local density.

One computation, one module (Rule 19): evaluate a
:class:`~radiant.atmosphere.segments.LevelArmSpec` into a
:class:`~radiant.atmosphere.segments.SegmentQuantities`.

Why this is not a column segment
--------------------------------
A level path is an **interior-tangent** topology (plan §8.3 addendum): its
lowest point is in the middle, not at an endpoint.  Its local zenith is π/2
everywhere, which is past ``ZENITH_CEILING_RAD`` where the
plane-parallel-with-spherical-correction air mass stops meaning anything —
and, worse, the column integral it multiplies is ``∫ exp(−h/H) dh`` between
two altitudes, which is exactly zero for a level path.  The column machinery
therefore cannot express this path at all; it needs the *true chord length*
against a *local* extinction coefficient.  Hence a separate spec type and a
separate module.

Model
-----
::

    τ(λ) = exp[ −α(λ, h) · L ]                       (Beer-Lambert, exact)
    L_path(λ) = (1 − τ(λ)) · B(λ, T_eff)             (thermal, Kirchhoff)
              + single-scatter solar source          (lit scenes)

with ``α(λ, h)`` the **local** extinction coefficient at the arm altitude
[1/km] and ``L`` the geometric arm length [km].

``α`` is derived from the same calibrated machinery the column model uses —
no new fit, no new constant.  Rayleigh and aerosol have closed-form local
values already (``_rayleigh_extinction_km`` / ``_aerosol_extinction_km``
evaluated *at* the arm altitude).  Water vapour and the well-mixed-gas floor
do not: CU-161 calibrates them as **column** optical depths, and the water
term is a curve of growth ``OD = k · w_eff^b`` that is not the integral of any
local coefficient.  They are linearised exactly the way ``simple.py`` already
linearises them for its single-scattering-albedo weights::

    α_x(λ, h) = [ OD_x(h → h_atm_top) / col_length_x(h → h_atm_top) ]
                · exp(−h / H_x)

i.e. the species' column-mean sea-level extinction over the column *above the
arm*, brought down to the arm's local density.  The reference column is the
one column that exists independently of the arm's own length, which is what
makes ``α`` a property of the altitude alone — and therefore makes ``τ`` a
pure exponential in ``L``.

``τ(2L) = τ(L)²`` exactly
-------------------------
That identity is a *property* of this analytic arm, not an accident, and it
is precisely where a MODTRAN band model disagrees: correlated-k / band-model
transmittance saturates sub-exponentially, because the strong lines in a band
go opaque first and the remaining flux leaks through the window between them.
Measured against the real MODTRAN horizontal 5×5 grid (rows L1–L25,
midlat_summer, rural, 23 km visibility), band-mean transmittance
model/MODTRAN at 8–12 µm runs 1.03, 1.01, 0.95, 0.87, 0.82 across the
5/10/25/50/100 km ranges at 3 km altitude — good — while at 3–5 µm the same
sweep runs 1.09, 0.88, 0.43, 0.11, 0.01: the exponential arm collapses while
MODTRAN's band model keeps leaking.  The identity holds in the model; the
L-grid anchors quantify what it costs.  Use a MODTRAN or interpolated backend
for quantitative long-range MWIR horizontal work.

Constant-density assumption
---------------------------
The arm is treated as a straight chord of uniform density at ``altitude_m``.
On a spherical Earth the chord dips below its endpoints by the tangent-height
depression ``Δh ≈ L² / 8 R_E`` (mean sag over the chord ``≈ (2/3) Δh``), so
the real path samples slightly *denser* air than the model assumes and the
model under-states optical depth.  The Phase-1 horizon guard
(:mod:`radiant.core.viewing_triangle`) bounds ``Δh`` for an admissible path:
clean below 100 m, warning band to 2 km, raise above.  At the ``Δh = 2 km``
raise threshold the mean sag is ≈ 1.3 km, which on the 2 km water scale
height is a density ratio of ``exp(1.33/2) ≈ 1.9`` — the arm would understate
water optical depth roughly two-fold, which is why that threshold raises
rather than warns.  At the top of the clean band (``Δh = 100 m``, ``L ≈
71 km``) the mean sag is 67 m and the water-density error is 3.4 %; at the
100 km range of the MODTRAN L-grid (``Δh = 196 m``) it is 6.8 %.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from radiant.atmosphere.segment_simple import DEFAULT_H_ATM_TOP_M
from radiant.atmosphere.segment_single_scatter import (
    COS_HORIZON_TOLERANCE,
    cos_scattering_angle,
    segment_single_scatter_radiance,
)
from radiant.atmosphere.segment_thermal import directional_segment_thermal
from radiant.atmosphere.segments import (
    LevelArmSpec,
    SegmentQuantities,
    validate_wavelength_grid,
)
from radiant.atmosphere.simple import H_H2O_M, H_MOL_M, SimpleAtmosphere
from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError

__all__ = ["LEVEL_ARM_ZENITH_RAD", "evaluate_level_arm", "local_extinction_per_km"]

# The local zenith along a constant-altitude arm, everywhere, by definition.
# Used for the single-scatter phase angle.  It is deliberately *past*
# ``ZENITH_CEILING_RAD``: the arm carries no air mass, so the ceiling — which
# bounds the column air-mass approximation — does not apply to it.
LEVEL_ARM_ZENITH_RAD: float = math.pi / 2.0


def local_extinction_per_km(
    atmosphere: SimpleAtmosphere,
    wavelength_um: np.ndarray,
    altitude_m: float,
    *,
    h_atm_top_m: float = DEFAULT_H_ATM_TOP_M,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Local extinction coefficient at ``altitude_m`` [1/km].

    Returns ``(alpha_total, per_species)`` where ``per_species`` carries the
    four components (``mol``, ``aer``, ``h2o``, ``gas``) — the same split the
    single-scattering albedo and phase function need.

    See the module docstring for the linearisation of the CU-161 water and
    well-mixed-gas terms.
    """
    lam = np.asarray(wavelength_um, dtype=np.float64)
    h = float(altitude_m)

    # Reference column above the arm — the arm-length-independent reference
    # that makes α a property of altitude alone.
    col_mol_ref = atmosphere._column_length_km(h, h_atm_top_m, H_MOL_M)
    col_h2o_ref = atmosphere._column_length_km(h, h_atm_top_m, H_H2O_M)

    alpha_mol = atmosphere._rayleigh_extinction_km(lam, h)
    alpha_aer = atmosphere._aerosol_extinction_km(lam, h)
    alpha_h2o = (
        atmosphere._h2o_vertical_od(lam, col_h2o_ref) / max(col_h2o_ref, 1e-12)
    ) * math.exp(-h / H_H2O_M)
    alpha_gas = (
        atmosphere._gas_floor_vertical_od(lam, col_mol_ref) / max(col_mol_ref, 1e-12)
    ) * math.exp(-h / H_MOL_M)

    per_species = {
        "mol": np.asarray(alpha_mol, dtype=np.float64),
        "aer": np.asarray(alpha_aer, dtype=np.float64),
        "h2o": np.asarray(alpha_h2o, dtype=np.float64),
        "gas": np.asarray(alpha_gas, dtype=np.float64),
    }
    total = alpha_mol + alpha_aer + alpha_h2o + alpha_gas
    return np.asarray(total, dtype=np.float64), per_species


def evaluate_level_arm(
    atmosphere: SimpleAtmosphere,
    wavelength_um: np.ndarray,
    spec: LevelArmSpec,
    *,
    theta_s_rad: float | None = None,
    delta_phi_rad: float = 0.0,
    h_atm_top_m: float = DEFAULT_H_ATM_TOP_M,
) -> SegmentQuantities:
    """Evaluate one constant-altitude arm into its directional products.

    Parameters
    ----------
    atmosphere:
        The configured :class:`~radiant.atmosphere.simple.SimpleAtmosphere`.
    wavelength_um:
        1-D strictly-ascending, strictly-positive chain wavelength grid [µm].
    spec:
        The validated level arm.
    theta_s_rad:
        Solar zenith at the arm altitude [rad], or ``None`` for a pure-thermal
        evaluation.
    delta_phi_rad:
        Relative azimuth ``φ_s − φ_o`` [rad] between the sun and the arm's
        travel direction.  Only its cosine is used.
    h_atm_top_m:
        Top of the modelled column [m]; an arm at or above it is exact vacuum,
        and it is also the reference column for the α linearisation.

    Returns
    -------
    SegmentQuantities
        ``tau`` plus the two directional radiance products [W/m²/sr/µm].  The
        **thermal** parts of the two are identical — an arm has one
        temperature and one τ, so its emission is exactly symmetric.  The
        scattered-solar parts are not: the two travel directions are
        anti-parallel, so their scattering angles are supplementary
        (forward scatter one way is back scatter the other).  With no sun
        supplied, or with the sun perpendicular to the arm
        (``cos Δφ = 0``), the two fields are equal element-for-element.
    """
    lam = validate_wavelength_grid(wavelength_um, "evaluate_level_arm")
    if not math.isfinite(h_atm_top_m) or h_atm_top_m <= 0.0:
        raise ParameterBoundsError(
            what=f"evaluate_level_arm: h_atm_top_m = {h_atm_top_m} m is not positive-finite",
            why="The top of the modelled column is a positive altitude.",
            action=f"Pass a positive h_atm_top_m (default {DEFAULT_H_ATM_TOP_M:g} m).",
            context={"h_atm_top_m": h_atm_top_m},
        )

    provenance: dict[str, Any] = {
        "segment_kind": "level_arm",
        "altitude_m": spec.altitude_m,
        "length_m": spec.length_m,
        "h_atm_top_m": h_atm_top_m,
        "model": "simple",
        "visibility_km": atmosphere.visibility_km,
        "aerosol_type": atmosphere.aerosol_type,
        "precipitable_water_cm": atmosphere.precipitable_water_cm,
        "standard_atmosphere": atmosphere.standard_atmosphere,
        "tangent_depression_m": spec.length_m**2 / (8.0 * R_EARTH_M),
    }

    if spec.altitude_m >= h_atm_top_m:
        zeros = np.zeros_like(lam)
        provenance["vacuum_reason"] = "arm at or above h_atm_top"
        return SegmentQuantities(
            wavelength_um=lam,
            tau=np.ones_like(lam),
            L_toward_upper=zeros,
            L_toward_lower=zeros.copy(),
            provenance=provenance,
        )

    alpha_total, per_species = local_extinction_per_km(
        atmosphere, lam, spec.altitude_m, h_atm_top_m=h_atm_top_m
    )
    length_km = spec.length_m / 1000.0
    tau = np.exp(-alpha_total * length_km)
    provenance["length_km"] = length_km

    # A level arm is isothermal, so the CU-321 height-resolved model collapses
    # to the exact single temperature T(h_arm) — the same value in both
    # directions, and no quadrature is run (``h_low == h_high``).  What changes
    # against the pre-CU-321 code is only that the CU-155 `z_em` offset, fit
    # for the hemispheric sky flux, no longer leaks into a directional product.
    thermal_toward_upper, thermal_toward_lower = directional_segment_thermal(
        atmosphere,
        lam,
        tau,
        h_low_m=spec.altitude_m,
        h_high_m=spec.altitude_m,
        species_od={key: value * length_km for key, value in per_species.items()},
        provenance=provenance,
    )

    scat_up, scat_dn, scatter_prov = _arm_single_scatter_terms(
        atmosphere,
        lam,
        tau,
        per_species,
        theta_s_rad=theta_s_rad,
        delta_phi_rad=delta_phi_rad,
    )
    provenance.update(scatter_prov)

    return SegmentQuantities(
        wavelength_um=lam,
        tau=tau,
        L_toward_upper=thermal_toward_upper + scat_up,
        L_toward_lower=thermal_toward_lower + scat_dn,
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _arm_single_scatter_terms(
    atmosphere: SimpleAtmosphere,
    lam: np.ndarray,
    tau: np.ndarray,
    per_species: dict[str, np.ndarray],
    *,
    theta_s_rad: float | None,
    delta_phi_rad: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Directional scattered-solar radiances for the arm, plus provenance."""
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

    # The arm's local extinctions ARE the species weights — no mean-altitude
    # approximation is needed, because the arm has a single altitude.
    omega0 = atmosphere._single_scattering_albedo(
        per_species["mol"], per_species["aer"], per_species["h2o"], per_species["gas"]
    )
    cos_up = cos_scattering_angle(LEVEL_ARM_ZENITH_RAD, theta_s_rad, delta_phi_rad, "toward_upper")
    cos_dn = cos_scattering_angle(LEVEL_ARM_ZENITH_RAD, theta_s_rad, delta_phi_rad, "toward_lower")
    prov["cos_scatter_toward_upper"] = cos_up
    prov["cos_scatter_toward_lower"] = cos_dn

    phase_up = atmosphere._single_scatter_phase_function(
        cos_up, per_species["mol"], per_species["aer"]
    )
    phase_dn = atmosphere._single_scatter_phase_function(
        cos_dn, per_species["mol"], per_species["aer"]
    )
    scat_up = segment_single_scatter_radiance(lam, tau, omega0, phase_up, cos_theta_sun)
    scat_dn = segment_single_scatter_radiance(lam, tau, omega0, phase_dn, cos_theta_sun)
    return scat_up, scat_dn, prov
