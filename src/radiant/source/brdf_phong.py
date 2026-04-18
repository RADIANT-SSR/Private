"""Phong BRDF model.

``BRDF = ρ_d(λ)/π + ρ_s(λ) · (n+2)/(2π) · cos^n(α)``

where ``α`` is the angle between the specular reflection direction and
the observer direction, ``ρ_d + ρ_s = ρ`` (total reflectance), and
``n`` is the Phong exponent (higher = narrower specular lobe).

See RADIANT_Source_Target_System.md §3.3 and §4.
See also ``brdf_lambertian.py``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class PhongBRDF:
    """Phong BRDF: diffuse + specular lobe.

    ``BRDF = ρ_d(λ)/π + ρ_s(λ) · (n+2)/(2π) · cos^n(α)``

    where ``ρ_d + ρ_s = ρ`` (total reflectance) and ``α`` is the angle
    between the specular reflection direction and the observer.

    Parameters
    ----------
    reflectance:
        Total hemispherical reflectance ρ ∈ [0, 1].
    specular_fraction:
        Fraction of reflectance in the specular lobe: ``ρ_s = specular_fraction · ρ``.
        Must be in [0, 1]. Default 0.0 (pure diffuse = Lambertian).
    phong_exponent:
        Specular exponent ``n``. Higher values = narrower highlight.
        Must be ≥ 0. Default 10.
    """

    reflectance: float | npt.NDArray[np.float64]
    specular_fraction: float = 0.0
    phong_exponent: float = 10.0

    def __post_init__(self) -> None:
        rho = np.atleast_1d(np.asarray(self.reflectance, dtype=np.float64))
        if np.any(rho < 0.0) or np.any(rho > 1.0):
            raise ValueError(
                f"PhongBRDF: reflectance must be in [0, 1], "
                f"got min={float(rho.min())}, max={float(rho.max())}"
            )
        if not (0.0 <= self.specular_fraction <= 1.0):
            raise ValueError(
                f"PhongBRDF: specular_fraction must be in [0, 1], "
                f"got {self.specular_fraction}"
            )
        if self.phong_exponent < 0.0:
            raise ValueError(
                f"PhongBRDF: phong_exponent must be >= 0, "
                f"got {self.phong_exponent}"
            )

    def evaluate(
        self,
        wavelength_um: npt.NDArray[np.float64],
        theta_sun_rad: float = 0.0,
        theta_obs_rad: float = 0.0,
    ) -> npt.NDArray[np.float64]:
        """Evaluate Phong BRDF [sr⁻¹] on the wavelength grid.

        Parameters
        ----------
        wavelength_um:
            Wavelength grid [µm].
        theta_sun_rad:
            Solar zenith angle [rad].
        theta_obs_rad:
            Observer zenith angle [rad]. For the specular geometry,
            the reflection angle equals the incidence angle in the
            specular plane.

        Returns
        -------
        ndarray
            BRDF values in sr⁻¹, same length as ``wavelength_um``.
        """
        n_wl = len(wavelength_um)
        rho = np.atleast_1d(np.asarray(self.reflectance, dtype=np.float64))
        if rho.size == 1:
            rho = np.full(n_wl, rho.item(), dtype=np.float64)
        elif rho.size != n_wl:
            raise ValueError(
                f"PhongBRDF: reflectance array length {rho.size} "
                f"does not match wavelength grid length {n_wl}"
            )

        rho_d = rho * (1.0 - self.specular_fraction)
        rho_s = rho * self.specular_fraction

        # Diffuse term: ρ_d / π
        diffuse = rho_d / math.pi

        # Specular term: ρ_s · (n+2)/(2π) · cos^n(α)
        # α = angle between specular reflection direction and observer.
        # In the plane of incidence with azimuthally symmetric geometry:
        # specular reflection angle = theta_sun (mirror of incidence).
        # α = |theta_obs - theta_sun| in the specular plane.
        n = self.phong_exponent
        alpha = abs(theta_obs_rad - theta_sun_rad)
        cos_alpha = max(math.cos(alpha), 0.0)
        specular = rho_s * ((n + 2.0) / (2.0 * math.pi)) * (cos_alpha ** n)

        return np.asarray(diffuse + specular, dtype=np.float64)
