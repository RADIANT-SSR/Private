"""Blackbody background source.

``L_bg(λ) = ε · B(λ, T)``

Per RADIANT_Source_Target_System.md §3.7, the "no background" case is
``BlackbodyBackground(T=2.7, emissivity=1.0)`` (CMB), not ``None``.

See also ``background_tabulated.py`` and ``background_constant.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt

from radiant.core.blackbody import planck_spectral_radiance


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

    def spectral_radiance(self, wavelength_um: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
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


# Default background: CMB at 2.7 K.
CMB_BACKGROUND = BlackbodyBackground(temperature_K=2.7, emissivity=1.0, name="cmb")
