"""Unit conversion system.

Conversions happen exactly once: on input (to canonical) and on output
(from canonical). No module may perform ad-hoc unit conversions.

Canonical units are defined in RADIANT_Conventions.md:
  Length: m          Angle: rad        Time: s
  Radiance: W/m²/sr/µm                Temperature: K
  Signal: e-         Noise: e- RMS
"""

import math

from radiant.core.constants import c, h

# (from_unit, to_unit) -> multiplicative factor
_CONVERSIONS: dict[tuple[str, str], float] = {
    # Length
    ("m", "m"): 1.0,
    ("cm", "m"): 1e-2,
    ("mm", "m"): 1e-3,
    ("um", "m"): 1e-6,
    ("nm", "m"): 1e-9,
    ("km", "m"): 1e3,
    # Angle
    ("rad", "rad"): 1.0,
    ("deg", "rad"): math.pi / 180.0,
    ("urad", "rad"): 1e-6,
    ("mrad", "rad"): 1e-3,  # accepted on input even though mrad is discouraged
    ("arcmin", "rad"): math.pi / 10800.0,
    ("arcsec", "rad"): math.pi / 648000.0,
    # Time
    ("s", "s"): 1.0,
    ("ms", "s"): 1e-3,
    ("us", "s"): 1e-6,
    # Frequency
    ("Hz", "Hz"): 1.0,
    # Temperature
    ("K", "K"): 1.0,
    # Spectral
    ("um", "um"): 1.0,
    ("nm", "um"): 1e-3,
    # Signal
    ("e-", "e-"): 1.0,
    ("e-/s", "e-/s"): 1.0,
    ("e-/s/pixel", "e-/s/pixel"): 1.0,
    # Dimensionless
    ("", ""): 1.0,
    # Dose
    ("krad", "krad"): 1.0,
    # Area
    ("m2", "m2"): 1.0,
    # Velocity
    ("m/s", "m/s"): 1.0,
    ("km/s", "m/s"): 1e3,
    # Irradiance
    ("W/m2/um", "W/m2/um"): 1.0,
    ("W/cm2/um", "W/m2/um"): 1e4,
    # Radiance
    ("W/m2/sr/um", "W/m2/sr/um"): 1.0,
    ("W/cm2/sr/um", "W/m2/sr/um"): 1e4,
}


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a value from one unit to another.

    Raises KeyError if the conversion is not registered.
    """
    if from_unit == to_unit:
        return value
    key = (from_unit, to_unit)
    if key not in _CONVERSIONS:
        raise KeyError(
            f"No conversion registered from '{from_unit}' to '{to_unit}'. "
            f"Register it in radiant.core.units._CONVERSIONS."
        )
    return value * _CONVERSIONS[key]


def inverse_convert(value: float, canonical_unit: str, display_unit: str) -> float:
    """Convert from canonical unit back to display unit for output."""
    if canonical_unit == display_unit:
        return value
    # Use the inverse of the forward conversion
    forward_key = (display_unit, canonical_unit)
    if forward_key not in _CONVERSIONS:
        raise KeyError(f"No conversion registered from '{display_unit}' to '{canonical_unit}'.")
    return value / _CONVERSIONS[forward_key]


def wavelength_to_wavenumber(lam_um: float) -> float:
    """Convert wavelength to wavenumber.

    Args:
        lam_um: Wavelength [µm]. Must be > 0.

    Returns:
        Wavenumber [cm⁻¹] = 10000 / lam_um.

    Raises:
        ValueError: If lam_um <= 0.
    """
    if lam_um <= 0.0:
        raise ValueError(f"wavelength must be > 0, got {lam_um} µm")
    return 10000.0 / lam_um


def wavenumber_to_wavelength(nu_cm: float) -> float:
    """Convert wavenumber to wavelength.

    Args:
        nu_cm: Wavenumber [cm⁻¹]. Must be > 0.

    Returns:
        Wavelength [µm] = 10000 / nu_cm.

    Raises:
        ValueError: If nu_cm <= 0.
    """
    if nu_cm <= 0.0:
        raise ValueError(f"wavenumber must be > 0, got {nu_cm} cm⁻¹")
    return 10000.0 / nu_cm


def photon_energy_J(lam_um: float) -> float:
    """Photon energy at given wavelength.

    Args:
        lam_um: Wavelength [µm]. Must be > 0.

    Returns:
        Photon energy [J] = h*c / (lam_um * 1e-6).

    Raises:
        ValueError: If lam_um <= 0.
    """
    if lam_um <= 0.0:
        raise ValueError(f"wavelength must be > 0, got {lam_um} µm")
    lam_m = lam_um * 1e-6
    return h * c / lam_m


def photon_rate(power_W: float, lam_um: float) -> float:
    """Photon rate for a given optical power at a given wavelength.

    Args:
        power_W: Optical power [W].
        lam_um: Wavelength [µm]. Must be > 0.

    Returns:
        Photon rate [photons/s] = power_W / photon_energy_J(lam_um).

    Raises:
        ValueError: If lam_um <= 0.
    """
    return power_W / photon_energy_J(lam_um)
