"""OpticalElement — individual optical component with Kirchhoff-enforced emissivity.

Per RADIANT_Optics.md section 6.1, emissivity is NEVER an independent
parameter for optical elements.  It is always derived from Kirchhoff's law:

- Reflective (mirrors):  ``epsilon = 1 - R``
- Refractive (simple, T-only):  ``epsilon = 0``  (absorption unknown)
- Refractive (cavity model):  ``epsilon = eps_eff`` from cavity physics

Construction validates energy conservation and that mirrors have zero
transmittance.
"""

from __future__ import annotations

import enum
import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from radiant.core.exceptions import RadiantError
from radiant.core.spectral import SpectralData

if TYPE_CHECKING:
    from radiant.optics.cavity_model import CavityModel

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


class ElementTransferMode(enum.Enum):
    """How the element transfers signal along the optical path."""

    REFLECTIVE = "reflective"
    REFRACTIVE = "refractive"


class KirchhoffViolationError(RadiantError, ValueError):
    """Raised when an optical element violates Kirchhoff's law.

    Co-inherits from :class:`ValueError` for back-compat with existing
    ``pytest.raises(ValueError, ...)`` patterns; :class:`RadiantError`
    is the canonical base.
    """


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
    transfer_mode: ElementTransferMode | None = None
    cavity: CavityModel | None = None
    declared_emissivity: SpectralData | None = None

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

        # --- Declared emissivity (LUMPED pseudo-elements only) ---
        # Rule 5 forbids independent emissivity for a physical surface. A
        # LUMPED element is a virtual stand-in for an entire optical train,
        # whose energy balance (mirror eps = 1-R vs refractive eps = 0) is not
        # resolvable from net transmission alone — so the user may declare the
        # train emissivity there, and only there.
        if self.declared_emissivity is not None:
            if self.kind != ElementKind.LUMPED:
                raise KirchhoffViolationError(
                    f"OpticalElement '{self.name}': declared_emissivity is only "
                    f"permitted for kind=LUMPED pseudo-elements, got "
                    f"kind={self.kind.value}. Physical surfaces derive emissivity "
                    "from Kirchhoff's law (Rule 5): use make_reflective_element "
                    "(eps = 1 - R) or a cavity model instead."
                )
            eps_decl = self.declared_emissivity.values
            if not np.array_equal(
                self.declared_emissivity.wavelength_um, self.transmittance.wavelength_um
            ):
                raise ValueError(
                    f"OpticalElement '{self.name}': declared_emissivity must "
                    "share the transmittance wavelength grid."
                )
            if np.any(eps_decl < 0.0) or np.any(eps_decl > 1.0):
                raise ValueError(
                    f"OpticalElement '{self.name}': declared_emissivity values "
                    f"must be in [0, 1], got range [{float(eps_decl.min()):.6g}, "
                    f"{float(eps_decl.max()):.6g}]."
                )
            budget = t_vals + r_vals + eps_decl
            if np.any(budget > 1.0 + KIRCHHOFF_TOL):
                worst = float(np.max(budget))
                raise KirchhoffViolationError(
                    f"OpticalElement '{self.name}': energy conservation violation — "
                    f"T + R + declared_emissivity = {worst:.6g} > 1 at some "
                    "wavelengths. A train cannot emit more than it absorbs; "
                    "reduce the declared emissivity or the transmission."
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
    # Transfer mode resolution
    # ------------------------------------------------------------------

    @property
    def resolved_transfer_mode(self) -> ElementTransferMode:
        """Return the transfer mode, inferring from kind if not set explicitly."""
        if self.transfer_mode is not None:
            return self.transfer_mode
        if self.kind in (ElementKind.MIRROR, ElementKind.COLD_STOP):
            return ElementTransferMode.REFLECTIVE
        return ElementTransferMode.REFRACTIVE

    # ------------------------------------------------------------------
    # Kirchhoff-derived properties
    # ------------------------------------------------------------------

    @property
    def net_transmittance(self) -> SpectralData:
        """Net throughput of this element along the signal path.

        Reflective: ``R(lambda)`` (reflection acts as the signal path).
        Refractive: ``T(lambda)`` (transmission acts as the signal path).
        """
        if self.resolved_transfer_mode == ElementTransferMode.REFLECTIVE:
            return self.reflectance
        return self.transmittance

    @property
    def emissivity(self) -> SpectralData:
        """Derived emissivity (Rule 5 — NEVER an independent parameter).

        - Reflective: ``eps = 1 - R`` (Kirchhoff)
        - Refractive with cavity: ``eps = T2 * n^2 * (1 - beer) / denom``
          (generalized Kirchhoff — n^2 enhancement for dielectric medium)
        - Refractive without cavity (simple): ``eps = 0`` (absorption unknown;
          the remaining ``1 - T`` is predominantly reflection, not absorption)
        - LUMPED with declared_emissivity: the user-declared train emissivity
          (the one sanctioned exception — a lump is not a physical surface)
        """
        if self.declared_emissivity is not None:
            return SpectralData(
                name=f"{self.name}.emissivity",
                wavelength_um=self.transmittance.wavelength_um.copy(),
                values=self.declared_emissivity.values.copy(),
                unit="",
                source=f"User-declared train emissivity ({self.name})",
            )
        if self.resolved_transfer_mode == ElementTransferMode.REFLECTIVE:
            eps_vals = 1.0 - self.reflectance.values
            source = f"Kirchhoff: 1 - R ({self.name})"
        elif self.cavity is not None:
            # Cavity emissivity: eps_eff = T2 * n^2 * (1 - beer) / denom.
            # The n^2 factor accounts for enhanced photon density of states
            # inside the dielectric medium (generalized Kirchhoff's law).
            eps_vals = self.cavity.eps_eff.values
            source = f"Cavity eps_eff ({self.name})"
        else:
            eps_vals = np.zeros_like(self.transmittance.values)
            source = f"Simple refractive: eps=0 ({self.name})"

        return SpectralData(
            name=f"{self.name}.emissivity",
            wavelength_um=self.transmittance.wavelength_um.copy(),
            values=np.clip(eps_vals, 0.0, 1.0),
            unit="",
            source=source,
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
