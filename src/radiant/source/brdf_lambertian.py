"""Lambertian BRDF model.

``BRDF(λ) = ρ(λ) / π``

The simplest physical BRDF: isotropic diffuse scatter. Energy-conserving
by construction since ``∫ (ρ/π) cos θ dΩ = ρ`` over the hemisphere.

See RADIANT_Source_Target_System.md §3.3 and §4.
See also ``brdf_phong.py``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class LambertianBRDF:
    """Isotropic diffuse BRDF: ``BRDF(λ) = ρ(λ) / π``.

    Parameters
    ----------
    reflectance:
        Hemispherical reflectance ρ ∈ [0, 1]. Scalar (spectrally flat)
        or 1-D array matching the wavelength grid.
    """

    reflectance: float | npt.NDArray[np.float64]

    def __post_init__(self) -> None:
        rho = np.atleast_1d(np.asarray(self.reflectance, dtype=np.float64))
        if np.any(rho < 0.0) or np.any(rho > 1.0):
            raise ValueError(
                f"LambertianBRDF: reflectance must be in [0, 1], "
                f"got min={float(rho.min())}, max={float(rho.max())}"
            )

    def evaluate(
        self,
        wavelength_um: npt.NDArray[np.float64],
        theta_sun_rad: float = 0.0,
        theta_obs_rad: float = 0.0,
    ) -> npt.NDArray[np.float64]:
        """Evaluate BRDF [sr⁻¹] on the wavelength grid.

        For Lambertian, the result is angle-independent: ``ρ(λ) / π``.

        Parameters
        ----------
        wavelength_um:
            Wavelength grid [µm]. Used only for shape when reflectance
            is scalar.
        theta_sun_rad:
            Solar zenith angle [rad]. Unused for Lambertian.
        theta_obs_rad:
            Observer zenith angle [rad]. Unused for Lambertian.

        Returns
        -------
        ndarray
            BRDF values in sr⁻¹, same length as ``wavelength_um``.
        """
        n = len(wavelength_um)
        rho = np.atleast_1d(np.asarray(self.reflectance, dtype=np.float64))
        if rho.size == 1:
            rho = np.full(n, rho.item(), dtype=np.float64)
        elif rho.size != n:
            raise ValueError(
                f"LambertianBRDF: reflectance array length {rho.size} "
                f"does not match wavelength grid length {n}"
            )
        return np.asarray(rho / math.pi, dtype=np.float64)
