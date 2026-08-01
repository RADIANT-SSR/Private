"""Column path-segment evaluation with the ``SimpleAtmosphere`` machinery.

One computation, one module (Rule 19): evaluate a
:class:`~radiant.atmosphere.segments.ColumnSegmentSpec` — a slant column
between two altitudes, keyed to the lower endpoint's zenith — into a
:class:`~radiant.atmosphere.segments.SegmentQuantities`.

Everything numerical here is **reused** from
:class:`radiant.atmosphere.simple.SimpleAtmosphere`; this module adds no
calibration, no fitted constant and no new spectral model.  Specifically it
calls the CU-161-calibrated pieces directly:

``_column_length_km``
    Analytic ``∫ exp(−h/H) dh`` between the two altitudes for each species'
    scale height — the endpoint-symmetric column integral.
``_rayleigh_extinction_km`` / ``_aerosol_extinction_km``
    Sea-level extinction coefficients [1/km].
``_h2o_vertical_od`` / ``_gas_floor_vertical_od``
    The CU-161 curve-of-growth water term and the well-mixed-gas floor.
``_single_scattering_albedo`` / ``_single_scatter_phase_function``
    The ω₀ and P(Θ) weights for the single-scatter source.
``_downwelling_effective_temperature_K``
    The CU-155 emission-height temperature, evaluated at the segment's
    **lower** endpoint.

Because the optical depth is built from exactly those functions with exactly
the same endpoints and the same
:meth:`~radiant.atmosphere.protocol.AtmosphericGeometry.air_mass`, a segment
that spans the same column as an existing down-looking ``evaluate`` call
reproduces its ``tau_up`` **bit for bit** — that identity is a Level-0 test.

Zero drift
----------
Nothing in ``simple.py`` is modified and nothing here is called from an
existing evaluate path.  The products are additive and reachable only from
the newly-legal up-looking / level topologies.

Direction conventions
---------------------
``tau`` is single-valued: transmittance is reciprocal
(``RADIANT_Atmosphere.md`` §4.4).  ``L_toward_upper`` and ``L_toward_lower``
are separate products; see
:mod:`radiant.atmosphere.segment_single_scatter` for the scattering-angle
flip and :mod:`radiant.atmosphere.segment_thermal` for the shared graybody
temperature and the size of the directional thermal approximation.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from radiant.atmosphere.near_horizon_air_mass import (
    apply_species_air_mass,
    is_near_horizon,
    near_horizon_species_air_mass,
    tangent_radius_m,
)
from radiant.atmosphere.protocol import H_ATM_TOP_M, AtmosphericGeometry
from radiant.atmosphere.segment_single_scatter import (
    COS_HORIZON_TOLERANCE,
    cos_scattering_angle,
    segment_single_scatter_radiance,
)
from radiant.atmosphere.segment_thermal import segment_thermal_emission
from radiant.atmosphere.segments import (
    ColumnSegmentSpec,
    SegmentQuantities,
    validate_wavelength_grid,
)
from radiant.atmosphere.simple import (
    H_AER_M,
    H_H2O_M,
    H_MOL_M,
    SimpleAtmosphere,
)
from radiant.core.parameters import ParameterBoundsError

__all__ = ["DEFAULT_H_ATM_TOP_M", "column_segment_optical_depth", "evaluate_column_segment"]

# Default top of the modelled atmospheric column [m] — the same Kármán-line
# value ``LineOfSightGeometry.h_atm_top`` defaults to.  It is used here only
# as the **vacuum discriminator**: a segment whose lower endpoint is at or
# above it contains no modelled air, so τ = 1 and L = 0 exactly.  The
# exponential density profiles themselves have no hard top, and the optical
# depth of a segment that straddles h_atm_top is NOT truncated — that keeps
# the bit-for-bit identity with the existing ``evaluate`` column integrals,
# which also run the exponential tail out to the sensor altitude.
#: Re-export of the single framework-wide column top (defined in ``protocol`` — the
#: lowest layer — so CU-255's absorbing-thickness clamp and this module agree).
DEFAULT_H_ATM_TOP_M: float = H_ATM_TOP_M


def column_segment_optical_depth(
    atmosphere: SimpleAtmosphere,
    wavelength_um: np.ndarray,
    spec: ColumnSegmentSpec,
) -> tuple[np.ndarray, float, dict[str, float]]:
    """Slant optical depth of a column segment [dimensionless].

    Returns ``(od_slant, air_mass, provenance)`` where ``od_slant`` is the
    wavelength-resolved slant optical depth, ``air_mass`` the dimensionless
    factor actually applied to the molecular column, and ``provenance`` the
    per-species density-weighted column lengths [km] plus, past the
    near-horizon hand-over, the spherical slant columns and per-species air
    masses that replaced the single plane-parallel factor.

    The vertical optical depth is the sum of the four CU-161 species terms
    evaluated over ``[h_low, h_high]``.  How it becomes a *slant* depth
    depends on the lower-endpoint zenith:

    * **at or below** :data:`~radiant.atmosphere.protocol.SPHERICAL_SWITCH_RAD`
      (80°) — one plane-parallel-with-spherical-correction air mass from
      :meth:`~radiant.atmosphere.protocol.AtmosphericGeometry.air_mass`,
      multiplying the summed vertical depth.  Unchanged, bit for bit;
    * **past 80°** — a per-species effective air mass from the exact spherical
      slant integral (:mod:`radiant.atmosphere.near_horizon_air_mass`), because
      ``sec ζ`` over-states the near-horizon column by 3.8 % at 80° rising to
      237 % at 89.4°, and over-states it *differently* per species (2.3× apart
      between water vapour and molecular air at 89.4°).  This is the same
      hand-over the up-looking sky has taken since CU-225 / CU-274, now given
      to the down-looking and solar columns as well (CU-224 / ex-CU-275).

    For a zero-thickness segment every column length is exactly zero and the
    optical depth is exactly zero.
    """
    lam = np.asarray(wavelength_um, dtype=np.float64)
    h_low = spec.h_low_m
    h_high = spec.h_high_m

    col_mol = atmosphere._column_length_km(h_low, h_high, H_MOL_M)
    col_aer = atmosphere._column_length_km(h_low, h_high, H_AER_M)
    col_h2o = atmosphere._column_length_km(h_low, h_high, H_H2O_M)

    od_vert_mol = atmosphere._rayleigh_extinction_km(lam, 0.0) * col_mol
    od_vert_aer = atmosphere._aerosol_extinction_km(lam, 0.0) * col_aer
    od_vert_h2o = atmosphere._h2o_vertical_od(lam, col_h2o)
    od_vert_gas = atmosphere._gas_floor_vertical_od(lam, col_mol)

    provenance = {
        "col_length_mol_km": col_mol,
        "col_length_aer_km": col_aer,
        "col_length_h2o_km": col_h2o,
    }

    if is_near_horizon(spec.zeta_low_rad):
        masses = near_horizon_species_air_mass(
            tangent_radius_m(h_low, spec.zeta_low_rad),
            h_low,
            h_high,
            col_mol_km=col_mol,
            col_aer_km=col_aer,
            col_h2o_km=col_h2o,
            scale_height_mol_m=H_MOL_M,
            scale_height_aer_m=H_AER_M,
            scale_height_h2o_m=H_H2O_M,
        )
        od_slant = apply_species_air_mass(
            masses,
            od_vert_mol=od_vert_mol,
            od_vert_aer=od_vert_aer,
            od_vert_h2o=od_vert_h2o,
            od_vert_gas=od_vert_gas,
        )
        provenance.update(masses.as_provenance())
        return od_slant, masses.m_mol, provenance

    od_vert = od_vert_mol + od_vert_aer + od_vert_h2o + od_vert_gas

    # Air mass at the LOWER endpoint (ADR-0011 decision 3).  The existing
    # AtmosphericGeometry places the lower endpoint in ``target_altitude_m``
    # and the upper in ``sensor_altitude_m`` and keys the zenith to the
    # former — exactly the segment convention.  Δh = 0 returns 1.0.
    air_mass = AtmosphericGeometry(
        sensor_altitude_m=h_high,
        target_altitude_m=h_low,
        path_zenith_rad=spec.zeta_low_rad,
    ).air_mass()

    return np.asarray(od_vert * air_mass, dtype=np.float64), air_mass, provenance


def evaluate_column_segment(
    atmosphere: SimpleAtmosphere,
    wavelength_um: np.ndarray,
    spec: ColumnSegmentSpec,
    *,
    theta_s_rad: float | None = None,
    delta_phi_rad: float = 0.0,
    h_atm_top_m: float = DEFAULT_H_ATM_TOP_M,
) -> SegmentQuantities:
    """Evaluate one slant column segment into its directional products.

    Parameters
    ----------
    atmosphere:
        The configured :class:`~radiant.atmosphere.simple.SimpleAtmosphere`.
    wavelength_um:
        1-D strictly-ascending, strictly-positive chain wavelength grid [µm].
    spec:
        The validated column segment.
    theta_s_rad:
        Solar zenith at the segment's lower endpoint [rad], or ``None`` for a
        pure-thermal evaluation (no scattered-solar term at all).
    delta_phi_rad:
        Relative azimuth ``φ_s − φ_o`` [rad].  Only its cosine is used.
    h_atm_top_m:
        Top of the modelled column [m].  Used only to decide that a segment
        wholly at or above it is vacuum.

    Returns
    -------
    SegmentQuantities
        ``tau`` (reciprocal, one per segment) plus the two directional
        radiance products [W/m²/sr/µm].

    Raises
    ------
    ParameterBoundsError
        On an invalid wavelength grid or a non-positive ``h_atm_top_m``.
        Segment-geometry validation happens in ``ColumnSegmentSpec``.
    """
    lam = validate_wavelength_grid(wavelength_um, "evaluate_column_segment")
    if not math.isfinite(h_atm_top_m) or h_atm_top_m <= 0.0:
        raise ParameterBoundsError(
            what=f"evaluate_column_segment: h_atm_top_m = {h_atm_top_m} m is not positive-finite",
            why="The top of the modelled column is a positive altitude.",
            action=f"Pass a positive h_atm_top_m (default {DEFAULT_H_ATM_TOP_M:g} m).",
            context={"h_atm_top_m": h_atm_top_m},
        )

    provenance: dict[str, Any] = {
        "segment_kind": "column",
        "h_low_m": spec.h_low_m,
        "h_high_m": spec.h_high_m,
        "zeta_low_rad": spec.zeta_low_rad,
        "h_atm_top_m": h_atm_top_m,
        "model": "simple",
        "visibility_km": atmosphere.visibility_km,
        "aerosol_type": atmosphere.aerosol_type,
        "precipitable_water_cm": atmosphere.precipitable_water_cm,
        "standard_atmosphere": atmosphere.standard_atmosphere,
    }

    # --- Vacuum: the whole segment sits at or above the modelled column ---
    if spec.h_low_m >= h_atm_top_m:
        zeros = np.zeros_like(lam)
        provenance["vacuum_reason"] = "segment at or above h_atm_top"
        return SegmentQuantities(
            wavelength_um=lam,
            tau=np.ones_like(lam),
            L_toward_upper=zeros,
            L_toward_lower=zeros.copy(),
            provenance=provenance,
        )

    od_slant, air_mass, od_provenance = column_segment_optical_depth(atmosphere, lam, spec)
    tau = np.exp(-od_slant)
    provenance["air_mass"] = air_mass
    provenance["air_mass_form"] = (
        "spherical per-species (near-horizon hand-over)"
        if is_near_horizon(spec.zeta_low_rad)
        else "plane-parallel with spherical correction"
    )
    provenance.update(od_provenance)

    # --- Thermal: Kirchhoff emissivity on the segment's own τ (Rule 5) ---
    t_eff_K = atmosphere._downwelling_effective_temperature_K(spec.h_low_m)
    provenance["t_eff_K"] = t_eff_K
    thermal = segment_thermal_emission(lam, tau, t_eff_K)

    # --- Single-scatter solar, resolved per travel direction ---
    scat_up, scat_dn, scatter_prov = _single_scatter_terms(
        atmosphere,
        lam,
        spec,
        tau,
        od_provenance,
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


def _single_scatter_terms(
    atmosphere: SimpleAtmosphere,
    lam: np.ndarray,
    spec: ColumnSegmentSpec,
    tau: np.ndarray,
    lengths: dict[str, float],
    *,
    theta_s_rad: float | None,
    delta_phi_rad: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Directional scattered-solar radiances and their provenance.

    Species weights are taken at the segment's **lower** endpoint (CU-260,
    adopted 2026-08-01 against the shipped ``midlat_summer_uplooking_ladder``
    MODTRAN family).  The retired alternative weighted at the arithmetic-mean
    altitude, which for any column taller than ~40 km put the weights above the
    altitude where the aerosol and water coefficients underflow: ω₀ went to
    exactly 1 and the Henyey-Greenstein forward peak collapsed to the isotropic
    Rayleigh 1.5, so a tall column scattered as if the atmosphere held no
    aerosol at all whatever ``visibility_km`` said.  Measured against all five
    non-degenerate ladder rungs (band-mean ``MODTRAN / model``, worst rung):
    VIS 3.09× → 1.36×, NIR 3.02× → 1.26×, SWIR 8.71× → 1.67×, MWIR 2.40× →
    2.33×, LWIR unchanged to 4e-4 (thermal-dominated control).  The anchors are
    frozen in ``tests/integration/test_species_split_anchors.py``.
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

    # Lower-endpoint species weights (CU-260, adopted 2026-08-01).  Absolute ODs
    # come from the column integral; the *relative* species split is taken at the
    # segment's lower endpoint, which is both the densest air in the column and
    # the end the ``L_toward_lower`` product emerges from — the same choice
    # ``segment_grazing`` and ``level_arm`` already make, so all three evaluators
    # now weight alike and the 80° hand-over carries no species-split step.
    weight_alt_m = spec.h_low_m
    col_mol = lengths["col_length_mol_km"]
    col_h2o = lengths["col_length_h2o_km"]
    sigma_mol = atmosphere._rayleigh_extinction_km(lam, weight_alt_m)
    sigma_aer = atmosphere._aerosol_extinction_km(lam, weight_alt_m)
    sigma_h2o = (atmosphere._h2o_vertical_od(lam, col_h2o) / max(col_h2o, 1e-12)) * math.exp(
        -weight_alt_m / H_H2O_M
    )
    sigma_gas = (atmosphere._gas_floor_vertical_od(lam, col_mol) / max(col_mol, 1e-12)) * math.exp(
        -weight_alt_m / H_MOL_M
    )

    omega0 = atmosphere._single_scattering_albedo(sigma_mol, sigma_aer, sigma_h2o, sigma_gas)

    cos_up = cos_scattering_angle(spec.zeta_low_rad, theta_s_rad, delta_phi_rad, "toward_upper")
    cos_dn = cos_scattering_angle(spec.zeta_low_rad, theta_s_rad, delta_phi_rad, "toward_lower")
    prov["cos_scatter_toward_upper"] = cos_up
    prov["cos_scatter_toward_lower"] = cos_dn
    prov["weight_altitude_m"] = weight_alt_m

    phase_up = atmosphere._single_scatter_phase_function(cos_up, sigma_mol, sigma_aer)
    phase_dn = atmosphere._single_scatter_phase_function(cos_dn, sigma_mol, sigma_aer)

    scat_up = segment_single_scatter_radiance(lam, tau, omega0, phase_up, cos_theta_sun)
    scat_dn = segment_single_scatter_radiance(lam, tau, omega0, phase_dn, cos_theta_sun)
    return scat_up, scat_dn, prov
