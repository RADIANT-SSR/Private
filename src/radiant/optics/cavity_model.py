"""CavityModel — per-surface cavity physics for refractive optical elements.

Computes system transmittance, system reflectance, and effective
emissivity from surface coatings (R1, T1, R2, T2), bulk absorption
coefficient (alpha), refractive index (n_refr), and substrate
thickness (thickness_m).

All spectral inputs must share the same wavelength grid.
This class contains NO geometry or thermal properties — it is
a pure radiometric computation.

See RADIANT_Optics.md section 6.1.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from radiant.core.spectral import SpectralData
from radiant.optics.element import KirchhoffViolationError

_CAVITY_KIRCHHOFF_TOL: float = 1e-4


@dataclass(frozen=True)
class CavityModel:
    """Per-surface cavity physics for a refractive optical element.

    Computes system transmittance, system reflectance, and effective
    emissivity from surface coatings (R1, T1, R2, T2), bulk absorption
    coefficient (alpha), refractive index (n_refr), and substrate
    thickness (thickness_m).

    All spectral inputs must share the same wavelength grid.
    This class contains NO geometry or thermal properties — it is
    a pure radiometric computation.

    Parameters
    ----------
    R1, T1:
        Entry surface reflectance and transmittance.
    R2, T2:
        Exit surface reflectance and transmittance.
    alpha:
        Bulk absorption coefficient [1/m].
    n_refr:
        Refractive index (dimensionless).
    thickness_m:
        Substrate thickness [m].
    """

    R1: SpectralData
    T1: SpectralData
    R2: SpectralData
    T2: SpectralData
    alpha: SpectralData
    n_refr: SpectralData
    thickness_m: float

    def __post_init__(self) -> None:
        # Validate all share the same wavelength grid.
        ref_wl = self.R1.wavelength_um
        for name, sd in [
            ("T1", self.T1), ("R2", self.R2), ("T2", self.T2),
            ("alpha", self.alpha), ("n_refr", self.n_refr),
        ]:
            if not np.array_equal(sd.wavelength_um, ref_wl):
                raise ValueError(
                    f"CavityModel: '{name}' wavelength grid does not match R1."
                )

        # Surface energy conservation: R + T <= 1 at each surface.
        for label, r_sd, t_sd in [("surface 1", self.R1, self.T1),
                                   ("surface 2", self.R2, self.T2)]:
            total = r_sd.values + t_sd.values
            if np.any(total > 1.0 + _CAVITY_KIRCHHOFF_TOL):
                worst = float(np.max(total))
                raise KirchhoffViolationError(
                    f"CavityModel {label}: R + T = {worst:.6g} > 1. "
                    "Surface energy conservation requires R + T <= 1."
                )

        # Absorption coefficient must be non-negative.
        if np.any(self.alpha.values < 0.0):
            raise ValueError(
                "CavityModel: absorption coefficient alpha must be >= 0 "
                f"(gain is not physical). Min value: {float(self.alpha.values.min()):.6g}."
            )

        # Refractive index must be >= 1.
        if np.any(self.n_refr.values < 1.0):
            raise ValueError(
                "CavityModel: refractive index n must be >= 1. "
                f"Min value: {float(self.n_refr.values.min()):.6g}."
            )

        # Thickness must be non-negative.
        if self.thickness_m < 0.0:
            raise ValueError(
                f"CavityModel: thickness_m must be >= 0, got {self.thickness_m}."
            )

        # Energy conservation: T_sys + R_sys <= 1 (absorptance >= 0).
        t_sys = self.T_sys.values
        r_sys = self.R_sys.values
        total = t_sys + r_sys
        if np.any(total > 1.0 + _CAVITY_KIRCHHOFF_TOL):
            worst = float(np.max(total))
            raise KirchhoffViolationError(
                f"CavityModel: energy violation — T_sys + R_sys = {worst:.6g} > 1. "
                "Check surface coating values."
            )

    @property
    def wavelength_um(self) -> np.ndarray:
        """Wavelength grid shared by all spectral inputs."""
        return self.R1.wavelength_um

    @property
    def beer(self) -> np.ndarray:
        """Beer-Lambert bulk transmission: exp(-alpha * d)."""
        return np.exp(-self.alpha.values * self.thickness_m)

    @property
    def denom(self) -> np.ndarray:
        """Cavity denominator: 1 - R1 * R2 * beer^2."""
        b = self.beer
        return 1.0 - self.R1.values * self.R2.values * b * b

    @property
    def T_sys(self) -> SpectralData:
        """System transmittance: T1 * beer * T2 / denom."""
        b = self.beer
        vals = self.T1.values * b * self.T2.values / self.denom
        return SpectralData(
            name="cavity.T_sys",
            wavelength_um=self.wavelength_um.copy(),
            values=vals,
            unit="",
            source="Cavity model: T1 * beer * T2 / denom",
        )

    @property
    def R_sys(self) -> SpectralData:
        """System reflectance: R1 + T1^2 * R2 * beer^2 / denom."""
        b = self.beer
        vals = self.R1.values + (
            self.T1.values ** 2 * self.R2.values * b * b / self.denom
        )
        return SpectralData(
            name="cavity.R_sys",
            wavelength_um=self.wavelength_um.copy(),
            values=vals,
            unit="",
            source="Cavity model: R1 + T1^2 * R2 * beer^2 / denom",
        )

    @property
    def eps_eff(self) -> SpectralData:
        """Effective cavity emissivity: T2 * n^2 * (1 - beer) / denom."""
        b = self.beer
        vals = self.T2.values * self.n_refr.values ** 2 * (1.0 - b) / self.denom
        return SpectralData(
            name="cavity.eps_eff",
            wavelength_um=self.wavelength_um.copy(),
            values=vals,
            unit="",
            source="Cavity model: T2 * n^2 * (1 - beer) / denom",
        )
