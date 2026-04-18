"""Reflected solar spectral radiance source.

Implements ReflectedSolarSource from RADIANT_Source_Target_System.md §3.3:

    L_refl(λ) = BRDF(λ; θ_sun, θ_r) · E_sun(λ) · cos θ_sun

For v1, the Sun is treated as a single directional source (no
hemisphere integration). The BRDF model (Lambertian or Phong) is
evaluated at the specified solar and observer geometry.

See RADIANT_Source_Target_System.md §3.3.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt

from radiant.core.solar import toa_solar_spectral_irradiance
from radiant.source.brdf_lambertian import LambertianBRDF
from radiant.source.brdf_phong import PhongBRDF


@dataclass(frozen=True)
class ReflectedSolarSource:
    """BRDF-weighted reflected solar radiance.

    ``L_refl(λ) = BRDF(λ; θ_sun, θ_obs) · E_sun(λ, d) · cos θ_sun``

    Parameters
    ----------
    brdf:
        BRDF model (LambertianBRDF or PhongBRDF).
    solar_zenith_rad:
        Solar zenith angle [rad]. Must be in [0, π/2].
        At π/2 the Sun is on the horizon; reflected radiance → 0.
    observer_zenith_rad:
        Observer zenith angle [rad]. Must be in [0, π/2].
    distance_au:
        Sun–target distance in AU. Default 1.0 (Earth).
    solar_model:
        Solar spectrum model. Default ``"blackbody_5778"``.
    name:
        Human-readable label.
    """

    brdf: LambertianBRDF | PhongBRDF
    solar_zenith_rad: float
    observer_zenith_rad: float = 0.0
    distance_au: float = 1.0
    solar_model: str = "blackbody_5778"
    name: str = "reflected_solar"
    _tag: str = field(default="reflected", init=False, repr=False)

    def __post_init__(self) -> None:
        if self.solar_zenith_rad < 0.0 or self.solar_zenith_rad > math.pi / 2.0:
            raise ValueError(
                f"ReflectedSolarSource '{self.name}': solar_zenith_rad must "
                f"be in [0, π/2], got {self.solar_zenith_rad}"
            )
        if self.observer_zenith_rad < 0.0 or self.observer_zenith_rad > math.pi / 2.0:
            raise ValueError(
                f"ReflectedSolarSource '{self.name}': observer_zenith_rad "
                f"must be in [0, π/2], got {self.observer_zenith_rad}"
            )
        if self.distance_au <= 0.0:
            raise ValueError(
                f"ReflectedSolarSource '{self.name}': distance_au must be "
                f"positive, got {self.distance_au}"
            )

    def spectral_radiance(
        self, wavelength_um: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """Return reflected solar radiance L_refl(λ) [W/m²/sr/µm].

        Parameters
        ----------
        wavelength_um:
            1-D ascending wavelength grid [µm].

        Returns
        -------
        ndarray
            Spectral radiance [W/m²/sr/µm]. Returns zeros if the Sun
            is exactly at the horizon (cos θ_sun = 0).
        """
        lam = np.asarray(wavelength_um, dtype=np.float64)

        cos_sun = math.cos(self.solar_zenith_rad)
        if cos_sun <= 0.0:
            return np.zeros(len(lam), dtype=np.float64)

        # Solar irradiance at target distance.
        e_sun = toa_solar_spectral_irradiance(lam, model=self.solar_model)
        scale = (1.0 / self.distance_au) ** 2
        e_sun_scaled = e_sun * scale

        # BRDF evaluation.
        brdf_vals = self.brdf.evaluate(
            lam,
            theta_sun_rad=self.solar_zenith_rad,
            theta_obs_rad=self.observer_zenith_rad,
        )

        return np.asarray(brdf_vals * e_sun_scaled * cos_sun, dtype=np.float64)
