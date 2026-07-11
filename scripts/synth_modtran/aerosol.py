"""Simplified aerosol optical depth and single-scatter estimate.

UNLIKE hitran_layers.py and emission.py, this module is NOT
independent physics -- HITRAN has no aerosol/particulate data at all,
so there is no line-by-line substitute here. This uses the same
published Koschmieder visibility relation and Angstrom power law that
RADIANT's own SimpleAtmosphere model uses (same literature source,
independently re-implemented here rather than imported, but the same
tier of approximation -- not multiple-scattering DISORT). Ground
reflection (GRND RFLT / DRCT RFLT) is not modeled: every run in
modtran_run_matrix.csv has surface_albedo_surref = 0, so those tape7
columns are legitimately zero regardless of method.
"""

from __future__ import annotations

import math

import numpy as np

from scripts.synth_modtran.emission import planck_radiance_W_cm2_sr_cm1

# Koschmieder visibility constant: sigma_aer(550nm) = KOSCHMIEDER / V_km [1/km].
_KOSCHMIEDER = 3.912
_AEROSOL_REFERENCE_WAVELENGTH_UM = 0.550
_AEROSOL_SCALE_HEIGHT_KM = 1.2

# Angstrom exponent and single-scattering albedo per aerosol type
# (Shettle & Fenn 1979 typical values; the same literature source
# RADIANT_Atmosphere.md cites for SimpleAtmosphere's aerosol table).
_AEROSOL_TABLE: dict[str, dict[str, float]] = {
    "rural": {"angstrom": 1.3, "ssa": 0.95},
    "urban": {"angstrom": 1.5, "ssa": 0.85},
    "maritime": {"angstrom": 0.7, "ssa": 0.99},
    "tropospheric": {"angstrom": 1.5, "ssa": 0.95},
    "none": {"angstrom": 1.3, "ssa": 0.95},
}

_SOLAR_DISK_TEMPERATURE_K = 5778.0
_SOLAR_RADIUS_M = 6.957e8
_AU_M = 1.495978707e11


def aerosol_column_fraction(z_lo_km: float, z_hi_km: float) -> float:
    """Fraction of the total vertical aerosol column inside [z_lo_km, z_hi_km].

    Aerosol follows the same exponential scale-height profile as
    ``aerosol_vertical_optical_depth`` assumes (1.2 km) -- a linear
    altitude fraction would badly misrepresent a partial column (e.g.
    0-35 km captures ~100% of the aerosol, not 35%, since the aerosol
    is concentrated in the lowest ~1-2 km).
    """
    frac_below_hi = 1.0 - math.exp(-max(z_hi_km, 0.0) / _AEROSOL_SCALE_HEIGHT_KM)
    frac_below_lo = 1.0 - math.exp(-max(z_lo_km, 0.0) / _AEROSOL_SCALE_HEIGHT_KM)
    return max(0.0, frac_below_hi - frac_below_lo)


def aerosol_vertical_optical_depth(
    wavenumber_cm1: np.ndarray, aerosol: str, visibility_km: float
) -> np.ndarray:
    """Vertical (nadir) aerosol optical depth via Koschmieder + Angstrom law."""
    if aerosol == "none" or visibility_km <= 0.0:
        return np.zeros_like(wavenumber_cm1)
    alpha = _AEROSOL_TABLE[aerosol]["angstrom"]
    sigma_550_km1 = _KOSCHMIEDER / visibility_km
    tau_vertical_550 = sigma_550_km1 * _AEROSOL_SCALE_HEIGHT_KM
    wavelength_um = 1.0e4 / np.maximum(wavenumber_cm1, 1e-9)
    return tau_vertical_550 * (wavelength_um / _AEROSOL_REFERENCE_WAVELENGTH_UM) ** (-alpha)


def toa_solar_irradiance_blackbody_W_cm2_cm1(wavenumber_cm1: np.ndarray) -> np.ndarray:
    """Crude Planck-disk approximation of TOA solar spectral irradiance.

    A 5778 K blackbody disk of the sun's true angular size at 1 AU --
    a standard textbook approximation, not the measured/Kurucz solar
    spectrum RADIANT's own radiant.core.solar module uses. Deliberately
    self-contained (this script does not import radiant internals) and
    adequate for a single-scatter ORDER-OF-MAGNITUDE estimate; not
    intended to be radiometrically precise.
    """
    solid_angle_sun = math.pi * (_SOLAR_RADIUS_M / _AU_M) ** 2
    surface_radiance = planck_radiance_W_cm2_sr_cm1(wavenumber_cm1, _SOLAR_DISK_TEMPERATURE_K)
    return surface_radiance * solid_angle_sun


def single_scatter_path_radiance_W_cm2_sr_cm1(
    wavenumber_cm1: np.ndarray,
    aerosol: str,
    visibility_km: float,
    tau_aerosol_slant: np.ndarray,
    tau_total_slant: np.ndarray,
    solar_zenith_rad: float,
) -> np.ndarray:
    """Crude single-scatter estimate for the tape7 SOL SCAT column.

    Not multiple-scattering DISORT -- see module docstring. Zero for
    aerosol='none' or when the sun is below the horizon.
    """
    if aerosol == "none" or visibility_km <= 0.0 or solar_zenith_rad >= math.pi / 2.0:
        return np.zeros_like(wavenumber_cm1)
    ssa = _AEROSOL_TABLE[aerosol]["ssa"]
    e_toa = toa_solar_irradiance_blackbody_W_cm2_cm1(wavenumber_cm1)
    # Isotropic-phase-function single-scatter approximation: fraction
    # tau_aerosol_slant of the beam is scattered, ssa of that survives
    # absorption, spread over 4*pi sr, attenuated by the two-way
    # transmittance to the sensor.
    scattered_fraction = 1.0 - np.exp(-np.clip(tau_aerosol_slant, 0.0, 50.0))
    return (
        e_toa
        * scattered_fraction
        * ssa
        / (4.0 * math.pi)
        * np.exp(-np.clip(tau_total_slant, 0.0, 50.0))
    )
