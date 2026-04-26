"""Sub-pixel regime source.

Implements the sub-pixel target model from
RADIANT_Source_Target_System.md §6 Path 3:

    L_pixel(λ) = ff · L_target(λ) + (1 − ff) · L_background(λ)

where ``ff`` is the fill fraction (target area / pixel area).

The chain sees a single equivalent radiance (the in-pixel mean).
The background radiance is preserved separately for the noise budget.

See RADIANT_Source_Target_System.md §6 Path 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from radiant.core.blackbody import planck_spectral_radiance


@dataclass(frozen=True)
class SubPixelSource:
    """Sub-pixel target: fill-fraction-weighted mix of target and background.

    Parameters
    ----------
    fill_fraction:
        Target's fraction of pixel area. Must be in (0, 1].
    target_temperature_K:
        Target surface temperature [K].
    target_emissivity:
        Target emissivity ∈ [0, 1]. Scalar.
    background_temperature_K:
        Background surface temperature [K].
    background_emissivity:
        Background emissivity ∈ [0, 1]. Scalar.
    name:
        Human-readable label.
    """

    fill_fraction: float
    target_temperature_K: float
    target_emissivity: float
    background_temperature_K: float
    background_emissivity: float
    name: str = "sub_pixel_source"
    _tag: str = field(default="sub_pixel", init=False, repr=False)

    def __post_init__(self) -> None:
        if self.fill_fraction <= 0.0 or self.fill_fraction > 1.0:
            raise ValueError(
                f"SubPixelSource '{self.name}': fill_fraction must be in "
                f"(0, 1], got {self.fill_fraction}"
            )
        if self.target_temperature_K < 0.0:
            raise ValueError(
                f"SubPixelSource '{self.name}': target_temperature_K must "
                f"be >= 0, got {self.target_temperature_K}"
            )
        if self.background_temperature_K < 0.0:
            raise ValueError(
                f"SubPixelSource '{self.name}': background_temperature_K "
                f"must be >= 0, got {self.background_temperature_K}"
            )
        if not (0.0 <= self.target_emissivity <= 1.0):
            raise ValueError(
                f"SubPixelSource '{self.name}': target_emissivity must be "
                f"in [0, 1], got {self.target_emissivity}"
            )
        if not (0.0 <= self.background_emissivity <= 1.0):
            raise ValueError(
                f"SubPixelSource '{self.name}': background_emissivity must "
                f"be in [0, 1], got {self.background_emissivity}"
            )

    def target_radiance(self, wavelength_um: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Return target spectral radiance L_target(λ) [W/m²/sr/µm]."""
        lam = np.asarray(wavelength_um, dtype=np.float64)
        B = planck_spectral_radiance(lam, self.target_temperature_K)
        return np.asarray(self.target_emissivity * B, dtype=np.float64)

    def background_radiance(
        self, wavelength_um: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """Return background spectral radiance L_bg(λ) [W/m²/sr/µm]."""
        lam = np.asarray(wavelength_um, dtype=np.float64)
        B = planck_spectral_radiance(lam, self.background_temperature_K)
        return np.asarray(self.background_emissivity * B, dtype=np.float64)

    def spectral_radiance(self, wavelength_um: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Return in-pixel mean radiance [W/m²/sr/µm].

        ``L_pixel = ff · L_target + (1 − ff) · L_background``

        Parameters
        ----------
        wavelength_um:
            1-D ascending wavelength grid [µm].

        Returns
        -------
        ndarray
            In-pixel mean spectral radiance [W/m²/sr/µm].
        """
        L_tgt = self.target_radiance(wavelength_um)
        L_bg = self.background_radiance(wavelength_um)
        ff = self.fill_fraction
        return np.asarray(ff * L_tgt + (1.0 - ff) * L_bg, dtype=np.float64)
