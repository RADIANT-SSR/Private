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
from radiant.core.exceptions import CoreValidationError

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
    ("e-/DN", "e-/DN"): 1.0,  # ADC conversion gain (electrons per digital number)
    # Dimensionless
    ("", ""): 1.0,
    ("%", ""): 1e-2,  # percent → fraction, for unit-aware set() (Gap 6)
    # Time (additional input forms)
    ("min", "s"): 60.0,
    # Temperature offsets are NOT multiplicative; only K is accepted.
    # Dose
    ("krad", "krad"): 1.0,
    # Area
    ("m2", "m2"): 1.0,
    # Velocity
    ("m/s", "m/s"): 1.0,
    ("km/s", "m/s"): 1e3,
    # Angular rate (canonical rad/s — LOS slew, target kinematics)
    ("rad/s", "rad/s"): 1.0,
    ("deg/s", "rad/s"): math.pi / 180.0,
    ("mrad/s", "rad/s"): 1e-3,
    ("urad/s", "rad/s"): 1e-6,
    # Irradiance
    ("W/m2/um", "W/m2/um"): 1.0,
    ("W/cm2/um", "W/m2/um"): 1e4,
    # Radiance
    ("W/m2/sr/um", "W/m2/sr/um"): 1.0,
    ("W/cm2/sr/um", "W/m2/sr/um"): 1e4,
}

# (from_unit, to_unit) -> (scale, offset) for AFFINE conversions: to = from*scale + offset.
# Temperature is the only affine dimension (an offset, not a pure ratio), so it cannot live
# in the multiplicative table above (GUI finding 13 — enter temperatures in K / °C / °F).
# Canonical stays K (RADIANT_Conventions.md); conversion happens only at the boundary
# (Rule 2). ``degC`` / ``degF`` are the ASCII unit tokens (consistent with ``deg`` /
# ``arcmin`` in the multiplicative table; no non-ASCII source literal, Rule 30).
_F_SCALE = 5.0 / 9.0
_AFFINE_CONVERSIONS: dict[tuple[str, str], tuple[float, float]] = {
    ("degC", "K"): (1.0, 273.15),
    ("K", "degC"): (1.0, -273.15),
    ("degF", "K"): (_F_SCALE, 273.15 - 32.0 * _F_SCALE),
    ("K", "degF"): (9.0 / 5.0, 32.0 - 273.15 * 9.0 / 5.0),
}


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a value from one unit to another.

    Raises KeyError if the conversion is not registered.
    """
    if from_unit == to_unit:
        return value
    key = (from_unit, to_unit)
    if key in _CONVERSIONS:
        return value * _CONVERSIONS[key]
    if key in _AFFINE_CONVERSIONS:
        scale, offset = _AFFINE_CONVERSIONS[key]
        return value * scale + offset
    raise KeyError(
        f"No conversion registered from '{from_unit}' to '{to_unit}'. "
        f"Register it in radiant.core.units._CONVERSIONS (or _AFFINE_CONVERSIONS)."
    )


def inverse_convert(value: float, canonical_unit: str, display_unit: str) -> float:
    """Convert from canonical unit back to display unit for output."""
    if canonical_unit == display_unit:
        return value
    # Affine dimensions (temperature) register both directions, so a canonical→display
    # entry exists directly (the multiplicative table only stores display→canonical).
    direct_key = (canonical_unit, display_unit)
    if direct_key in _AFFINE_CONVERSIONS:
        scale, offset = _AFFINE_CONVERSIONS[direct_key]
        return value * scale + offset
    # Multiplicative: invert the registered forward (display→canonical) factor.
    forward_key = (display_unit, canonical_unit)
    if forward_key not in _CONVERSIONS:
        raise KeyError(f"No conversion registered from '{display_unit}' to '{canonical_unit}'.")
    return value / _CONVERSIONS[forward_key]


def units_for(canonical_unit: str) -> tuple[str, ...]:
    """Input units that convert to *canonical_unit* (sorted; includes the canonical).

    The named "units convertible to X" accessor (CU-109) — the display-unit choices
    a GUI/CLI should offer for a parameter whose canonical unit is *canonical_unit*.
    Includes affine (temperature) units. Returns an empty tuple for an unregistered
    canonical unit.
    """
    both = list(_CONVERSIONS) + list(_AFFINE_CONVERSIONS)
    return tuple(sorted({frm for (frm, to) in both if to == canonical_unit}))


def input_units() -> tuple[str, ...]:
    """All recognised (non-empty) input unit strings, sorted."""
    both = list(_CONVERSIONS) + list(_AFFINE_CONVERSIONS)
    return tuple(sorted({frm for (frm, _to) in both if frm}))


def targets_for(from_unit: str) -> tuple[str, ...]:
    """Canonical units *from_unit* converts to, excluding the identity (sorted)."""
    both = list(_CONVERSIONS) + list(_AFFINE_CONVERSIONS)
    return tuple(sorted({to for (frm, to) in both if frm == from_unit and frm != to}))


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
        raise CoreValidationError(f"wavelength must be > 0, got {lam_um} µm")
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
        raise CoreValidationError(f"wavenumber must be > 0, got {nu_cm} cm⁻¹")
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
        raise CoreValidationError(f"wavelength must be > 0, got {lam_um} µm")
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
