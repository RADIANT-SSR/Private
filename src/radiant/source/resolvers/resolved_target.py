"""ResolvedTarget — unified output of all five target input paths.

The signal chain consumes ``ResolvedTarget`` and never inspects how
it was built.  Each of the five factory functions (in separate files)
produces a ``ResolvedTarget`` with the same frozen interface.

See RADIANT_Source_Target_System.md §2 and §6.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.core.regime import RadiometricRegime, TargetInputPath
from radiant.source.material import SurfaceMaterial
from radiant.source.protocol import SpectralRadianceSource
from radiant.source.shape import TargetShape


@dataclass(frozen=True)
class ResolvedTarget:
    """Everything the chain needs to know about a target.

    Produced by exactly one of the five input paths. Immutable.
    The chain consumes this and never inspects how it was built.

    Attributes
    ----------
    name:
        Human-readable target label.
    input_path:
        Which of the 5 paths produced this.
    derivation_chain:
        Human-readable sequence of build steps.
    radiance_source:
        Produces L(λ) [W/m²/sr/µm] — the target surface radiance.
    background_source:
        Produces L_bg(λ) [W/m²/sr/µm].
    projected_area_m2:
        Area facing observer [m²]. 0 for pure point sources.
    angular_extent_rad:
        √(projected_area) / range [rad].
    range_m:
        Observer → target distance [m].
    tentative_regime:
        POINT_SOURCE, SUB_PIXEL, or EXTENDED. Finalized in OpticsStage.
    regime_override:
        If set, forces regime classification. None = auto.
    shapes:
        Preserved geometry (Paths 2 and 5 only).
    materials:
        Preserved materials (Paths 2 and 5 only).
    """

    name: str
    input_path: TargetInputPath
    derivation_chain: tuple[str, ...]

    radiance_source: SpectralRadianceSource
    background_source: SpectralRadianceSource

    projected_area_m2: float
    angular_extent_rad: float
    range_m: float

    tentative_regime: RadiometricRegime
    regime_override: RadiometricRegime | None = None

    shapes: tuple[TargetShape, ...] | None = None
    materials: tuple[SurfaceMaterial, ...] | None = None

    def spectral_radiance(self, wavelength_um: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Target surface spectral radiance [W/m²/sr/µm]."""
        return self.radiance_source.spectral_radiance(wavelength_um)

    def spectral_intensity(self, wavelength_um: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Target spectral intensity [W/sr/µm] = L(λ) × A_proj."""
        return self.radiance_source.spectral_radiance(wavelength_um) * self.projected_area_m2

    def background_radiance(
        self, wavelength_um: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """Background spectral radiance [W/m²/sr/µm]."""
        return self.background_source.spectral_radiance(wavelength_um)


# ---------------------------------------------------------------------------
# Shared helpers used by all resolver functions
# ---------------------------------------------------------------------------


def angular_extent(projected_area_m2: float, range_m: float) -> float:
    """√(A_proj) / range [rad]."""
    if projected_area_m2 <= 0.0:
        return 0.0
    return math.sqrt(projected_area_m2) / range_m


def validate_range(range_m: float) -> None:
    """Raise ValueError if range_m is not positive."""
    if range_m <= 0.0:
        raise ValueError(
            f"range_m must be positive, got {range_m}. Distance from observer to target in meters."
        )


def validate_area(projected_area_m2: float) -> None:
    """Raise ValueError if projected_area_m2 is negative."""
    if projected_area_m2 < 0.0:
        raise ValueError(f"projected_area_m2 must be >= 0, got {projected_area_m2}")
