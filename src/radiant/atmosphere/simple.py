"""Simple parametric atmosphere — closed-form Beer-Lambert.

Implements the ``SimpleAtmosphere`` model from
``docs/RADIANT_Atmosphere.md`` §3.1::

    τ_atm(λ) = exp[ −σ_total(λ) · L_slant ]

with three contributions:

- **Molecular (Rayleigh)** — Bucholtz 1995 sea-level coefficient
  ``σ_mol(λ) = 0.0088 · λ_µm⁻⁴·⁰⁹ km⁻¹``, scaled to a path-mean
  altitude with an exponential atmosphere of scale height ``H_mol = 8 km``.
- **Aerosol (Mie)** — Koschmieder visibility relation
  ``σ_aer(550 nm) = 3.912 / V_km`` with three canonical Ångström
  exponents (rural ``α=1.3``, urban ``α=1.5``, maritime ``α=0.7``).
  Aerosol scale height ``H_aer = 1.2 km``.
- **Water vapor** — five-band Lorentzian-like absorption fit centered
  at 1.4, 1.9, 2.7, 3.2, and 6.3 µm, parameterised by precipitable
  water ``w_pw [cm]``. Calibrated against MODTRAN US Standard at the
  band centres; *not* claimed accurate elsewhere.

This cut implements the full §3.1 simple-model triple:

- **``τ_atm(λ)``** via Beer-Lambert on the three extinction species.
- **``L_path(λ)``** via the single-scatter approximation, using a
  5778 K blackbody TOA solar spectrum from ``radiant.core.solar`` and
  a weighted two-component phase function (Rayleigh for molecular,
  Henyey-Greenstein with ``g = 0.7`` for aerosol).
- **``L_atm_down(λ)``** via the graybody ``(1 − τ) · B(λ, T_atm_eff)``
  with ``T_atm_eff`` from a closed-form standard-atmosphere
  temperature lookup evaluated at ``0.5 × sensor_altitude``
  (plane-parallel troposphere with a fixed 6.5 K/km lapse, floored
  at the ICAO tropopause temperature 216.65 K).

Assumptions
-----------
- Plane-parallel atmosphere; spherical-Earth correction applied past
  80° zenith via :class:`AtmosphericGeometry`.
- Aerosol and molecular scale heights are evaluated at the path-mean
  altitude (i.e. one mean column extinction × slant path), not
  integrated layer-by-layer. This is the textbook closed-form
  approximation appropriate for the simple model's accuracy class.
- Wavelength dependence is monotone in each species. The water-vapor
  fit is bumpy by construction at the band centres but is smooth in
  the windows.
- Single thermodynamic equilibrium temperature (no pressure broadening
  variation along the path).

These assumptions fail in the upper stratosphere, in heavy cirrus, and
for narrow-band line absorption. Users with those needs run MODTRAN.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from radiant.atmosphere.protocol import (
    AtmosphericGeometry,
    AtmosphericState,
)
from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.solar import toa_solar_equivalent_radiance
from radiant.core.spectral import SpectralData

# ---------------------------------------------------------------------------
# Model constants
# ---------------------------------------------------------------------------

# Bucholtz 1995 sea-level Rayleigh extinction coefficient at λ = 1 µm.
# σ_mol(λ) = RAYLEIGH_COEFF_KM * λ_µm**(-RAYLEIGH_EXPONENT)  [1/km]
RAYLEIGH_COEFF_KM: float = 0.0088
RAYLEIGH_EXPONENT: float = 4.09

# Exponential-atmosphere scale heights [m].
H_MOL_M: float = 8_000.0
H_AER_M: float = 1_200.0

# Koschmieder visibility constant: σ_aer(550 nm) = KOSCHMIEDER / V_km  [1/km]
# 3.912 = -ln(0.02), the contrast threshold defining "meteorological
# visibility." Per RADIANT_Atmosphere.md §3.1.
KOSCHMIEDER: float = 3.912
AEROSOL_REFERENCE_WAVELENGTH_UM: float = 0.550

# Ångström exponents and single-scattering albedos per aerosol type,
# from RADIANT_Atmosphere.md §3.1. The SSA values drive the per-species
# weight of the aerosol phase function in the single-scatter ``L_path``.
_AEROSOL_TABLE: dict[str, dict[str, float]] = {
    "rural": {"angstrom": 1.3, "ssa": 0.95},
    "urban": {"angstrom": 1.5, "ssa": 0.85},
    "maritime": {"angstrom": 0.7, "ssa": 0.99},
}

# Henyey-Greenstein asymmetry parameter for the aerosol phase function.
# ``g ≈ 0.7`` is the canonical value for continental boundary-layer
# aerosol (forward-scattering). RADIANT_Atmosphere.md §3.1 flags this
# as a tunable simple-model default; later phases may expose it as a
# parameter per aerosol type.
HG_ASYMMETRY: float = 0.7


# Five-band water-vapor absorption fit. Each entry: centre wavelength
# (µm), peak extinction coefficient per cm precipitable water [1/km/cm],
# and the half-width-at-half-max (HWHM, µm) of a Lorentzian-shaped band.
# The values are tuned to give monotone OD scaling with w_pw and band
# depths consistent with US Standard MODTRAN runs at the band centres.
# Outside the bands the contribution falls off as 1/(1 + (Δλ/HWHM)²)
# and is dominated at long wavelengths by the continuum term below.
@dataclass(frozen=True)
class _H2OBand:
    centre_um: float
    extinction_km_per_cm: float  # [1/km per cm precipitable water]
    hwhm_um: float


_H2O_BANDS: tuple[_H2OBand, ...] = (
    _H2OBand(centre_um=1.4, extinction_km_per_cm=0.6, hwhm_um=0.06),
    _H2OBand(centre_um=1.9, extinction_km_per_cm=1.4, hwhm_um=0.10),
    _H2OBand(centre_um=2.7, extinction_km_per_cm=3.5, hwhm_um=0.15),
    _H2OBand(centre_um=3.2, extinction_km_per_cm=0.8, hwhm_um=0.10),
    _H2OBand(centre_um=6.3, extinction_km_per_cm=4.0, hwhm_um=0.40),
)

# Continuum water-vapor extinction at long wavelengths [1/km/(cm pwv)].
# Tiny but nonzero — represents the rotational line wing buildup that
# is the leading background term in MWIR/LWIR for the simple model.
H2O_CONTINUUM_KM: float = 0.002

# Sea-level air temperature [K] per standard-atmosphere profile.
# Values from U.S. Committee on Extension to the Standard Atmosphere
# (COESA) 1976 supplements for the five non-US profiles; us_standard
# is COESA 1976 itself. Used to build ``T_atm_eff`` for the graybody
# downwelling term.
_T_SEA_LEVEL_K: dict[str, float] = {
    "us_standard": 288.15,
    "tropical": 299.65,
    "midlat_summer": 294.15,
    "midlat_winter": 272.15,
    "subarctic_summer": 287.15,
    "subarctic_winter": 257.15,
}

# ICAO tropospheric lapse rate and tropopause clamp.
_LAPSE_RATE_K_PER_M: float = 6.5e-3  # 6.5 K / km
_TROPOPAUSE_T_K: float = 216.65  # ICAO isothermal tropopause temperature
_TROPOPAUSE_H_M: float = 11_000.0


# ---------------------------------------------------------------------------
# SimpleAtmosphere
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SimpleAtmosphere:
    """Closed-form Beer-Lambert atmosphere model.

    Parameters
    ----------
    visibility_km:
        Meteorological visibility at 550 nm [km]. Must be ``> 0``.
        Default ``23.0`` ("clear" per Koschmieder).
    aerosol_type:
        One of ``"rural"``, ``"urban"``, ``"maritime"``.
    precipitable_water_cm:
        Total column precipitable water [cm]. Must be ``≥ 0``.
        Default ``1.4`` (US Standard mid-latitude annual mean).
    standard_atmosphere:
        Atmosphere profile selector — currently informational only;
        defaults are tuned to ``us_standard``. Stored for provenance.
    name:
        Optional human-readable label.

    Notes
    -----
    The model is frozen and pure. ``build_state`` may be called any
    number of times with different geometries; nothing is cached on the
    instance.
    """

    visibility_km: float = 23.0
    aerosol_type: str = "rural"
    precipitable_water_cm: float = 1.4
    standard_atmosphere: str = "us_standard"
    name: str = "simple_atmosphere"
    _tag: str = field(default="simple", init=False, repr=False)

    def __post_init__(self) -> None:
        if not math.isfinite(self.visibility_km) or self.visibility_km <= 0.0:
            raise ValueError(
                f"SimpleAtmosphere '{self.name}': visibility_km = "
                f"{self.visibility_km} is invalid. Visibility is the "
                "meteorological range in km and must be a positive finite number."
            )
        if self.aerosol_type not in _AEROSOL_TABLE:
            raise ValueError(
                f"SimpleAtmosphere '{self.name}': aerosol_type = "
                f"'{self.aerosol_type}' is not recognised. Choose one of "
                f"{sorted(_AEROSOL_TABLE)}."
            )
        if not math.isfinite(self.precipitable_water_cm) or self.precipitable_water_cm < 0.0:
            raise ValueError(
                f"SimpleAtmosphere '{self.name}': precipitable_water_cm = "
                f"{self.precipitable_water_cm} is invalid. It is a non-negative "
                "column amount in cm of liquid-equivalent water vapour."
            )
        if self.standard_atmosphere not in _T_SEA_LEVEL_K:
            raise ValueError(
                f"SimpleAtmosphere '{self.name}': standard_atmosphere = "
                f"'{self.standard_atmosphere}' is not recognised. Choose one "
                f"of {sorted(_T_SEA_LEVEL_K)}."
            )

    # ------------------------------------------------------------------
    # Per-species extinction [1/km]
    # ------------------------------------------------------------------

    def _rayleigh_extinction_km(
        self, wavelength_um: np.ndarray, mean_altitude_m: float
    ) -> np.ndarray:
        """Molecular (Rayleigh) extinction at the path-mean altitude.

        ``σ_mol(λ, h) = 0.0088 · λ_µm^{−4.09} · exp(−h / 8 km)`` [1/km].
        """
        sea_level = RAYLEIGH_COEFF_KM * wavelength_um ** (-RAYLEIGH_EXPONENT)
        scale = math.exp(-mean_altitude_m / H_MOL_M)
        return np.asarray(sea_level * scale, dtype=np.float64)

    def _aerosol_extinction_km(
        self, wavelength_um: np.ndarray, mean_altitude_m: float
    ) -> np.ndarray:
        """Aerosol (Mie) extinction at the path-mean altitude.

        Koschmieder gives ``σ_aer(550 nm) = 3.912 / V_km``. The Ångström
        relation provides the wavelength scaling::

            σ_aer(λ) = σ_aer(λ_ref) · (λ / λ_ref)^{−α}

        and the aerosol vertical profile is exponential with scale
        height ``H_aer = 1.2 km``.
        """
        alpha = _AEROSOL_TABLE[self.aerosol_type]["angstrom"]
        sigma_550 = KOSCHMIEDER / self.visibility_km
        scaled = sigma_550 * (wavelength_um / AEROSOL_REFERENCE_WAVELENGTH_UM) ** (-alpha)
        height_factor = math.exp(-mean_altitude_m / H_AER_M)
        return np.asarray(scaled * height_factor, dtype=np.float64)

    def _single_scatter_phase_function(
        self,
        cos_theta_scatter: float,
        sigma_mol: np.ndarray,
        sigma_aer: np.ndarray,
    ) -> np.ndarray:
        """Extinction-weighted phase function ``P(Θ, λ)`` [dimensionless].

        Normalized so that an isotropic scatterer has ``P ≡ 1`` (i.e.,
        ``∫ P dΩ / 4π = 1``). Two components:

        - **Rayleigh (molecular)**: ``P_R(Θ) = 0.75 · (1 + cos²Θ)``.
        - **Aerosol**: Henyey-Greenstein with asymmetry ``g``,
          ``P_HG(Θ) = (1 − g²) / (1 + g² − 2 g cos Θ)^{3/2}``.

        The two are combined by *scattering* cross-section (not
        extinction), since a photon that is absorbed by water vapor
        does not contribute to scattered radiance at all::

            P_total(λ) = (σ_mol · P_R  +  ω_aer · σ_aer · P_HG)
                         / (σ_mol + ω_aer · σ_aer)

        Water vapor is treated as pure absorption and does not enter
        the numerator. The denominator is the wavelength-dependent
        total scattering coefficient; where it is zero (e.g. no
        molecular and no aerosol at some wavelength), the phase
        function is defined as 1 by convention and multiplied by a
        zero scattering albedo downstream so the contribution
        vanishes.
        """
        cos_t = cos_theta_scatter
        p_rayleigh = 0.75 * (1.0 + cos_t * cos_t)

        g = HG_ASYMMETRY
        denom_hg = (1.0 + g * g - 2.0 * g * cos_t) ** 1.5
        p_hg = (1.0 - g * g) / denom_hg

        omega_aer = float(_AEROSOL_TABLE[self.aerosol_type]["ssa"])
        scat_mol = sigma_mol
        scat_aer = omega_aer * sigma_aer
        scat_total = scat_mol + scat_aer

        # Avoid divide-by-zero at wavelengths where both scatter terms
        # are zero (unreachable in practice for this model but defensive).
        safe = scat_total > 0.0
        p_total = np.ones_like(scat_total)
        p_total[safe] = (scat_mol[safe] * p_rayleigh + scat_aer[safe] * p_hg) / scat_total[safe]
        return p_total

    def _single_scattering_albedo(
        self,
        sigma_mol: np.ndarray,
        sigma_aer: np.ndarray,
        sigma_h2o: np.ndarray,
    ) -> np.ndarray:
        """Extinction-weighted single-scattering albedo ``ω₀(λ)``.

        ``ω₀ = σ_scat / σ_ext`` where ``σ_scat`` counts molecular
        (pure scatter) plus aerosol ``ω_aer · σ_aer`` and ``σ_ext``
        counts everything including H₂O absorption. Bounded in
        ``[0, 1]`` by construction; returns zero wherever the total
        extinction vanishes.
        """
        omega_aer = float(_AEROSOL_TABLE[self.aerosol_type]["ssa"])
        scat = sigma_mol + omega_aer * sigma_aer
        ext = sigma_mol + sigma_aer + sigma_h2o
        omega0 = np.zeros_like(ext)
        safe = ext > 0.0
        omega0[safe] = scat[safe] / ext[safe]
        return omega0

    def _effective_atmospheric_temperature_K(self, sensor_altitude_m: float) -> float:
        """Graybody downwelling effective temperature [K].

        Evaluated at ``0.5 × sensor_altitude_m`` per RADIANT_Atmosphere.md
        §3.1: a plane-parallel troposphere with a fixed 6.5 K/km lapse
        rate and an isothermal tropopause clamp at 216.65 K (ICAO
        standard). Negative or sub-sea-level sensor altitudes clamp to
        ``h_eval = 0``; altitudes above ``2 × 11 km`` saturate at the
        tropopause temperature. This is the textbook closed-form
        approximation appropriate for a "simple" atmosphere.
        """
        h_eval_m = max(0.0, 0.5 * sensor_altitude_m)
        h_eval_m = min(h_eval_m, _TROPOPAUSE_H_M)
        t_sea = _T_SEA_LEVEL_K[self.standard_atmosphere]
        t_eff = t_sea - _LAPSE_RATE_K_PER_M * h_eval_m
        return max(t_eff, _TROPOPAUSE_T_K)

    def _h2o_extinction_km(self, wavelength_um: np.ndarray) -> np.ndarray:
        """Water-vapor extinction [1/km].

        Five Lorentzian bands plus a flat continuum. Both contributions
        scale linearly with precipitable water. The OD-per-km
        normalisation assumes the water column is concentrated in the
        boundary layer (the dominant case for working radiometry).
        """
        w = float(self.precipitable_water_cm)
        if w == 0.0:
            return np.zeros_like(wavelength_um, dtype=np.float64)

        sigma = np.zeros_like(wavelength_um, dtype=np.float64)
        for band in _H2O_BANDS:
            dx = (wavelength_um - band.centre_um) / band.hwhm_um
            lorentz = 1.0 / (1.0 + dx * dx)
            sigma += band.extinction_km_per_cm * w * lorentz

        sigma += H2O_CONTINUUM_KM * w
        return np.asarray(sigma, dtype=np.float64)

    # ------------------------------------------------------------------
    # Atmosphere protocol
    # ------------------------------------------------------------------

    def build_state(
        self,
        wavelength_um: np.ndarray,
        geometry: AtmosphericGeometry,
    ) -> AtmosphericState:
        """Compute the atmospheric state on the given grid."""
        lam = np.asarray(wavelength_um, dtype=np.float64)
        if lam.ndim != 1:
            raise ValueError(
                f"SimpleAtmosphere '{self.name}': wavelength_um must be 1-D, got shape {lam.shape}."
            )
        if lam.size < 2:
            raise ValueError(
                f"SimpleAtmosphere '{self.name}': wavelength_um needs at "
                f"least two samples, got {lam.size}."
            )
        if not np.all(np.diff(lam) > 0):
            raise ValueError(
                f"SimpleAtmosphere '{self.name}': wavelength_um must be strictly ascending."
            )
        if np.any(lam <= 0.0):
            raise ValueError(
                f"SimpleAtmosphere '{self.name}': wavelength_um must be strictly positive."
            )

        slant_m = geometry.slant_path_length_m()
        slant_km = slant_m / 1000.0
        mean_alt_m = 0.5 * (geometry.sensor_altitude_m + geometry.target_altitude_m)

        sigma_mol = self._rayleigh_extinction_km(lam, mean_alt_m)
        sigma_aer = self._aerosol_extinction_km(lam, mean_alt_m)
        sigma_h2o = self._h2o_extinction_km(lam)
        sigma_total = sigma_mol + sigma_aer + sigma_h2o  # [1/km]

        # Beer-Lambert. clip to [0, 1] is unnecessary because all
        # σ_i ≥ 0 and slant ≥ 0 → exp(...) ∈ (0, 1].
        tau = np.exp(-sigma_total * slant_km)

        # When slant path is zero (Δh = 0 — exo-like configuration of
        # SimpleAtmosphere) τ collapses to ones exactly.
        if slant_km == 0.0:
            tau = np.ones_like(lam)

        t_atm_eff_K = self._effective_atmospheric_temperature_K(geometry.sensor_altitude_m)

        cos_theta_sun = math.cos(geometry.solar_zenith_rad)
        cos_theta_scatter = geometry.cos_scattering_angle()
        omega0 = self._single_scattering_albedo(sigma_mol, sigma_aer, sigma_h2o)
        phase = self._single_scatter_phase_function(cos_theta_scatter, sigma_mol, sigma_aer)

        provenance: dict[str, Any] = {
            "model": "simple",
            "visibility_km": self.visibility_km,
            "aerosol_type": self.aerosol_type,
            "precipitable_water_cm": self.precipitable_water_cm,
            "standard_atmosphere": self.standard_atmosphere,
            "slant_path_km": slant_km,
            "mean_altitude_m": mean_alt_m,
            "t_atm_eff_K": t_atm_eff_K,
            "cos_theta_sun": cos_theta_sun,
            "cos_theta_scatter": cos_theta_scatter,
            "hg_asymmetry": HG_ASYMMETRY,
        }

        transmittance = SpectralData(
            name="atm.transmittance.simple",
            wavelength_um=lam,
            values=tau,
            unit="",
            source="SimpleAtmosphere (Beer-Lambert: Rayleigh+aerosol+H2O)",
            source_parameters=provenance,
        )

        # Single-scatter upwelling path radiance.  The standard
        # single-scatter approximation (Schott, *Remote Sensing*;
        # Liou, *Atmospheric Radiation*) is:
        #
        #   L_path(λ) = [E_sun(λ) / (4π)] · cos(θ_sun) · ω₀(λ)
        #                · P(Θ) · (1 − τ)
        #
        # where E_sun is TOA solar irradiance [W/m²/µm], the 4π comes
        # from the full-sphere normalization of the phase function, and
        # (1 − τ) is the path-integrated single-scatter source.
        #
        # Since toa_solar_equivalent_radiance returns E_sun/π, we
        # divide by an additional factor of 4 to get E_sun/(4π).
        #
        # We clamp to ≥ 0 because the AtmosphericState invariant
        # forbids negative path radiance, and for a sun below the
        # horizon cos θ_sun can legitimately be zero (producing a
        # hard zero rather than a negative number).
        if cos_theta_sun > 0.0:
            l_sun = toa_solar_equivalent_radiance(lam)
            path_radiance_values = (
                l_sun * cos_theta_sun * omega0 * phase * (1.0 - tau) / 4.0
            )
            path_radiance_values = np.maximum(path_radiance_values, 0.0)
            path_source = (
                f"SimpleAtmosphere single-scatter "
                f"(cos θ_sun={cos_theta_sun:.4f}, "
                f"cos Θ={cos_theta_scatter:.4f})"
            )
        else:
            path_radiance_values = np.zeros_like(lam)
            path_source = "SimpleAtmosphere single-scatter (sun below horizon)"

        path_radiance = SpectralData(
            name="atm.path_radiance.simple",
            wavelength_um=lam,
            values=path_radiance_values,
            unit="W/m²/sr/µm",
            source=path_source,
            source_parameters=provenance,
        )

        # Graybody downwelling: L_atm_down(λ) = (1 − τ) · B(λ, T_atm_eff).
        # At τ = 1 (exo-configuration / zero slant path) this is exactly
        # zero; at τ = 0 (opaque column) it saturates at the blackbody
        # curve, consistent with Kirchhoff's law for the atmospheric
        # column treated as a single isothermal slab.
        planck_curve = planck_spectral_radiance(lam, t_atm_eff_K)
        atm_emission_down_values = (1.0 - tau) * planck_curve
        atm_emission_down = SpectralData(
            name="atm.emission_down.simple",
            wavelength_um=lam,
            values=atm_emission_down_values,
            unit="W/m²/sr/µm",
            source=(f"SimpleAtmosphere graybody downwelling (T_atm_eff={t_atm_eff_K:.2f} K)"),
            source_parameters=provenance,
        )

        return AtmosphericState(
            transmittance=transmittance,
            path_radiance=path_radiance,
            atm_emission_down=atm_emission_down,
            geometry=geometry,
            derivation_chain=(
                f"SimpleAtmosphere(visibility_km={self.visibility_km}, "
                f"aerosol={self.aerosol_type}, pwv_cm={self.precipitable_water_cm})",
                f"slant_path_km={slant_km:.4f}, mean_alt_m={mean_alt_m:.1f}",
                f"L_path = L_sun · μ₀ · ω₀ · P(Θ) · (1 − τ); "
                f"μ₀={cos_theta_sun:.4f}, cos Θ={cos_theta_scatter:.4f}, "
                f"HG g={HG_ASYMMETRY}",
                f"L_atm_down = (1 − τ) · B(λ, T_atm_eff={t_atm_eff_K:.2f} K) "
                f"[{self.standard_atmosphere}]",
            ),
        )
