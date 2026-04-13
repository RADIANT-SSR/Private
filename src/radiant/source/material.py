"""Surface material with Kirchhoff-consistent optical properties.

Implements SurfaceMaterial per RADIANT_Source_Target_System.md §4.
Kirchhoff's law (ε + ρ = 1 for opaque surfaces) is enforced: reflectance
is always derived from emissivity, never accepted as an independent input.

See also CLAUDE.md Rule 5.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.source.combined import CombinedSource
from radiant.source.emitted import ThermalSource


@dataclass(frozen=True)
class SurfaceMaterial:
    """Optical and thermal properties of an opaque surface.

    Reflectance is derived via Kirchhoff: ``ρ = 1 − ε``.

    Parameters
    ----------
    name:
        Human-readable identifier.
    temperature_K:
        Surface temperature [K]. Must be ≥ 0.
    emissivity:
        Scalar (graybody) or 1-D array of ε(λ) ∈ [0, 1].
    brdf_model:
        BRDF type: ``"lambertian"`` or ``"phong"``.
    phong_exponent:
        Phong specular exponent (only if brdf_model="phong").
    specular_fraction:
        Fraction of reflectance in specular lobe (only for Phong).
    """

    name: str
    temperature_K: float
    emissivity: float | npt.NDArray[np.float64]
    brdf_model: str = "lambertian"
    phong_exponent: float = 10.0
    specular_fraction: float = 0.0

    def __post_init__(self) -> None:
        if self.temperature_K < 0.0:
            raise ValueError(
                f"SurfaceMaterial '{self.name}': temperature_K must be "
                f">= 0, got {self.temperature_K}"
            )
        eps = np.atleast_1d(np.asarray(self.emissivity, dtype=np.float64))
        if np.any(eps < 0.0) or np.any(eps > 1.0):
            raise ValueError(
                f"SurfaceMaterial '{self.name}': emissivity must be in "
                f"[0, 1], got min={float(eps.min())}, max={float(eps.max())}"
            )
        if self.brdf_model not in ("lambertian", "phong"):
            raise ValueError(
                f"SurfaceMaterial '{self.name}': brdf_model must be "
                f"'lambertian' or 'phong', got '{self.brdf_model}'"
            )
        if not (0.0 <= self.specular_fraction <= 1.0):
            raise ValueError(
                f"SurfaceMaterial '{self.name}': specular_fraction must be "
                f"in [0, 1], got {self.specular_fraction}"
            )
        if self.phong_exponent < 0.0:
            raise ValueError(
                f"SurfaceMaterial '{self.name}': phong_exponent must be "
                f">= 0, got {self.phong_exponent}"
            )

    @property
    def reflectance(self) -> float | npt.NDArray[np.float64]:
        """Derived reflectance: ρ = 1 − ε (Kirchhoff)."""
        return 1.0 - np.asarray(self.emissivity, dtype=np.float64)

    @classmethod
    def graybody(
        cls,
        name: str,
        temperature_K: float,
        emissivity: float,
        brdf_model: str = "lambertian",
    ) -> SurfaceMaterial:
        """Convenience constructor for a spectrally flat (graybody) surface."""
        return cls(
            name=name,
            temperature_K=temperature_K,
            emissivity=emissivity,
            brdf_model=brdf_model,
        )

    def create_source(
        self,
        solar_zenith_rad: float | None = None,
        observer_zenith_rad: float = 0.0,
        distance_au: float = 1.0,
    ) -> ThermalSource | CombinedSource:
        """Create the appropriate source from this material's properties.

        Parameters
        ----------
        solar_zenith_rad:
            If provided, creates a CombinedSource (thermal + reflected).
            If None, creates a thermal-only ThermalSource.
        observer_zenith_rad:
            Observer zenith angle [rad]. Only used if solar_zenith_rad
            is not None.
        distance_au:
            Sun–target distance [AU]. Only used if solar_zenith_rad
            is not None.

        Returns
        -------
        ThermalSource or CombinedSource
        """
        if solar_zenith_rad is None:
            return ThermalSource(
                temperature_K=self.temperature_K,
                emissivity=self.emissivity,
            )
        return CombinedSource(
            temperature_K=self.temperature_K,
            emissivity=self.emissivity,
            solar_zenith_rad=solar_zenith_rad,
            observer_zenith_rad=observer_zenith_rad,
            brdf_model=self.brdf_model,
            phong_exponent=self.phong_exponent,
            specular_fraction=self.specular_fraction,
            distance_au=distance_au,
        )

    def verify_kirchhoff(self) -> bool:
        """Return True if ε + ρ = 1 (always True by construction)."""
        eps = np.atleast_1d(np.asarray(self.emissivity, dtype=np.float64))
        rho = np.atleast_1d(np.asarray(self.reflectance, dtype=np.float64))
        return bool(np.allclose(eps + rho, 1.0, atol=1e-15))
