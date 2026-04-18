"""Constant background source.

Flat background radiance across all wavelengths.

See RADIANT_Source_Target_System.md §3.7.
See also ``background_blackbody.py`` and ``background_tabulated.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt


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
