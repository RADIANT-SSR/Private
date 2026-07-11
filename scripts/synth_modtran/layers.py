"""Layered atmosphere builder for synthetic tape7 generation.

Builds temperature, pressure, and per-species mixing ratios for a
small set of altitude layers, per RADIANT's six named standard-
atmosphere profiles. This is deliberately NOT RADIANT's own atmosphere
model (radiant.atmosphere.simple) — it exists so the HITRAN/RADIS-
based synthetic tape7 generator has an independent vertical structure
to integrate over, rather than reusing RADIANT's own transmittance
approximation as its own "ground truth."

Physical inputs (published, not RADIANT-derived):
- Pressure/temperature/density altitude structure: ICAO standard
  atmosphere (COESA 1976), via the independent `ambiance` package.
- Per-profile sea-level temperature and total precipitable water:
  McClatchey et al. 1972 (AFCRL-72-0497) — the same reference MODTRAN's
  own MODEL 1-6 standard profiles are built from.
- CO2: well-mixed, 415 ppm (current atmospheric concentration).
- O3: a Chapman-layer-like profile peaking at 25 km, calibrated to a
  300 DU mid-latitude-average total column, scaled by the run's
  o3_scale.

Known limitation (stated plainly): only the sea-level temperature and
total-column-water anchors vary by profile; the vertical STRUCTURE
(lapse rate, tropopause height, water-vapor scale height) is held at
ICAO-standard shape for every profile. Real AFGL/McClatchey profiles
have profile-specific lapse rates and tropopause heights (e.g. a
tropical tropopause near 17 km vs. subarctic winter near 8 km) that
this simplified builder does not reproduce. This generator is scoped
for pipeline/scenario exercise, not profile-fidelity replication of
MODTRAN's MODEL cards.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from ambiance import Atmosphere

# Layer boundaries [km] — finer near the surface (H2O/aerosol-dominated),
# coarser aloft (CO2/O3-dominated, weaker gradients).
LAYER_BOUNDARIES_KM: tuple[float, ...] = (0.0, 1.0, 2.0, 4.0, 7.0, 12.0, 20.0, 35.0, 60.0, 100.0)

# McClatchey et al. 1972 (AFCRL-72-0497) sea-level temperature [K] and
# total precipitable water [cm] per profile — same published reference
# MODTRAN's MODEL 1-6 cards are built from.
SEA_LEVEL_T_K: dict[str, float] = {
    "us_standard": 288.15,
    "tropical": 299.65,
    "midlat_summer": 294.15,
    "midlat_winter": 272.15,
    "subarctic_summer": 287.15,
    "subarctic_winter": 257.15,
}
PROFILE_PWV_CM: dict[str, float] = {
    "us_standard": 1.4,
    "tropical": 4.11,
    "midlat_summer": 2.92,
    "midlat_winter": 0.85,
    "subarctic_summer": 2.08,
    "subarctic_winter": 0.42,
}

_ICAO_SEA_LEVEL_T_K = 288.15  # ambiance's own sea-level reference
_H2O_SCALE_HEIGHT_KM = 2.0  # standard atmospheric-physics value (e.g. Salby)
_M_AIR_G_MOL = 28.9647
_M_H2O_G_MOL = 18.0153
_M_O3_G_MOL = 47.9982
_RHO_WATER_KG_M3 = 1000.0
_DOBSON_UNIT_MOLEC_CM2 = 2.69e16
_O3_PEAK_ALTITUDE_KM = 25.0
_O3_LAYER_SIGMA_KM = 6.0
_O3_TOTAL_COLUMN_DU = 300.0  # mid-latitude annual average
_CO2_MOLE_FRACTION = 415e-6
_K_B = 1.380649e-23  # J/K, CODATA — SI Boltzmann constant


@dataclass(frozen=True)
class Layer:
    z_lo_km: float
    z_hi_km: float
    z_mid_km: float
    temperature_K: float
    pressure_bar: float
    number_density_cm3: float
    h2o_mole_fraction: float
    co2_mole_fraction: float
    o3_mole_fraction: float

    @property
    def thickness_km(self) -> float:
        return self.z_hi_km - self.z_lo_km


def build_layers(profile: str, h2o_scale: float, o3_scale: float) -> list[Layer]:
    """Build the layer stack for one (profile, h2o_scale, o3_scale) column.

    Temperature is the ICAO standard-atmosphere profile shifted by a
    uniform offset so its sea-level value matches ``SEA_LEVEL_T_K``.
    Pressure/density are the unmodified ICAO profile (climate-profile
    differences in P are secondary to the T differences this generator
    is scoped to capture). H2O mixing ratio is an exponential-scale-
    height profile whose surface value is numerically calibrated so the
    column-integrated precipitable water matches
    ``PROFILE_PWV_CM[profile] * h2o_scale``. O3 mixing ratio is a
    Gaussian layer calibrated to ``_O3_TOTAL_COLUMN_DU * o3_scale``.
    """
    z_mid = np.array(
        [
            (LAYER_BOUNDARIES_KM[i] + LAYER_BOUNDARIES_KM[i + 1]) / 2.0
            for i in range(len(LAYER_BOUNDARIES_KM) - 1)
        ]
    )
    thickness_km = np.diff(np.array(LAYER_BOUNDARIES_KM))

    atm = Atmosphere(z_mid * 1000.0)
    t_offset = SEA_LEVEL_T_K[profile] - _ICAO_SEA_LEVEL_T_K
    temperature_K = atm.temperature + t_offset
    pressure_bar = atm.pressure / 1.0e5  # Pa -> bar
    number_density_cm3 = (atm.pressure / (_K_B * temperature_K)) * 1e-6  # 1/m^3 -> 1/cm^3

    # --- H2O: exponential profile, calibrated to the target PWV column ---
    h2o_shape = np.exp(-z_mid / _H2O_SCALE_HEIGHT_KM)
    mass_col_per_q0 = np.sum(
        h2o_shape * atm.density * (thickness_km * 1000.0)
    )  # kg/m^2 per unit q0
    target_pwv_m = (PROFILE_PWV_CM[profile] * h2o_scale) / 100.0
    target_mass_col = target_pwv_m * _RHO_WATER_KG_M3  # kg/m^2
    q0_mass = target_mass_col / mass_col_per_q0 if mass_col_per_q0 > 0 else 0.0
    h2o_mass_mixing = q0_mass * h2o_shape
    h2o_mole_fraction = h2o_mass_mixing * (_M_AIR_G_MOL / _M_H2O_G_MOL)

    # --- O3: Gaussian layer, calibrated to the target Dobson column ---
    o3_shape = np.exp(-0.5 * ((z_mid - _O3_PEAK_ALTITUDE_KM) / _O3_LAYER_SIGMA_KM) ** 2)
    col_per_n0 = np.sum(
        o3_shape * number_density_cm3 * (thickness_km * 1e5)
    )  # cm^-2 per unit n0 mole fraction
    target_col_molec_cm2 = _O3_TOTAL_COLUMN_DU * o3_scale * _DOBSON_UNIT_MOLEC_CM2
    n0 = target_col_molec_cm2 / col_per_n0 if col_per_n0 > 0 else 0.0
    o3_mole_fraction = n0 * o3_shape

    layers = []
    for i in range(len(z_mid)):
        layers.append(
            Layer(
                z_lo_km=LAYER_BOUNDARIES_KM[i],
                z_hi_km=LAYER_BOUNDARIES_KM[i + 1],
                z_mid_km=float(z_mid[i]),
                temperature_K=float(temperature_K[i]),
                pressure_bar=float(pressure_bar[i]),
                number_density_cm3=float(number_density_cm3[i]),
                h2o_mole_fraction=float(max(h2o_mole_fraction[i], 1e-12)),
                co2_mole_fraction=_CO2_MOLE_FRACTION,
                o3_mole_fraction=float(max(o3_mole_fraction[i], 1e-15)),
            )
        )
    return layers


def layer_overlap_km(layer: Layer, z_lo_km: float, z_hi_km: float) -> float:
    """Length [km] of ``layer`` inside the closed interval [z_lo_km, z_hi_km]."""
    lo = max(layer.z_lo_km, z_lo_km)
    hi = min(layer.z_hi_km, z_hi_km)
    return max(0.0, hi - lo)


def airmass_factor(path_zenith_rad: float) -> float:
    """Plane-parallel secant airmass factor, capped to avoid a near-limb blowup."""
    cos_theta = math.cos(path_zenith_rad)
    return 1.0 / max(cos_theta, 0.05)
