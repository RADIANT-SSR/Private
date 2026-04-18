"""Kirchhoff-consistent combined source (thermal + reflected solar).

Implements CombinedSource from RADIANT_Source_Target_System.md §3.4:

    L_total(λ) = ε(λ) · B(λ, T) + (1 − ε(λ)) · BRDF_norm(λ; geom) · E_sun(λ) · cos θ_sun

Enforces Kirchhoff's law: ``ε(λ) + ρ(λ) = 1`` at every wavelength for
opaque surfaces. The reflectance is derived from emissivity; no
independent reflectance input is accepted (per Rule 5 in CLAUDE.md —
emissivity of scene targets IS a legitimate independent parameter, but
for CombinedSource, reflectance is derived, not specified independently).

See RADIANT_Source_Target_System.md §3.4.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.solar import toa_solar_spectral_irradiance
from radiant.source.brdf_lambertian import LambertianBRDF
from radiant.source.brdf_phong import PhongBRDF


@dataclass(frozen=True)
class CombinedSource:
    """Kirchhoff-consistent thermal emission + reflected solar.

    Parameters
    ----------
    temperature_K:
        Surface temperature [K]. Must be ≥ 0.
    emissivity:
        Spectral emissivity ε ∈ [0, 1]. Scalar (graybody) or 1-D
        array matching the wavelength grid. Reflectance is derived
        as ``ρ = 1 − ε``.
    solar_zenith_rad:
        Solar zenith angle [rad]. In [0, π/2]. At π/2 the reflected
        term is zero (Sun at horizon).
    observer_zenith_rad:
        Observer zenith angle [rad]. In [0, π/2].
    brdf_model:
        BRDF type: ``"lambertian"`` or ``"phong"``. Default Lambertian.
    phong_exponent:
        Phong specular exponent (only used if brdf_model="phong").
    specular_fraction:
        Fraction of reflectance in specular lobe (only for Phong).
    distance_au:
        Sun–target distance [AU]. Default 1.0.
    solar_model:
        Solar spectrum model. Default ``"blackbody_5778"``.
    name:
        Human-readable label.
    """

    temperature_K: float
    emissivity: float | npt.NDArray[np.float64]
    solar_zenith_rad: float
    observer_zenith_rad: float = 0.0
    brdf_model: str = "lambertian"
    phong_exponent: float = 10.0
    specular_fraction: float = 0.0
    distance_au: float = 1.0
    solar_model: str = "blackbody_5778"
    name: str = "combined_source"
    _tag: str = field(default="combined", init=False, repr=False)

    def __post_init__(self) -> None:
        if self.temperature_K < 0.0:
            raise ValueError(
                f"CombinedSource '{self.name}': temperature_K must be "
                f">= 0, got {self.temperature_K}"
            )
        eps = np.atleast_1d(np.asarray(self.emissivity, dtype=np.float64))
        if np.any(eps < 0.0) or np.any(eps > 1.0):
            raise ValueError(
                f"CombinedSource '{self.name}': emissivity must be in "
                f"[0, 1], got min={float(eps.min())}, max={float(eps.max())}"
            )
        if self.solar_zenith_rad < 0.0 or self.solar_zenith_rad > math.pi / 2.0:
            raise ValueError(
                f"CombinedSource '{self.name}': solar_zenith_rad must be "
                f"in [0, π/2], got {self.solar_zenith_rad}"
            )
        if self.observer_zenith_rad < 0.0 or self.observer_zenith_rad > math.pi / 2.0:
            raise ValueError(
                f"CombinedSource '{self.name}': observer_zenith_rad must "
                f"be in [0, π/2], got {self.observer_zenith_rad}"
            )
        if self.brdf_model not in ("lambertian", "phong"):
            raise ValueError(
                f"CombinedSource '{self.name}': brdf_model must be "
                f"'lambertian' or 'phong', got '{self.brdf_model}'"
            )
        if self.distance_au <= 0.0:
            raise ValueError(
                f"CombinedSource '{self.name}': distance_au must be "
                f"positive, got {self.distance_au}"
            )

    def spectral_radiance(
        self, wavelength_um: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """Return Kirchhoff-consistent total radiance [W/m²/sr/µm].

        ``L(λ) = ε(λ)·B(λ,T) + (1-ε(λ))·BRDF_norm·E_sun·cos θ_sun``

        Parameters
        ----------
        wavelength_um:
            1-D ascending wavelength grid [µm].

        Returns
        -------
        ndarray
            Total spectral radiance [W/m²/sr/µm].
        """
        lam = np.asarray(wavelength_um, dtype=np.float64)
        n = len(lam)

        # Emissivity array.
        eps = np.atleast_1d(np.asarray(self.emissivity, dtype=np.float64))
        if eps.size == 1:
            eps = np.full(n, eps.item(), dtype=np.float64)

        # Thermal term: ε(λ) · B(λ, T).
        B = planck_spectral_radiance(lam, self.temperature_K)
        L_thermal = eps * B

        # Reflected term: (1 - ε(λ)) · BRDF_norm · E_sun · cos θ_sun.
        rho = 1.0 - eps  # Kirchhoff: ρ = 1 - ε
        cos_sun = math.cos(self.solar_zenith_rad)

        if cos_sun <= 0.0:
            return np.asarray(L_thermal, dtype=np.float64)

        # Build BRDF from derived reflectance.
        if self.brdf_model == "lambertian":
            brdf = LambertianBRDF(reflectance=rho)
        else:
            brdf = PhongBRDF(
                reflectance=rho,
                specular_fraction=self.specular_fraction,
                phong_exponent=self.phong_exponent,
            )

        brdf_vals = brdf.evaluate(
            lam,
            theta_sun_rad=self.solar_zenith_rad,
            theta_obs_rad=self.observer_zenith_rad,
        )

        # Solar irradiance at target.
        e_sun = toa_solar_spectral_irradiance(lam, model=self.solar_model)
        scale = (1.0 / self.distance_au) ** 2

        L_reflected = brdf_vals * e_sun * scale * cos_sun

        return np.asarray(L_thermal + L_reflected, dtype=np.float64)
