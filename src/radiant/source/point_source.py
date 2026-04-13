"""Point source intensity variants.

Implements spectral intensity sources ``I(λ)`` [W/sr/µm] for unresolved
targets per RADIANT_Source_Target_System.md §3.6.

Three variants:
1. ``DirectIntensitySource``: user-provided I(λ) directly.
2. ``BlackbodyIntensitySource``: I(λ) = A · ε(λ) · B(λ, T).

The third variant (IntegratedObjectIntensitySource) requires the
geometry system and will be implemented in 2D.2.

See RADIANT_Source_Target_System.md §3.6 and §6 Path 4.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.spectral import SpectralData


@dataclass(frozen=True)
class DirectIntensitySource:
    """User-provided spectral intensity I(λ) [W/sr/µm].

    Parameters
    ----------
    intensity_data:
        Spectral intensity table [W/sr/µm]. Interpolated onto the
        evaluation wavelength grid.
    name:
        Human-readable label.
    """

    intensity_data: SpectralData
    name: str = "direct_intensity"
    _tag: str = field(default="point_source", init=False, repr=False)

    def __post_init__(self) -> None:
        if np.any(self.intensity_data.values < 0.0):
            raise ValueError(
                f"DirectIntensitySource '{self.name}': intensity values "
                f"must be non-negative (min={float(self.intensity_data.values.min())})"
            )

    def spectral_intensity(
        self, wavelength_um: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """Return I(λ) interpolated onto the requested grid [W/sr/µm].

        Parameters
        ----------
        wavelength_um:
            1-D ascending wavelength grid [µm].

        Returns
        -------
        ndarray
            Spectral intensity [W/sr/µm].

        Raises
        ------
        ValueError
            If wavelengths extend outside the table range.
        """
        lam = np.asarray(wavelength_um, dtype=np.float64)
        src_wl = self.intensity_data.wavelength_um
        if lam[0] < src_wl[0] or lam[-1] > src_wl[-1]:
            raise ValueError(
                f"DirectIntensitySource '{self.name}': requested range "
                f"[{lam[0]:.4f}, {lam[-1]:.4f}] µm outside table "
                f"[{src_wl[0]:.4f}, {src_wl[-1]:.4f}] µm."
            )
        result = np.interp(lam, src_wl, self.intensity_data.values)
        return np.asarray(result, dtype=np.float64)

    def spectral_radiance(
        self,
        wavelength_um: npt.NDArray[np.float64],
        reference_area_m2: float = 1e-12,
    ) -> npt.NDArray[np.float64]:
        """Convert to radiance via reference area [W/m²/sr/µm].

        Per RADIANT_Source_Target_System.md §6 Path 4, the chain
        always has an extended-source representation. For point sources,
        this is ``I / reference_area`` with a small fictitious area.

        Parameters
        ----------
        wavelength_um:
            1-D ascending wavelength grid [µm].
        reference_area_m2:
            Fictitious reference area [m²]. Default 1e-12.
        """
        if reference_area_m2 <= 0.0:
            raise ValueError(
                f"reference_area_m2 must be positive, got {reference_area_m2}"
            )
        I = self.spectral_intensity(wavelength_um)
        return np.asarray(I / reference_area_m2, dtype=np.float64)


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
