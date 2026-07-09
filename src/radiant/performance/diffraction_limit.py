"""Diffraction-limited resolution — the optics-only resolution floor.

The Rayleigh criterion sets the smallest angle an unobstructed circular
aperture can resolve:

    θ_Rayleigh = 1.22 · λ / D          [rad]

Projected to the ground at a slant range R (nadir or off-nadir):

    d_ground = θ_Rayleigh · R           [m]

This is the optics-only resolution floor — the companion to the
detector-sampled GSD. When the diffraction ground spot exceeds the GSD the
image is diffraction- (optics-) limited; when smaller, detector-limited
(see :mod:`radiant.performance.sampling_regime`).

Gap 49 (Phase T4): scenario 1.2 computed this locally to draw the
diffraction constraint line; it belongs in the result metrics next to
``gsd_geometric_mean_m``.
"""

from __future__ import annotations

from radiant.core.exceptions import RadiantError

__all__ = [
    "DiffractionLimitError",
    "diffraction_limited_angular_rad",
    "diffraction_limited_ground_m",
]

_RAYLEIGH = 1.22


class DiffractionLimitError(RadiantError):
    """Raised for out-of-range diffraction-limit inputs."""


def diffraction_limited_angular_rad(wavelength_m: float, aperture_m: float) -> float:
    """Rayleigh angular resolution ``1.22 · λ / D`` [rad]."""
    if wavelength_m <= 0.0:
        raise DiffractionLimitError(f"wavelength_m must be positive, got {wavelength_m}.")
    if aperture_m <= 0.0:
        raise DiffractionLimitError(f"aperture_m must be positive, got {aperture_m}.")
    return _RAYLEIGH * wavelength_m / aperture_m


def diffraction_limited_ground_m(wavelength_m: float, aperture_m: float, range_m: float) -> float:
    """Rayleigh resolution projected to the ground ``θ · R`` [m]."""
    if range_m <= 0.0:
        raise DiffractionLimitError(f"range_m must be positive, got {range_m}.")
    return diffraction_limited_angular_rad(wavelength_m, aperture_m) * range_m
