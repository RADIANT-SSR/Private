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

This 2B.2 cut implements **transmittance only**. The single-scatter
``L_path`` formulation in §3.1 needs a solar source spectrum, and the
graybody downwelling needs the Planck function — both currently live
in ``radiant.source`` which physics stages may not import (Rule 11).
``L_path`` and ``L_atm_down`` are populated as numerical zero, which
is consistent with the doc's "always populated, prefer zero over
``None``" rule. The two open items are recorded in ``notes/blocked.md``.

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

# Ångström exponents and (currently unused) single-scattering albedos
# per aerosol type, from RADIANT_Atmosphere.md §3.1. SSA values are
# placeholders for the future single-scatter L_path implementation.
_AEROSOL_TABLE: dict[str, dict[str, float]] = {
    "rural": {"angstrom": 1.3, "ssa": 0.95},
    "urban": {"angstrom": 1.5, "ssa": 0.85},
    "maritime": {"angstrom": 0.7, "ssa": 0.99},
}


# Five-band water-vapor absorption fit. Each entry: centre wavelength
# (µm), peak optical depth at w_pw = 1 cm precipitable water, and the
# half-width-at-half-max (HWHM, µm) of a Lorentzian-shaped band. The
# values are tuned to give monotone OD scaling with w_pw and band
# depths consistent with US Standard MODTRAN runs at the band centres.
# Outside the bands the contribution falls off as 1/(1 + (Δλ/HWHM)²)
# and is dominated at long wavelengths by the continuum term below.
@dataclass(frozen=True)
class _H2OBand:
    centre_um: float
    peak_od_per_cm: float
    hwhm_um: float


_H2O_BANDS: tuple[_H2OBand, ...] = (
    _H2OBand(centre_um=1.4, peak_od_per_cm=0.6, hwhm_um=0.06),
    _H2OBand(centre_um=1.9, peak_od_per_cm=1.4, hwhm_um=0.10),
    _H2OBand(centre_um=2.7, peak_od_per_cm=3.5, hwhm_um=0.15),
    _H2OBand(centre_um=3.2, peak_od_per_cm=0.8, hwhm_um=0.10),
    _H2OBand(centre_um=6.3, peak_od_per_cm=4.0, hwhm_um=0.40),
)

# Continuum water-vapor extinction at long wavelengths [1/km/(cm pwv)].
# Tiny but nonzero — represents the rotational line wing buildup that
# is the leading background term in MWIR/LWIR for the simple model.
H2O_CONTINUUM_KM: float = 0.002


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
            sigma += band.peak_od_per_cm * w * lorentz

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

        provenance: dict[str, Any] = {
            "model": "simple",
            "visibility_km": self.visibility_km,
            "aerosol_type": self.aerosol_type,
            "precipitable_water_cm": self.precipitable_water_cm,
            "standard_atmosphere": self.standard_atmosphere,
            "slant_path_km": slant_km,
            "mean_altitude_m": mean_alt_m,
        }

        transmittance = SpectralData(
            name="atm.transmittance.simple",
            wavelength_um=lam,
            values=tau,
            unit="",
            source="SimpleAtmosphere (Beer-Lambert: Rayleigh+aerosol+H2O)",
            source_parameters=provenance,
        )

        # L_path and L_atm_down are stubs in this 2B.2 cut. See
        # notes/blocked.md for the open items: single-scatter L_path
        # needs a solar source spectrum, graybody L_atm_down needs the
        # Planck function. Both live in radiant.source which physics
        # stages may not import (CLAUDE.md Rule 11).
        zeros = np.zeros_like(lam)
        path_radiance = SpectralData(
            name="atm.path_radiance.simple",
            wavelength_um=lam,
            values=zeros,
            unit="W/m²/sr/µm",
            source="SimpleAtmosphere stub (pending solar source)",
            source_parameters=provenance,
        )
        atm_emission_down = SpectralData(
            name="atm.emission_down.simple",
            wavelength_um=lam,
            values=zeros.copy(),
            unit="W/m²/sr/µm",
            source="SimpleAtmosphere stub (pending Planck-in-core)",
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
            ),
        )
