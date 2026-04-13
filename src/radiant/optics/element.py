"""OpticalElement — individual optical component with Kirchhoff-enforced emissivity.

Per RADIANT_Optics.md section 6.1, emissivity is NEVER an independent
parameter for optical elements.  It is always derived from Kirchhoff's law:

- Mirrors:  ``epsilon = 1 - R``
- Transmissive:  ``epsilon = 1 - T - R``

Construction validates that ``T + R <= 1 + tolerance`` at every wavelength
and that mirrors have zero transmittance.
"""

from __future__ import annotations

import enum
import logging
import math
from dataclasses import dataclass

import numpy as np

from radiant.core.spectral import SpectralData

logger = logging.getLogger(__name__)

# Tolerance for Kirchhoff energy conservation: T + R <= 1 + KIRCHHOFF_TOL.
KIRCHHOFF_TOL: float = 1e-4


class ElementKind(enum.Enum):
    """Types of optical element in the train."""

    MIRROR = "mirror"
    LENS = "lens"
    WINDOW = "window"
    FILTER = "filter"
    BEAMSPLITTER = "beamsplitter"
    DEWAR_WINDOW = "dewar_window"
    COLD_STOP = "cold_stop"
    LUMPED = "lumped"


class KirchhoffViolationError(ValueError):
    """Raised when an optical element violates Kirchhoff's law."""


@dataclass(frozen=True)
class OpticalElement:
    """A single optical element with Kirchhoff-derived emissivity.

    Parameters
    ----------
    name:
        Human-readable label (e.g. ``"primary_mirror"``).
    kind:
        Element type from :class:`ElementKind`.
    temperature_K:
        Physical temperature of the element in Kelvin.
    transmittance:
        Spectral transmittance ``T(lambda)``; must be zero for mirrors.
    reflectance:
        Spectral reflectance ``R(lambda)``.
    diameter_m:
        Clear aperture diameter of this element in meters.
    distance_to_fpa_m:
        Distance from this element to the focal-plane array in meters.
    n_surfaces:
        Number of optical surfaces (for provenance only).
    """

    name: str
    kind: ElementKind
    temperature_K: float
    transmittance: SpectralData
    reflectance: SpectralData
    diameter_m: float
    distance_to_fpa_m: float
    n_surfaces: int = 1

    def __post_init__(self) -> None:
        # --- Wavelength grid compatibility ---
        if not np.array_equal(self.transmittance.wavelength_um, self.reflectance.wavelength_um):
            raise ValueError(
                f"OpticalElement '{self.name}': transmittance and reflectance "
                "must share the same wavelength grid."
            )

        # --- Value bounds ---
        t_vals = self.transmittance.values
        r_vals = self.reflectance.values

        if np.any(t_vals < 0.0) or np.any(t_vals > 1.0):
            raise ValueError(
                f"OpticalElement '{self.name}': transmittance values must be "
                f"in [0, 1], got range [{float(t_vals.min()):.6g}, "
                f"{float(t_vals.max()):.6g}]."
            )
        if np.any(r_vals < 0.0) or np.any(r_vals > 1.0):
            raise ValueError(
                f"OpticalElement '{self.name}': reflectance values must be "
                f"in [0, 1], got range [{float(r_vals.min()):.6g}, "
                f"{float(r_vals.max()):.6g}]."
            )

        # --- Kirchhoff enforcement ---
        total = t_vals + r_vals
        if np.any(total > 1.0 + KIRCHHOFF_TOL):
            worst = float(np.max(total))
            raise KirchhoffViolationError(
                f"OpticalElement '{self.name}': Kirchhoff violation — "
                f"T + R = {worst:.6g} > 1 at some wavelengths. "
                "Energy conservation requires T + R <= 1."
            )

        # Mirror-specific: transmittance must be zero.
        if self.kind == ElementKind.MIRROR and np.any(t_vals > KIRCHHOFF_TOL):
            raise KirchhoffViolationError(
                f"OpticalElement '{self.name}': mirrors must have zero "
                f"transmittance, but max(T) = {float(t_vals.max()):.6g}. "
                "Use kind=WINDOW or kind=BEAMSPLITTER for partially "
                "transmissive elements."
            )

        # --- Geometry ---
        if self.temperature_K < 0.0:
            raise ValueError(
                f"OpticalElement '{self.name}': temperature_K must be >= 0, "
                f"got {self.temperature_K}."
            )
        if self.diameter_m <= 0.0:
            raise ValueError(
                f"OpticalElement '{self.name}': diameter_m must be > 0, got {self.diameter_m}."
            )
        if self.distance_to_fpa_m <= 0.0:
            raise ValueError(
                f"OpticalElement '{self.name}': distance_to_fpa_m must be > 0, "
                f"got {self.distance_to_fpa_m}."
            )

    # ------------------------------------------------------------------
    # Kirchhoff-derived properties
    # ------------------------------------------------------------------

    @property
    def net_transmittance(self) -> SpectralData:
        """Net throughput of this element along the signal path.

        Mirrors: ``R(lambda)`` (reflection acts as the signal path).
        All others: ``T(lambda)``.
        """
        if self.kind == ElementKind.MIRROR:
            return self.reflectance
        return self.transmittance

    @property
    def emissivity(self) -> SpectralData:
        """Kirchhoff-derived emissivity: ``epsilon = 1 - T - R`` (or ``1 - R`` for mirrors).

        This is NEVER an independent parameter (Rule 5).
        """
        if self.kind == ElementKind.MIRROR:
            eps_vals = 1.0 - self.reflectance.values
        else:
            eps_vals = 1.0 - self.transmittance.values - self.reflectance.values

        return SpectralData(
            name=f"{self.name}.emissivity",
            wavelength_um=self.transmittance.wavelength_um.copy(),
            values=np.clip(eps_vals, 0.0, 1.0),
            unit="",
            source=f"Kirchhoff: 1 - T - R ({self.name})",
        )

    @property
    def nearfield_solid_angle_sr(self) -> float:
        """Solid angle subtended by this element as seen from the FPA [sr].

        ``Omega = pi * (D/2)^2 / d^2``, clipped at ``2*pi`` (half-space).
        """
        omega = math.pi * (self.diameter_m / 2.0) ** 2 / self.distance_to_fpa_m**2
        if omega > 2.0 * math.pi:
            logger.warning(
                "OpticalElement '%s': computed solid angle %.4g sr exceeds "
                "2*pi; clipping to 2*pi. Element fills the half-space; "
                "nearfield estimate is approximate.",
                self.name,
                omega,
            )
            return 2.0 * math.pi
        return omega


# ------------------------------------------------------------------
# Factory helpers
# ------------------------------------------------------------------


def make_lumped_element(
    transmission: SpectralData,
    temperature_K: float,
    diameter_m: float,
    distance_to_fpa_m: float,
    name: str = "lumped",
) -> OpticalElement:
    """Create a LUMPED element with the given transmission and zero reflectance.

    Emissivity is derived as ``1 - T`` via Kirchhoff (no reflectance term).
    This is the canonical way to synthesize a virtual element for Modes 1-4.
    """
    zero_reflectance = SpectralData(
        name=f"{name}.reflectance",
        wavelength_um=transmission.wavelength_um.copy(),
        values=np.zeros_like(transmission.values),
        unit="",
        source=f"Lumped element zero reflectance ({name})",
    )
    return OpticalElement(
        name=name,
        kind=ElementKind.LUMPED,
        temperature_K=temperature_K,
        transmittance=transmission,
        reflectance=zero_reflectance,
        diameter_m=diameter_m,
        distance_to_fpa_m=distance_to_fpa_m,
    )
