"""Simple parametric atmosphere — closed-form Beer-Lambert.

Implements the ``SimpleAtmosphere`` model from
``docs/architecture/RADIANT_Atmosphere.md`` §3.1::

    τ_atm(λ) = exp[ −OD_total(λ) × air_mass ]

where ``OD_total`` is the **column-integrated** vertical optical depth
through an exponential atmosphere::

    OD_vert(λ) = Σ_species σ₀(λ) · H_s · [exp(−h_tgt/H_s) − exp(−h_sen/H_s)]

with four contributions:

- **Molecular (Rayleigh)** — Bucholtz 1995 sea-level coefficient
  ``σ_mol(λ) = 0.0088 · λ_µm⁻⁴·⁰⁹ km⁻¹`` with exponential scale
  height ``H_mol = 8 km``.
- **Aerosol (Mie)** — Koschmieder visibility relation
  ``σ_aer(550 nm) = 3.912 / V_km`` with three canonical Ångström
  exponents (rural ``α=1.3``, urban ``α=1.5``, maritime ``α=0.7``).
  Aerosol scale height ``H_aer = 1.2 km``.
- **Water vapor** (CU-161, 2026-07-17) — per-region curve-of-growth
  power law ``OD = k(λ) · w_eff^b(λ)`` in the path water amount,
  calibrated region-by-region against the real MODTRAN 6 water ladder
  (sub-linear ``b < 1`` in the saturated bands, super-linear
  ``b ≈ 1.5–1.75`` in the LWIR e-type continuum). Scale height
  ``H_h2o = 2 km``. Replaces the former five-Lorentzian fit whose far
  wings over-responded to water ~5× in the MWIR.
- **Well-mixed gases** (CU-161) — water-independent absorption floor
  per region (CO₂ 4.3/15 µm, N₂O, O₃ 9.6 µm, O₂/CH₄ overtones) on the
  molecular scale height; the term whose absence made the old model
  attribute the MWIR CO₂ floor to water.

This cut implements the full §3.1 simple-model triple:

- **``τ_atm(λ)``** via Beer-Lambert on the three extinction species.
- **``L_path(λ)``** via the single-scatter approximation, using a
  5778 K blackbody TOA solar spectrum from ``radiant.core.solar`` and
  a weighted two-component phase function (Rayleigh for molecular,
  Henyey-Greenstein with ``g = 0.7`` for aerosol).
- **``L_atm_down(λ)``** via the graybody ``(1 − τ_vert^D) · B(λ, T_eff)``
  (CU-155) with ``T_eff`` the standard-atmosphere temperature a small
  emission-height offset above the TARGET (plane-parallel troposphere,
  fixed 6.5 K/km lapse, floored at the ICAO tropopause 216.65 K) and
  ``D`` a flux-diffusivity exponent — both fit to the real MODTRAN 6
  up-looking H-runs (see the ``_ESKY_*`` constants). The sensor
  altitude does not enter: the sky a target sees is independent of
  where the sensor flies.

Assumptions
-----------
- Plane-parallel atmosphere; spherical-Earth correction applied past
  80° zenith via :class:`AtmosphericGeometry`.
- Each species has an exponential density profile with a fixed scale
  height. The optical depth is computed by analytically integrating
  ``σ₀ · exp(−h/H)`` from target to sensor altitude, then multiplying
  by the geometric air mass factor. This is exact for the assumed
  exponential profile and works correctly at all altitudes including
  orbital (LEO/MEO/GEO).
- Mean-altitude extinctions are still used for the *relative* species
  weights in the single-scattering albedo and phase function (these
  are ratios, not absolute ODs, so the approximation is benign).
- Wavelength dependence is monotone in each species. The water-vapor
  fit is bumpy by construction at the band centres but is smooth in
  the windows.
- Single thermodynamic equilibrium temperature (no pressure broadening
  variation along the path).

These assumptions fail in the upper stratosphere, in heavy cirrus, and
for narrow-band line absorption. Users with those needs run MODTRAN.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.errors import AtmosphereValidationError
from radiant.atmosphere.omega0_eff import omega0_eff
from radiant.atmosphere.protocol import (
    AtmosphericGeometry,
    AtmosphericState,
)
from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.solar import (
    toa_solar_equivalent_radiance,
    toa_solar_spectral_irradiance,
)
from radiant.core.spectral import SpectralData

logger = logging.getLogger(__name__)

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
H_H2O_M: float = 2_000.0

# Koschmieder visibility constant: σ_aer(550 nm) = KOSCHMIEDER / V_km  [1/km]
# 3.912 = -ln(0.02), the contrast threshold defining "meteorological
# visibility." Per RADIANT_Atmosphere.md §3.1.
KOSCHMIEDER: float = 3.912
AEROSOL_REFERENCE_WAVELENGTH_UM: float = 0.550

# Aerosol Ångström clamp wavelength [µm] (CU-088). The power law
# σ_aer ∝ λ^{−α} models scattering: it is good in VIS/SWIR, "already weak"
# but usable through MWIR, and *wrong* in LWIR where aerosol extinction is
# absorption-dominated and roughly flat, not decaying
# (RADIANT_Atmosphere.md §12 Open Question 2). The clamp is placed at the
# MWIR–LWIR boundary so the "weak but usable" MWIR power law is preserved
# and only the genuinely-wrong long-wave extrapolation is frozen at the
# boundary value instead of decaying unphysically toward zero.
AEROSOL_CLAMP_WAVELENGTH_UM: float = 5.0

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


# Calibrated gas-band region table (CU-161, 2026-07-17). Replaces the
# former five-Lorentzian water fit whose far wings made the MWIR water
# response ~5× too steep and which modeled no well-mixed gases at all.
#
# Per spectral region, the nadir full-column optical depth is
#
#     OD(w) = floor_od + k_h2o · w_eff^b_h2o
#
# where ``floor_od`` is the water-INDEPENDENT well-mixed-gas absorption
# (CO₂ 4.3/15 µm, N₂O, O₃ 9.6 µm, O₂/CH₄ overtones) in excess of what
# Rayleigh + aerosol already provide, and the water term is a
# curve-of-growth power law in the path water amount ``w_eff`` [cm]
# (sub-linear b < 1 in the saturated absorption bands; super-linear
# b ≈ 1.5–1.75 in the LWIR where the e-type continuum dominates).
#
# Generator: ``scripts/fit_simple_atmosphere_gas_bands.py`` — closed-form
# fits to the real MODTRAN 6 water ladder D4/A1/D5 (us_standard,
# rural 23 km, H₂O ×0.5/×1/×2, 2026-07-17 run set), cross-validated
# against the five other standard-profile anchors to ≤ ±0.012 τ in the
# water-relevant windows (worst: NIR on the driest profile, −0.034).
# Regions where the pre-existing Rayleigh+aerosol terms already meet or
# exceed the measured floor (VIS/UV — the aerosol there over-absorbs,
# see scenario 3.4's validation note) get floor_od = 0, never negative.
@dataclass(frozen=True)
class _GasRegion:
    lo_um: float
    hi_um: float
    floor_od: float  # vertical full-column well-mixed-gas OD [-]
    k_h2o: float  # water OD at 1 cm effective path water [per cm^b]
    b_h2o: float  # water curve-of-growth exponent [-]


_CALIBRATED_GAS_REGIONS: tuple[_GasRegion, ...] = (
    _GasRegion(lo_um=0.30, hi_um=0.45, floor_od=0.0000, k_h2o=0.0000, b_h2o=1.000),
    _GasRegion(lo_um=0.45, hi_um=0.70, floor_od=0.0000, k_h2o=0.0025, b_h2o=0.874),
    _GasRegion(lo_um=0.70, hi_um=1.30, floor_od=0.0000, k_h2o=0.1245, b_h2o=0.434),
    _GasRegion(lo_um=1.30, hi_um=1.50, floor_od=0.0000, k_h2o=1.0933, b_h2o=0.327),
    _GasRegion(lo_um=1.50, hi_um=1.75, floor_od=0.0133, k_h2o=0.0282, b_h2o=0.645),
    _GasRegion(lo_um=1.75, hi_um=2.05, floor_od=0.0000, k_h2o=1.1186, b_h2o=0.216),
    _GasRegion(lo_um=2.05, hi_um=2.40, floor_od=0.0725, k_h2o=0.0320, b_h2o=0.843),
    _GasRegion(lo_um=2.40, hi_um=3.10, floor_od=0.7434, k_h2o=0.9666, b_h2o=0.560),
    _GasRegion(lo_um=3.10, hi_um=3.50, floor_od=0.1366, k_h2o=0.5824, b_h2o=0.457),
    _GasRegion(lo_um=3.50, hi_um=5.00, floor_od=0.4497, k_h2o=0.0944, b_h2o=0.808),
    _GasRegion(lo_um=5.00, hi_um=7.50, floor_od=1.3543, k_h2o=1.7850, b_h2o=0.530),
    _GasRegion(lo_um=7.50, hi_um=8.00, floor_od=0.9424, k_h2o=0.9210, b_h2o=0.673),
    _GasRegion(lo_um=8.00, hi_um=10.00, floor_od=0.2751, k_h2o=0.0877, b_h2o=1.268),
    _GasRegion(lo_um=10.00, hi_um=12.00, floor_od=0.0471, k_h2o=0.0602, b_h2o=1.750),
    _GasRegion(lo_um=12.00, hi_um=14.29, floor_od=0.5956, k_h2o=0.1398, b_h2o=1.583),
)

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

# Total precipitable water column [cm] per standard-atmosphere profile.
# Values are the LOWTRAN/MODTRAN standard-profile water columns (McClatchey
# et al. 1972, AFCRL-72-0497; carried into MODTRAN MODELs 1–6). Gap 57: the
# climate preset implies its humidity — the loader applies these when the
# user selects a profile but leaves ``precipitable_water_cm`` at its schema
# default, so "tropical" does not silently run US-standard transmission.
# ``us_standard`` is pinned to the schema default (1.4, vs McClatchey's
# 1.42) so a default-everything configuration is bit-identical to before.
PROFILE_PWV_CM: dict[str, float] = {
    "us_standard": 1.4,
    "tropical": 4.11,
    "midlat_summer": 2.92,
    "midlat_winter": 0.85,
    "subarctic_summer": 2.08,
    "subarctic_winter": 0.42,
}

# ICAO tropospheric lapse rate and tropopause clamp.
_LAPSE_RATE_K_PER_M: float = 6.5e-3  # 6.5 K / km
_TROPOPAUSE_T_K: float = 216.65  # ICAO isothermal tropopause temperature
_TROPOPAUSE_H_M: float = 11_000.0

# --- CU-155: downwelling sky-emission calibration (fit 2026-07-18) ---
# E_sky_thermal = (1 − τ_sky,vert^D) · π · B(T(h_tgt + z_em)), where τ_sky,vert
# is the VERTICAL transmittance of the target→h_atm_top column — the sky the
# target actually sees. Two things deliberately do NOT enter: the sensor
# altitude (the sky above a ground target is the same whether the sensor is at
# 2 km or 500 km — the pre-fix model evaluated T at 0.5·h_sensor and clamped
# every space column to the 216.65 K tropopause, producing the measured
# ~5×/40× LWIR/MWIR downwelling deficit), and the sensor's viewing zenith
# (downwelling is a hemispheric flux at the target).
#
# Both constants are fit jointly to the real MODTRAN 6 up-looking H-runs
# (H2 us_standard + H4 tropical; band-integrated π·L_sky(48.2°), the
# diffusivity-angle hemispheric-flux proxy validated to ~15% against the E1
# flux table — tests/integration/test_modtran_real_runs.py):
#
#   z_em = 200 m  — emission-height offset: downwelling is dominated by
#                   near-surface air (the E1 flux DOWN at 14.4 µm ≈ π·B(283 K)).
#   D    = 1.1    — flux-diffusivity exponent on the vertical transmittance.
#                   The textbook Elsasser value is 1.66; the fitted value is
#                   lower because the CU-161 gas-band τ calibration (fit to
#                   slant-path transmission) already absorbs part of the
#                   hemispheric weighting in the LWIR window.
#
# Fit result, band-integrated model/MODTRAN (8–12 µm | 3–5 µm):
#   H2 us_standard 1.24 | 0.70    H4 tropical 1.41 | 1.34
# vs 0.21 | 0.018 and 0.21 | 0.026 before the fix. The residual ±40% tracks
# the CU-161 region-flat spectral-shape fragility, not temperature structure
# (an opacity-dependent spectral emission-height variant measured worse).
_ESKY_EMISSION_HEIGHT_M: float = 200.0
_ESKY_DIFFUSIVITY_D: float = 1.1


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
            raise AtmosphereValidationError(
                f"SimpleAtmosphere '{self.name}': visibility_km = "
                f"{self.visibility_km} is invalid. Visibility is the "
                "meteorological range in km and must be a positive finite number."
            )
        if self.aerosol_type not in _AEROSOL_TABLE:
            raise AtmosphereValidationError(
                f"SimpleAtmosphere '{self.name}': aerosol_type = "
                f"'{self.aerosol_type}' is not recognised. Choose one of "
                f"{sorted(_AEROSOL_TABLE)}."
            )
        if not math.isfinite(self.precipitable_water_cm) or self.precipitable_water_cm < 0.0:
            raise AtmosphereValidationError(
                f"SimpleAtmosphere '{self.name}': precipitable_water_cm = "
                f"{self.precipitable_water_cm} is invalid. It is a non-negative "
                "column amount in cm of liquid-equivalent water vapour."
            )
        if self.standard_atmosphere not in _T_SEA_LEVEL_K:
            raise AtmosphereValidationError(
                f"SimpleAtmosphere '{self.name}': standard_atmosphere = "
                f"'{self.standard_atmosphere}' is not recognised. Choose one "
                f"of {sorted(_T_SEA_LEVEL_K)}."
            )

    # ------------------------------------------------------------------
    # Column-integrated optical depth
    # ------------------------------------------------------------------

    @staticmethod
    def _column_length_km(h_low_m: float, h_high_m: float, scale_height_m: float) -> float:
        """Effective column length [km] for an exponential density profile.

        Analytically integrates ``exp(−h / H)`` from ``h_low`` to ``h_high``::

            ∫ exp(−h/H) dh = H · [exp(−h_low/H) − exp(−h_high/H)]

        The result is in km (matching the sea-level extinction units of
        [1/km]) so that ``σ₀ [1/km] × column_length [km] = OD``
        (dimensionless).

        For ``h_high ≫ H`` (orbital altitudes), ``exp(−h_high/H) → 0``
        and the column length saturates at ``H · exp(−h_low/H)``, i.e.
        the full atmospheric column above the target.
        """
        hs = scale_height_m
        return (hs / 1000.0) * (math.exp(-h_low_m / hs) - math.exp(-h_high_m / hs))

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
        # CU-088: clamp the Ångström fit beyond the MWIR-LWIR boundary. The
        # power law keeps decreasing extinction with wavelength, which is
        # wrong in LWIR; freeze it at the boundary value instead of
        # extrapolating toward zero.
        lam_eff = np.minimum(wavelength_um, AEROSOL_CLAMP_WAVELENGTH_UM)
        scaled = sigma_550 * (lam_eff / AEROSOL_REFERENCE_WAVELENGTH_UM) ** (-alpha)
        if np.any(wavelength_um > AEROSOL_CLAMP_WAVELENGTH_UM):
            # Warning-free-UX campaign: the Ångström clamp beyond 5 µm is a
            # documented property of choosing SimpleAtmosphere for an MWIR/LWIR
            # grid (CU-088), not a per-evaluate event — log at debug (quiet by
            # default, discoverable) instead of a UserWarning on every evaluate.
            logger.debug(
                "SimpleAtmosphere: aerosol extinction is clamped to its %.1f µm "
                "(MWIR-LWIR boundary) value for longer wavelengths — the Ångström "
                "power law is unreliable in MWIR and wrong in LWIR (CU-088). Aerosol "
                "sensitivity to visibility_km in those bands is approximate; use a "
                "MODTRAN or tabulated aerosol model for quantitative MWIR/LWIR work.",
                AEROSOL_CLAMP_WAVELENGTH_UM,
            )
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
        sigma_gas: np.ndarray | None = None,
    ) -> np.ndarray:
        """Extinction-weighted single-scattering albedo ``ω₀(λ)``.

        ``ω₀ = σ_scat / σ_ext`` where ``σ_scat`` counts molecular
        (pure scatter) plus aerosol ``ω_aer · σ_aer`` and ``σ_ext``
        counts everything including H₂O and well-mixed-gas absorption
        (the gas term entered with CU-161 — pure absorbers belong in
        the denominator only). Bounded in ``[0, 1]`` by construction;
        returns zero wherever extinction vanishes.

        Since the Gap 38 swap (2026-07-20) this internal ω₀ feeds only
        the phase-weighted ``L_path`` single-scatter terms; the
        ``E_sky_scattered`` diffuse-sky formula uses the MODTRAN-derived
        ``omega0_eff(λ, aerosol)`` lookup instead (that table is fit
        through the hemispheric-flux closed form and is not a valid
        substitute in the phase-function-weighted path-radiance
        integral, so the two deliberately coexist).
        """
        omega_aer = float(_AEROSOL_TABLE[self.aerosol_type]["ssa"])
        scat = sigma_mol + omega_aer * sigma_aer
        ext = sigma_mol + sigma_aer + sigma_h2o
        if sigma_gas is not None:
            ext = ext + sigma_gas
        omega0 = np.zeros_like(ext)
        safe = ext > 0.0
        omega0[safe] = scat[safe] / ext[safe]
        return omega0

    def _downwelling_effective_temperature_K(self, target_altitude_m: float) -> float:
        """Effective sky-emission temperature at the target [K] (CU-155).

        The downwelling reaching a target is dominated by the first
        optical depth of air ABOVE it, so the graybody temperature is the
        profile temperature a small emission-height offset above the
        target — ``T(h_tgt + _ESKY_EMISSION_HEIGHT_M)`` on the
        fixed-lapse ICAO troposphere, floored at the 216.65 K tropopause
        (evaluation height capped at the tropopause). The sensor altitude
        does not enter: the sky a ground target sees is the same whether
        the sensor flies at 2 km or 500 km. (The pre-CU-155 model
        evaluated at ``0.5 × h_sensor`` and clamped every space column to
        the tropopause — the measured ~5×/40× LWIR/MWIR deficit against
        the real up-looking H-runs.) Negative target altitudes clamp
        to 0 m.
        """
        h_eval_m = max(0.0, target_altitude_m) + _ESKY_EMISSION_HEIGHT_M
        h_eval_m = min(h_eval_m, _TROPOPAUSE_H_M)
        t_sea = _T_SEA_LEVEL_K[self.standard_atmosphere]
        t_eff = t_sea - _LAPSE_RATE_K_PER_M * h_eval_m
        return max(t_eff, _TROPOPAUSE_T_K)

    @staticmethod
    def _region_params(wavelength_um: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Per-wavelength (floor_od, k_h2o, b_h2o) from the region table.

        Wavelengths beyond the table's ends clamp to the first/last
        region (the table spans 0.30–14.29 µm; anything outside carries
        that edge region's calibration — documented fragility, the
        anchors do not constrain it).
        """
        lam = np.asarray(wavelength_um, dtype=np.float64)
        floor = np.empty_like(lam)
        k = np.empty_like(lam)
        b = np.empty_like(lam)
        for i, region in enumerate(_CALIBRATED_GAS_REGIONS):
            if i == 0:
                mask = lam < region.hi_um
            elif i == len(_CALIBRATED_GAS_REGIONS) - 1:
                mask = lam >= region.lo_um
            else:
                mask = (lam >= region.lo_um) & (lam < region.hi_um)
            floor[mask] = region.floor_od
            k[mask] = region.k_h2o
            b[mask] = region.b_h2o
        return floor, k, b

    def _h2o_vertical_od(self, wavelength_um: np.ndarray, col_h2o_km: float) -> np.ndarray:
        """Water-vapor vertical optical depth for a partial column.

        Curve of growth in the PATH water amount: the effective water in
        the column is ``w_eff = w · col_h2o/H_h2o`` (the fraction of the
        exponential water profile the path traverses), and

            OD_h2o(λ) = k(λ) · w_eff^b(λ)

        — sub-linear (b < 1) in the saturated bands, super-linear
        (b ≈ 1.5–1.75) in the LWIR continuum, per the CU-161 calibration
        against the real MODTRAN 6 water ladder. For the full column
        ``col_h2o = H_h2o`` and ``w_eff`` is the total precipitable
        water, reproducing the anchors exactly.
        """
        w = float(self.precipitable_water_cm)
        if w <= 0.0 or col_h2o_km <= 0.0:
            return np.zeros_like(np.asarray(wavelength_um, dtype=np.float64))
        _floor, k, b = self._region_params(wavelength_um)
        w_eff = w * col_h2o_km / (H_H2O_M / 1000.0)
        return k * np.power(w_eff, b)

    @staticmethod
    def _gas_floor_vertical_od(wavelength_um: np.ndarray, col_mol_km: float) -> np.ndarray:
        """Well-mixed-gas vertical optical depth for a partial column.

        The calibrated ``floor_od`` is the full-column value; well-mixed
        gases (CO₂, N₂O, O₃-as-modeled, O₂, CH₄) follow the molecular
        scale height, so a partial column carries the fraction
        ``col_mol/H_mol`` of it. Water-independent by construction
        (CU-161 — this is the term whose absence made the simple model
        attribute the MWIR's CO₂ floor to water).
        """
        if col_mol_km <= 0.0:
            return np.zeros_like(np.asarray(wavelength_um, dtype=np.float64))
        floor, _k, _b = SimpleAtmosphere._region_params(wavelength_um)
        return floor * (col_mol_km / (H_MOL_M / 1000.0))

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
            raise AtmosphereValidationError(
                f"SimpleAtmosphere '{self.name}': wavelength_um must be 1-D, got shape {lam.shape}."
            )
        if lam.size < 2:
            raise AtmosphereValidationError(
                f"SimpleAtmosphere '{self.name}': wavelength_um needs at "
                f"least two samples, got {lam.size}."
            )
        if not np.all(np.diff(lam) > 0):
            raise AtmosphereValidationError(
                f"SimpleAtmosphere '{self.name}': wavelength_um must be strictly ascending."
            )
        if np.any(lam <= 0.0):
            raise AtmosphereValidationError(
                f"SimpleAtmosphere '{self.name}': wavelength_um must be strictly positive."
            )

        slant_m = geometry.slant_path_length_m()
        slant_km = slant_m / 1000.0
        mean_alt_m = 0.5 * (geometry.sensor_altitude_m + geometry.target_altitude_m)

        # Sea-level extinction coefficients [1/km] — for column OD.
        sigma_mol_0 = self._rayleigh_extinction_km(lam, 0.0)
        sigma_aer_0 = self._aerosol_extinction_km(lam, 0.0)

        # Column-integrated vertical optical depth through exponential
        # atmosphere profiles.  Each species integrates σ₀·exp(-h/H)
        # from h_target to h_sensor, yielding an effective column
        # length [km] that is multiplied by the sea-level extinction.
        h_low_m = min(geometry.target_altitude_m, geometry.sensor_altitude_m)
        h_high_m = max(geometry.target_altitude_m, geometry.sensor_altitude_m)

        col_mol = self._column_length_km(h_low_m, h_high_m, H_MOL_M)
        col_aer = self._column_length_km(h_low_m, h_high_m, H_AER_M)
        col_h2o = self._column_length_km(h_low_m, h_high_m, H_H2O_M)

        # Vertical OD per species [dimensionless arrays over wavelength].
        # Water and well-mixed gases come from the CU-161 calibrated
        # region model (curve of growth in path water; CO₂/N₂O/O₃ floor).
        od_mol = sigma_mol_0 * col_mol
        od_aer = sigma_aer_0 * col_aer
        od_h2o = self._h2o_vertical_od(lam, col_h2o)
        od_gas = self._gas_floor_vertical_od(lam, col_mol)

        # Apply geometric air mass factor for off-nadir viewing.
        airmass = geometry.air_mass()
        od_total = (od_mol + od_aer + od_h2o + od_gas) * airmass

        # Beer-Lambert.  OD ≥ 0 by construction → τ ∈ (0, 1].
        tau = np.exp(-od_total)

        # Mean-altitude extinctions [1/km] — used only for the
        # *relative* species weights in SSA and phase function, not
        # for optical depth.  Water and gas-floor "extinctions" are the
        # column-mean values (OD/column) scaled to the mean altitude by
        # their scale heights, keeping the weights consistent with the
        # OD actually in the path.
        sigma_mol = self._rayleigh_extinction_km(lam, mean_alt_m)
        sigma_aer = self._aerosol_extinction_km(lam, mean_alt_m)
        h2o_scale = math.exp(-mean_alt_m / H_H2O_M)
        sigma_h2o = (od_h2o / max(col_h2o, 1e-12)) * h2o_scale
        sigma_gas = (od_gas / max(col_mol, 1e-12)) * math.exp(-mean_alt_m / H_MOL_M)

        t_atm_eff_K = self._downwelling_effective_temperature_K(geometry.target_altitude_m)

        cos_theta_sun = math.cos(geometry.solar_zenith_rad)
        cos_theta_scatter = geometry.cos_scattering_angle()
        omega0 = self._single_scattering_albedo(sigma_mol, sigma_aer, sigma_h2o, sigma_gas)
        phase = self._single_scatter_phase_function(cos_theta_scatter, sigma_mol, sigma_aer)

        provenance: dict[str, Any] = {
            "model": "simple",
            "visibility_km": self.visibility_km,
            "aerosol_type": self.aerosol_type,
            "precipitable_water_cm": self.precipitable_water_cm,
            "standard_atmosphere": self.standard_atmosphere,
            "slant_path_km": slant_km,
            "mean_altitude_m": mean_alt_m,
            "air_mass": airmass,
            "col_length_mol_km": col_mol,
            "col_length_aer_km": col_aer,
            "col_length_h2o_km": col_h2o,
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
            source="SimpleAtmosphere (column-integrated: Rayleigh+aerosol+H2O)",
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
            path_radiance_values = l_sun * cos_theta_sun * omega0 * phase * (1.0 - tau) / 4.0
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

        # Graybody downwelling (CU-155): L_atm_down(λ) = (1 − τ_vert^D) ·
        # B(λ, T_eff) — hemispheric-mean sky radiance at the target. The
        # VERTICAL optical depth with the fitted flux-diffusivity exponent
        # D gives the slab's hemispheric emissivity (the slant/airmass
        # factor belongs to the sensor's beam, not the sky's flux); T_eff
        # is target-anchored (see _downwelling_effective_temperature_K).
        # At τ_vert = 1 (exo / zero column) this is exactly zero; at
        # τ_vert = 0 it saturates at the blackbody curve (Kirchhoff).
        planck_curve = planck_spectral_radiance(lam, t_atm_eff_K)
        od_vert_total = od_mol + od_aer + od_h2o + od_gas
        atm_emission_down_values = -np.expm1(-_ESKY_DIFFUSIVITY_D * od_vert_total) * planck_curve
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
                f"Column-integrated OD: h_low={h_low_m:.0f} m, h_high={h_high_m:.0f} m, "
                f"airmass={airmass:.4f}",
                f"col_lengths [km]: mol={col_mol:.4f}, aer={col_aer:.4f}, h2o={col_h2o:.4f}",
                f"L_path = L_sun · μ₀ · ω₀ · P(Θ) · (1 − τ); "
                f"μ₀={cos_theta_sun:.4f}, cos Θ={cos_theta_scatter:.4f}, "
                f"HG g={HG_ASYMMETRY}",
                f"L_atm_down = (1 − τ) · B(λ, T_atm_eff={t_atm_eff_K:.2f} K) "
                f"[{self.standard_atmosphere}]",
            ),
        )

    # ------------------------------------------------------------------
    # Option C evaluate()
    # ------------------------------------------------------------------

    def evaluate(
        self,
        wavelength_um: np.ndarray,
        los: LineOfSightGeometry,
        params: ParameterSet,
    ) -> AtmosphericQuantities:
        """Option C two-leg quantities bundle with A3 partial-column support.

        Scope (Stage 5 — Option C Implementation Plan §Stage 5):

        - Supports arbitrary ``0 ≤ h_tgt < h_atm_top``.  At ``h_tgt == 0`` the
          code path is bit-exactly the post-Stage-4 behaviour so Cell 28 /
          Cell 58 anchors at rtol=1e-6 are preserved.
        - ``tau_up`` = exp(−airmass_up · ∫_{h_tgt}^{h_sensor} k(λ,z) dz).
        - ``tau_sun`` = exp(−airmass_sun · ∫_{h_tgt}^{h_atm_top} k(λ,z) dz).
        - ``tau_full_up`` = exp(−airmass_up · ∫_{0}^{h_sensor} k(λ,z) dz) —
          the ground-to-sensor column used by the background branch.  This
          is **independent of** ``h_tgt`` by construction.
        - ``L_path_up`` = single-scatter integral from h_tgt to h_sensor
          (uses (1 − τ_up)).
        - ``L_path_full`` = single-scatter integral from 0 to h_sensor
          (uses (1 − τ_full_up)).
        - ``E_sky_scattered = E_TOA · cos(θ_s) · ω₀ · (1 − τ_down,vert)``
          on the h_tgt→h_sensor vertical column (same slab as thermal)
          (Stage 6, ADR-0002).  Degrades to 0 as cos θ_s → 0 (sun below
          horizon) or as h_tgt → h_sensor (vacuum limit).
        - ``E_sky_thermal = (1 − τ_sky,vert^D) · π · B(T(h_tgt + z_em))``
          (CU-155) on the h_tgt→h_atm_top vertical column — the sky the
          target sees, independent of the sensor — with the H-run-fit
          ``_ESKY_*`` constants; degrades to 0 exactly as
          ``h_tgt → h_atm_top``.

        The sensor altitude comes from ``params["geometry.sensor_altitude_m"]``
        (the LineOfSightGeometry does not carry ``h_sensor`` in v1 — see
        `docs/RADIANT_SourceStage.md`).
        """
        h_tgt = los.h_tgt

        lam = np.asarray(wavelength_um, dtype=np.float64)
        if lam.ndim != 1:
            raise AtmosphereValidationError(
                f"SimpleAtmosphere '{self.name}': wavelength_um must be 1-D, got shape {lam.shape}."
            )
        if lam.size < 2:
            raise AtmosphereValidationError(
                f"SimpleAtmosphere '{self.name}': wavelength_um needs at "
                f"least two samples, got {lam.size}."
            )
        if not np.all(np.diff(lam) > 0):
            raise AtmosphereValidationError(
                f"SimpleAtmosphere '{self.name}': wavelength_um must be strictly ascending."
            )
        if np.any(lam <= 0.0):
            raise AtmosphereValidationError(
                f"SimpleAtmosphere '{self.name}': wavelength_um must be strictly positive."
            )

        # Sensor altitude from the ParameterSet (LineOfSightGeometry does
        # not carry h_sensor in v1 — see Stage 3 plan).
        h_sensor_m = float(params.get("geometry.sensor_altitude_m"))
        if h_sensor_m < 0.0:
            raise ParameterBoundsError(
                what=f"SimpleAtmosphere.evaluate: h_sensor = {h_sensor_m} m is negative",
                why="Sensor altitude must be non-negative.",
                action="Set geometry.sensor_altitude_m ≥ 0.",
                context={"h_sensor_m": h_sensor_m},
            )

        # A3 degenerate case: h_tgt == h_atm_top collapses the sun-leg
        # column to zero extent, making the solar airmass undefined.
        # Physically this means the target is above the atmosphere — the
        # caller should use target_location='no_atmosphere' / 'space'
        # instead of routing through the simple backend.
        if h_tgt >= los.h_atm_top:
            raise ParameterBoundsError(
                what=(
                    f"SimpleAtmosphere.evaluate: h_tgt = {h_tgt} m is at or "
                    f"above h_atm_top = {los.h_atm_top} m — column above "
                    "the target has zero vertical extent."
                ),
                why=(
                    "The atmospheric-column integrals need a positive "
                    "(h_tgt, h_atm_top) interval.  At equality the sun "
                    "down-leg airmass is undefined (0/0) and the simple "
                    "backend is outside its validity window."
                ),
                action=(
                    "Use target_location='no_atmosphere' with sub-case "
                    "'space' for above-atmosphere targets, or lower h_tgt "
                    "below h_atm_top."
                ),
                context={"h_tgt": h_tgt, "h_atm_top": los.h_atm_top},
            )

        # Sensor must sit above the target for the up-leg column to have
        # positive extent.  An airborne target higher than the sensor is
        # a looking-up configuration which Option C's partial-column model
        # does not support (it would require a separate downlooking-from-
        # target-to-sensor integral).
        if h_sensor_m < h_tgt:
            raise ParameterBoundsError(
                what=(
                    f"SimpleAtmosphere.evaluate: h_sensor = {h_sensor_m} m is "
                    f"below h_tgt = {h_tgt} m (looking-up configuration)."
                ),
                why=(
                    "The A3 partial-column model integrates the slant column "
                    "from h_tgt upward to h_sensor; h_sensor must be at or "
                    "above h_tgt for the integral to be well-defined."
                ),
                action=(
                    "Raise geometry.sensor_altitude_m above h_tgt, or model "
                    "a looking-up configuration with a dedicated backend."
                ),
                context={"h_sensor_m": h_sensor_m, "h_tgt": h_tgt},
            )

        # --- Geometry factors ---
        # Up-leg airmass for the target→sensor slant column.
        # A3 partial-column: the observer zenith is defined at the target,
        # so for h_tgt > 0 we build an AtmosphericGeometry with
        # target_altitude_m = h_tgt and sensor_altitude_m = h_sensor_m.
        # For h_tgt == 0 we retain the exact legacy construction
        # (target_altitude_m=0.0) so Cell 28 / Cell 58 anchors remain
        # bit-exact at rtol=1e-6.
        if h_tgt == 0.0:
            # Exact legacy path (bit-invariant for the h_tgt=0 anchors).
            airmass_up = (
                los.path_airmass_up
                if h_sensor_m >= los.h_atm_top
                else (
                    AtmosphericGeometry(
                        sensor_altitude_m=h_sensor_m,
                        target_altitude_m=0.0,
                        path_zenith_rad=los.theta_o,
                    ).air_mass()
                )
            )
        else:
            # A3 partial-column airmass: target→sensor slant through the
            # (h_tgt, h_sensor) column.  Using AtmosphericGeometry here
            # gives spherical-Earth behaviour identical to the legacy
            # construction; reduces to sec(θ_o) in the plane-parallel
            # limit (Δh / cos θ_o with Δh = h_sensor_m − h_tgt).
            airmass_up = AtmosphericGeometry(
                sensor_altitude_m=h_sensor_m,
                target_altitude_m=h_tgt,
                path_zenith_rad=los.theta_o,
            ).air_mass()

        # For the sun down-leg, the equivalent "airmass_down" is sec(θ_s)
        # with a spherical correction past 80°.  Reuse the same
        # AtmosphericGeometry class, with target_altitude_m = h_tgt (A3;
        # 0 for the legacy h_tgt=0 path) and sensor_altitude_m = h_atm_top
        # as the "upper endpoint" of the solar column.  Use params
        # fallback when the LOS does not carry theta_s (shadow-mode
        # legacy parity).
        if los.theta_s is not None:
            theta_s_effective = los.theta_s
        else:
            try:
                theta_s_effective = float(params.get("geometry.solar_zenith_rad"))
            except (KeyError, TypeError):
                theta_s_effective = 0.0
        if math.cos(theta_s_effective) > 0.0:
            sun_geom = AtmosphericGeometry(
                sensor_altitude_m=los.h_atm_top,
                target_altitude_m=h_tgt,
                path_zenith_rad=min(theta_s_effective, ZENITH_CEILING_RAD_SIMPLE),
            )
            airmass_sun = sun_geom.air_mass()
        else:
            airmass_sun = 1.0  # vertical column — irrelevant when sun term is zero

        # --- Column-integrated OD ---
        # Sea-level extinction per species [1/km]; water + well-mixed
        # gases come from the CU-161 calibrated region model.
        sigma_mol_0 = self._rayleigh_extinction_km(lam, 0.0)
        sigma_aer_0 = self._aerosol_extinction_km(lam, 0.0)

        # Up-leg column length: [h_tgt, h_sensor_m] for A3, [0, h_sensor_m]
        # for the h_tgt=0 surface-target case (unchanged).
        col_mol_up = self._column_length_km(h_tgt, h_sensor_m, H_MOL_M)
        col_aer_up = self._column_length_km(h_tgt, h_sensor_m, H_AER_M)
        col_h2o_up = self._column_length_km(h_tgt, h_sensor_m, H_H2O_M)

        od_vert_up = (
            sigma_mol_0 * col_mol_up
            + sigma_aer_0 * col_aer_up
            + self._h2o_vertical_od(lam, col_h2o_up)
            + self._gas_floor_vertical_od(lam, col_mol_up)
        )
        od_slant_up = od_vert_up * airmass_up
        tau_up = np.exp(-od_slant_up)

        # Sun-leg column length: [h_tgt, h_atm_top].  For h_tgt=0 this
        # reduces to [0, h_atm_top] (the legacy full-column solar leg).
        col_mol_sun = self._column_length_km(h_tgt, los.h_atm_top, H_MOL_M)
        col_aer_sun = self._column_length_km(h_tgt, los.h_atm_top, H_AER_M)
        col_h2o_sun = self._column_length_km(h_tgt, los.h_atm_top, H_H2O_M)
        od_vert_sun = (
            sigma_mol_0 * col_mol_sun
            + sigma_aer_0 * col_aer_sun
            + self._h2o_vertical_od(lam, col_h2o_sun)
            + self._gas_floor_vertical_od(lam, col_mol_sun)
        )
        od_slant_sun = od_vert_sun * airmass_sun
        tau_sun = np.exp(-od_slant_sun)

        # tau_full_up: the ground-to-sensor column, used by the background
        # branch regardless of the airborne target's altitude.  For h_tgt=0
        # this is identically tau_up (preserved via .copy() so the two
        # arrays are independent objects but equal element-wise).
        if h_tgt == 0.0:
            tau_full_up = tau_up.copy()
        else:
            col_mol_full = self._column_length_km(0.0, h_sensor_m, H_MOL_M)
            col_aer_full = self._column_length_km(0.0, h_sensor_m, H_AER_M)
            col_h2o_full = self._column_length_km(0.0, h_sensor_m, H_H2O_M)
            od_vert_full = (
                sigma_mol_0 * col_mol_full
                + sigma_aer_0 * col_aer_full
                + self._h2o_vertical_od(lam, col_h2o_full)
                + self._gas_floor_vertical_od(lam, col_mol_full)
            )
            od_slant_full = od_vert_full * airmass_up
            tau_full_up = np.exp(-od_slant_full)

        # --- E_TOA from core solar spectrum ---
        E_TOA = np.asarray(toa_solar_spectral_irradiance(lam), dtype=np.float64)

        # --- Single-scatter L_path_up ---
        # Mean-altitude extinctions for the phase function and SSA weights.
        # For h_tgt=0 the mean altitude is 0.5 · h_sensor_m (preserves the
        # legacy scaling bit-exactly).  For h_tgt > 0 we use the mean of
        # (h_tgt, h_sensor_m) so the phase-function weights track the
        # column actually being integrated.
        mean_alt_m = 0.5 * (h_tgt + h_sensor_m)
        sigma_mol = self._rayleigh_extinction_km(lam, mean_alt_m)
        sigma_aer = self._aerosol_extinction_km(lam, mean_alt_m)
        h2o_scale = math.exp(-mean_alt_m / H_H2O_M)
        # Column-mean water/gas "extinctions" from the up-leg ODs (CU-161),
        # scaled to the mean altitude by their scale heights — relative
        # weights for SSA/phase only, not optical depth.
        sigma_h2o = (self._h2o_vertical_od(lam, col_h2o_up) / max(col_h2o_up, 1e-12)) * h2o_scale
        sigma_gas = (
            self._gas_floor_vertical_od(lam, col_mol_up) / max(col_mol_up, 1e-12)
        ) * math.exp(-mean_alt_m / H_MOL_M)

        # Solar-zenith fallback: when the LOS does not carry theta_s (the
        # LWIR-friendly Stage-2 inferrer default), the simple backend
        # falls back to the ParameterSet default for the single-scatter
        # L_path computation.  This preserves bit-exact equivalence with
        # the legacy build_state() path in shadow mode — the T1 assembly
        # arm (which has ρ = 0) is unaffected either way.  Descriptors
        # that do carry theta_s override the params default.
        if los.theta_s is not None:
            theta_s_for_scatter = los.theta_s
        else:
            try:
                theta_s_for_scatter = float(params.get("geometry.solar_zenith_rad"))
            except (KeyError, TypeError):
                theta_s_for_scatter = 0.0
        cos_theta_sun = math.cos(theta_s_for_scatter)

        if los.delta_phi is not None:
            delta_phi_for_scatter = los.delta_phi
        else:
            try:
                delta_phi_for_scatter = float(params.get("geometry.solar_azimuth_rad"))
            except (KeyError, TypeError):
                delta_phi_for_scatter = 0.0

        # Scatter-angle geometry: target_altitude_m = h_tgt for A3 consistency.
        # For h_tgt=0 this reduces to the exact legacy construction.
        # Guard: AtmosphericGeometry rejects solar_zenith_rad ≥ π/2, so
        # only construct it when the sun is meaningfully above the
        # horizon (cos_theta_sun > the same horizon tolerance used by
        # E_sky_scattered below — keeps the two branches in sync).
        omega0 = self._single_scattering_albedo(sigma_mol, sigma_aer, sigma_h2o, sigma_gas)
        if cos_theta_sun > 1.0e-12:
            scatter_geom = AtmosphericGeometry(
                sensor_altitude_m=h_sensor_m,
                target_altitude_m=h_tgt,
                path_zenith_rad=los.theta_o,
                solar_zenith_rad=theta_s_for_scatter,
                solar_azimuth_rad=delta_phi_for_scatter,
            )
            cos_theta_scatter = scatter_geom.cos_scattering_angle()
            phase = self._single_scatter_phase_function(
                cos_theta_scatter,
                sigma_mol,
                sigma_aer,
            )
            l_sun = toa_solar_equivalent_radiance(lam)
            # L_path_up uses (1 − τ_up) over the partial column [h_tgt, h_sensor].
            L_path_vals = l_sun * cos_theta_sun * omega0 * phase * (1.0 - tau_up) / 4.0
            L_path_vals = np.maximum(L_path_vals, 0.0)
        else:
            L_path_vals = np.zeros_like(lam)
        L_path_up = L_path_vals

        # L_path_full: the background-branch single-scatter radiance,
        # integrated over the full ground-to-sensor column.  For h_tgt=0
        # this is identically L_path_up (preserved via .copy()).  For
        # h_tgt > 0 we need the single-scatter integral over [0, h_sensor],
        # which uses (1 − τ_full_up) and the mean-altitude weights for
        # that full column.
        if h_tgt == 0.0:
            L_path_full = L_path_up.copy()
        else:
            mean_alt_full_m = 0.5 * h_sensor_m
            sigma_mol_full = self._rayleigh_extinction_km(lam, mean_alt_full_m)
            sigma_aer_full = self._aerosol_extinction_km(lam, mean_alt_full_m)
            h2o_scale_full = math.exp(-mean_alt_full_m / H_H2O_M)
            col_h2o_full_w = self._column_length_km(0.0, h_sensor_m, H_H2O_M)
            col_mol_full_w = self._column_length_km(0.0, h_sensor_m, H_MOL_M)
            sigma_h2o_full = (
                self._h2o_vertical_od(lam, col_h2o_full_w) / max(col_h2o_full_w, 1e-12)
            ) * h2o_scale_full
            sigma_gas_full = (
                self._gas_floor_vertical_od(lam, col_mol_full_w) / max(col_mol_full_w, 1e-12)
            ) * math.exp(-mean_alt_full_m / H_MOL_M)
            # Scatter geometry for the ground-based full column: the
            # observer zenith is still θ_o at the target, but the target
            # is now on the ground.  Reuse the legacy target_altitude_m=0
            # shape so the phase function matches the surface-target case.
            # Same horizon guard as the L_path_up block — skip the
            # AtmosphericGeometry construction when cos θ_s ≤ tolerance.
            if cos_theta_sun > 1.0e-12:
                scatter_geom_full = AtmosphericGeometry(
                    sensor_altitude_m=h_sensor_m,
                    target_altitude_m=0.0,
                    path_zenith_rad=los.theta_o,
                    solar_zenith_rad=theta_s_for_scatter,
                    solar_azimuth_rad=delta_phi_for_scatter,
                )
                cos_theta_scatter_full = scatter_geom_full.cos_scattering_angle()
                omega0_full = self._single_scattering_albedo(
                    sigma_mol_full, sigma_aer_full, sigma_h2o_full, sigma_gas_full
                )
                phase_full = self._single_scatter_phase_function(
                    cos_theta_scatter_full, sigma_mol_full, sigma_aer_full
                )
                l_sun_full = toa_solar_equivalent_radiance(lam)
                L_path_full_vals = (
                    l_sun_full
                    * cos_theta_sun
                    * omega0_full
                    * phase_full
                    * (1.0 - tau_full_up)
                    / 4.0
                )
                L_path_full = np.maximum(L_path_full_vals, 0.0)
            else:
                L_path_full = np.zeros_like(lam)

        # --- E_sky_thermal: (1 − τ_sky,vert^D) · π · B(T(h_tgt + z_em)) (CU-155) ---
        # τ_sky,vert is the VERTICAL transmittance of the target→h_atm_top
        # column (od_vert_sun) — the sky the target actually sees; the
        # sensor's altitude and zenith do not enter a hemispheric flux at
        # the target. D (flux-diffusivity exponent) and the emission-height
        # offset in T_eff are fit to the real MODTRAN up-looking H-runs —
        # see the _ESKY_* constants. As h_tgt → h_atm_top the sky column
        # collapses, τ_sky,vert → 1, and E_sky_thermal → 0 exactly (the
        # vacuum limit, Anchor 2, is preserved).
        # tau_down_vertical (target→sensor column) is kept for the
        # E_sky_scattered slab below (Stage 6 / Gap 38 semantics unchanged).
        tau_down_vertical = np.exp(-od_vert_up)
        t_atm_eff_K = self._downwelling_effective_temperature_K(h_tgt)
        B_atm = planck_spectral_radiance(lam, t_atm_eff_K)
        E_sky_thermal = -np.expm1(-_ESKY_DIFFUSIVITY_D * od_vert_sun) * np.pi * B_atm

        # --- E_sky_scattered: single-scatter diffuse solar on target ---
        # Stage 6 (ADR-0002 / Option C plan):
        #     E_sky_scattered(λ) = E_TOA(λ) · cos(θ_s) · ω₀(λ) · (1 − τ_down,vert(λ))
        # where τ_down,vert is the *vertical* (airmass=1) transmittance of the
        # target→sensor column (identical to the column used by E_sky_thermal,
        # which keeps the two decomposed components on a symmetric footing —
        # both are diffuse-sky fluxes at the target generated within the same
        # atmospheric slab) and ω₀ is the MODTRAN-derived effective albedo
        # ω₀_eff(λ, aerosol) (Gap 38, swapped 2026-07-20): the value that
        # makes this closed form reproduce the real MODTRAN 6 ground-level
        # diffuse flux (band-median inversion of the E1/E3/E4 flux tables;
        # see atmosphere/omega0_eff.py). The previous extinction-weighted
        # column ω₀ evaluated ≈ 1.000 for space columns, over-predicting
        # diffuse sky irradiance ~1.3× (VIS rural) to ~5× (SWIR/urban).
        # Physics:
        #   • cos(θ_s) projects the TOA normal irradiance onto the horizontal
        #     target plane (plane-parallel single-scatter convention).
        #   • ω₀_eff converts extinction to effective scattering (absorbed
        #     photons do not contribute; the fit through this formula also
        #     absorbs MODTRAN's multiple-scatter contribution).
        #   • (1 − τ_down,vert) is the fraction of the incoming solar flux
        #     that interacts with the overhead atmospheric slab and is
        #     scattered isotropically toward the target.  The *vertical*
        #     form matches the diffuse geometry (isotropic hemispheric
        #     integral) — the slant airmass factor belongs to the direct
        #     beam, not to the downwelling diffuse.
        #   • Same column as E_sky_thermal ⇒ both diffuse components share
        #     an identical optical-thickness weighting, which is the
        #     standard textbook single-scatter + Kirchhoff split for a
        #     plane-parallel graybody slab.
        #   • For sun at or below horizon (cos θ_s ≤ 0) the term is 0.
        #   • As h_tgt → h_sensor the slab collapses, (1 − τ_down,vert) → 0,
        #     and E_sky_scattered → 0 (vacuum limit) — mirrors E_sky_thermal.
        #   • The ceiling is E_TOA · cos(θ_s) since ω₀ ≤ 1 and (1−τ) ≤ 1
        #     (energy-conservation check in the single-scatter limit).
        omega0_up = omega0_eff(lam, self.aerosol_type)
        # Sun-below-horizon guard: cos(π/2) evaluates to ~6e-17 in IEEE-754
        # due to π round-off; treat cosines below a small tolerance as
        # exactly zero so the diffuse-sky term is strictly null for
        # θ_s ≥ π/2 (matches the direct-solar term's sentinel behaviour in
        # assembly._direct_solar_term and the Stage 6 Anchor-3 fragility
        # test, which asserts exact-zero via np.testing.assert_array_equal).
        _COS_HORIZON_TOL = 1.0e-12
        if cos_theta_sun > _COS_HORIZON_TOL:
            E_sky_scattered = E_TOA * cos_theta_sun * omega0_up * (1.0 - tau_down_vertical)
            E_sky_scattered = np.maximum(E_sky_scattered, 0.0)
        else:
            E_sky_scattered = np.zeros_like(lam)

        # Snap tiny numerical negatives (from floating-point cancellation) to 0.
        # τ ∈ (0, 1] and (1 − τ) is the main risk; with expm1 we avoid it but
        # the assembly invariant forbids silent clipping past the tolerance.
        E_sky_thermal = np.maximum(E_sky_thermal, 0.0)

        return AtmosphericQuantities(
            wavelength_um=lam,
            tau_sun=tau_sun,
            tau_up=tau_up,
            tau_full_up=tau_full_up,
            E_TOA=E_TOA,
            E_sky_scattered=E_sky_scattered,
            E_sky_thermal=E_sky_thermal,
            L_path_up=L_path_up,
            L_path_full=L_path_full,
        )


# Re-export the spherical ceiling so evaluate() above can clamp sun zenith
# without importing from protocol.py inside the method body.
from radiant.atmosphere.protocol import (  # noqa: E402  # circular-avoidance re-export
    ZENITH_CEILING_RAD as ZENITH_CEILING_RAD_SIMPLE,
)
