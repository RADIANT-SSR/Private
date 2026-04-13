"""Background source types.

Backgrounds produce ``L_bg(λ)`` which:
- Adds to in-pixel radiance for sub-pixel and point-source regimes
- Drives background photon shot noise in all regimes
- Sets the contrast reference for detection metrics

Per RADIANT_Source_Target_System.md §3.7, the "no background" case is
``BlackbodyBackground(T=2.7, emissivity=1.0)`` (CMB), not ``None``.

See RADIANT_Source_Target_System.md §3.7.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.spectral import SpectralData


@dataclass(frozen=True)
class BlackbodyBackground:
    """Background at temperature T with optional emissivity.

    ``L_bg(λ) = ε · B(λ, T)``

    Parameters
    ----------
    temperature_K:
        Background temperature [K]. Must be ≥ 0.
    emissivity:
        Scalar emissivity ∈ [0, 1]. Default 1.0 (perfect blackbody).
    name:
        Human-readable label.
    """

    temperature_K: float
    emissivity: float = 1.0
    name: str = "blackbody_background"
    _tag: str = field(default="background", init=False, repr=False)

    def __post_init__(self) -> None:
        if self.temperature_K < 0.0:
            raise ValueError(
                f"BlackbodyBackground '{self.name}': temperature_K must be "
                f">= 0, got {self.temperature_K}"
            )
        if not (0.0 <= self.emissivity <= 1.0):
            raise ValueError(
                f"BlackbodyBackground '{self.name}': emissivity must be in "
                f"[0, 1], got {self.emissivity}"
            )

    def spectral_radiance(
        self, wavelength_um: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """Return ``ε · B(λ, T)`` [W/m²/sr/µm]."""
        lam = np.asarray(wavelength_um, dtype=np.float64)
        B = planck_spectral_radiance(lam, self.temperature_K)
        return np.asarray(self.emissivity * B, dtype=np.float64)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "blackbody",
            "name": self.name,
            "temperature_K": self.temperature_K,
            "emissivity": self.emissivity,
        }


@dataclass(frozen=True)
class TabulatedBackground:
    """User-provided background radiance L_bg(λ).

    Parameters
    ----------
    radiance_data:
        Spectral radiance table [W/m²/sr/µm].
    name:
        Human-readable label.
    """

    radiance_data: SpectralData
    name: str = "tabulated_background"
    _tag: str = field(default="background", init=False, repr=False)

    def __post_init__(self) -> None:
        if np.any(self.radiance_data.values < 0.0):
            raise ValueError(
                f"TabulatedBackground '{self.name}': radiance values "
                f"must be non-negative (min={float(self.radiance_data.values.min())})"
            )

    def spectral_radiance(
        self, wavelength_um: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """Return L_bg(λ) interpolated onto requested grid [W/m²/sr/µm]."""
        lam = np.asarray(wavelength_um, dtype=np.float64)
        src_wl = self.radiance_data.wavelength_um
        if lam[0] < src_wl[0] or lam[-1] > src_wl[-1]:
            raise ValueError(
                f"TabulatedBackground '{self.name}': requested range "
                f"[{lam[0]:.4f}, {lam[-1]:.4f}] µm outside table "
                f"[{src_wl[0]:.4f}, {src_wl[-1]:.4f}] µm."
            )
        result = np.interp(lam, src_wl, self.radiance_data.values)
        return np.asarray(result, dtype=np.float64)


@dataclass(frozen=True)
class ConstantBackground:
    """Flat background radiance across all wavelengths.

    Parameters
    ----------
    radiance_W_m2_sr_um:
        Constant spectral radiance [W/m²/sr/µm]. Must be ≥ 0.
    name:
        Human-readable label.
    """

    radiance_W_m2_sr_um: float
    name: str = "constant_background"
    _tag: str = field(default="background", init=False, repr=False)

    def __post_init__(self) -> None:
        if self.radiance_W_m2_sr_um < 0.0:
            raise ValueError(
                f"ConstantBackground '{self.name}': radiance must be "
                f">= 0, got {self.radiance_W_m2_sr_um}"
            )

    def spectral_radiance(
        self, wavelength_um: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """Return constant L_bg [W/m²/sr/µm]."""
        return np.full(
            len(wavelength_um),
            self.radiance_W_m2_sr_um,
            dtype=np.float64,
        )


# Default background: CMB at 2.7 K.
CMB_BACKGROUND = BlackbodyBackground(temperature_K=2.7, emissivity=1.0, name="cmb")
