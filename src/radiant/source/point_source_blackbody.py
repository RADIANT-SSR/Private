"""Blackbody intensity point source.

``I(λ) = A · ε · B(λ, T)`` for a heated emitter.

See RADIANT_Source_Target_System.md §3.6 and §6 Path 4.
See also ``point_source_direct.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from radiant.core.blackbody import planck_spectral_radiance


@dataclass(frozen=True)
class BlackbodyIntensitySource:
    """Point source from a heated emitter: ``I(λ) = A · ε · B(λ, T)``.

    Parameters
    ----------
    temperature_K:
        Emitter temperature [K]. Must be > 0.
    projected_area_m2:
        Projected emitting area [m²]. Must be > 0.
    emissivity:
        Scalar emissivity ∈ [0, 1]. Default 1.0.
    name:
        Human-readable label.
    """

    temperature_K: float
    projected_area_m2: float
    emissivity: float = 1.0
    name: str = "blackbody_intensity"
    _tag: str = field(default="point_source", init=False, repr=False)

    def __post_init__(self) -> None:
        if self.temperature_K <= 0.0:
            raise ValueError(
                f"BlackbodyIntensitySource '{self.name}': temperature_K "
                f"must be > 0, got {self.temperature_K}"
            )
        if self.projected_area_m2 <= 0.0:
            raise ValueError(
                f"BlackbodyIntensitySource '{self.name}': "
                f"projected_area_m2 must be > 0, got {self.projected_area_m2}"
            )
        if not (0.0 <= self.emissivity <= 1.0):
            raise ValueError(
                f"BlackbodyIntensitySource '{self.name}': emissivity must "
                f"be in [0, 1], got {self.emissivity}"
            )

    def spectral_intensity(
        self, wavelength_um: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """Return I(λ) = A · ε · B(λ, T) [W/sr/µm].

        Parameters
        ----------
        wavelength_um:
            1-D ascending wavelength grid [µm].

        Returns
        -------
        ndarray
            Spectral intensity [W/sr/µm].
        """
        lam = np.asarray(wavelength_um, dtype=np.float64)
        B = planck_spectral_radiance(lam, self.temperature_K)
        return np.asarray(
            self.projected_area_m2 * self.emissivity * B,
            dtype=np.float64,
        )

    def spectral_radiance(
        self, wavelength_um: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """Return equivalent radiance L = I / A [W/m²/sr/µm].

        For a BlackbodyIntensitySource this simplifies to ``ε · B(λ, T)``.
        """
        lam = np.asarray(wavelength_um, dtype=np.float64)
        B = planck_spectral_radiance(lam, self.temperature_K)
        return np.asarray(self.emissivity * B, dtype=np.float64)
