"""Tabulated background source.

User-provided background radiance L_bg(λ) as a spectral table.

See RADIANT_Source_Target_System.md §3.7.
See also ``background_blackbody.py`` and ``background_constant.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from radiant.core.spectral import SpectralData


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
