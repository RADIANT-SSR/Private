"""Tabulated radiance source — user-provided L(λ).

Escape hatch for measured radiance, DIRSIG results, or unit test
mocks. No physical model is applied; the user owns the physics.

Per RADIANT_Source_Target_System.md §3.5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt

from radiant.core.spectral import SpectralData
from radiant.source.errors import SourceValidationError


@dataclass(frozen=True)
class TabulatedRadianceSource:
    """User-provided spectral radiance L(λ).

    Parameters
    ----------
    radiance_data:
        Spectral radiance table [W/m²/sr/µm]. Interpolated onto
        the evaluation wavelength grid.
    name:
        Human-readable label.
    """

    radiance_data: SpectralData
    name: str = "tabulated_source"
    _tag: str = field(default="tabulated", init=False, repr=False)

    def __post_init__(self) -> None:
        if np.any(self.radiance_data.values < 0.0):
            raise SourceValidationError(
                f"TabulatedRadianceSource '{self.name}': radiance values "
                f"must be non-negative (min={float(self.radiance_data.values.min())})"
            )

    def spectral_radiance(self, wavelength_um: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Return L(λ) interpolated onto the requested grid [W/m²/sr/µm].

        Parameters
        ----------
        wavelength_um:
            1-D ascending wavelength grid [µm].

        Returns
        -------
        ndarray
            Spectral radiance [W/m²/sr/µm].

        Raises
        ------
        ValueError
            If requested wavelengths extend outside the table range.
        """
        lam = np.asarray(wavelength_um, dtype=np.float64)
        src_wl = self.radiance_data.wavelength_um
        if lam[0] < src_wl[0] or lam[-1] > src_wl[-1]:
            raise SourceValidationError(
                f"TabulatedRadianceSource '{self.name}': requested range "
                f"[{lam[0]:.4f}, {lam[-1]:.4f}] µm extends outside table "
                f"[{src_wl[0]:.4f}, {src_wl[-1]:.4f}] µm."
            )
        result = np.interp(lam, src_wl, self.radiance_data.values)
        return np.asarray(result, dtype=np.float64)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "name": self.name,
            "radiance_data": self.radiance_data.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TabulatedRadianceSource:
        """Deserialize from dict."""
        return cls(
            radiance_data=SpectralData.from_dict(d["radiance_data"]),
            name=str(d.get("name", "tabulated_source")),
        )
