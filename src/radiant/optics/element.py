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


class ElementTransferMode(enum.Enum):
    """How the element transfers signal along the optical path."""

    REFLECTIVE = "reflective"
    REFRACTIVE = "refractive"


class KirchhoffViolationError(ValueError):
    """Raised when an optical element violates Kirchhoff's law."""


# ------------------------------------------------------------------
# CavityModel — pure radiometric computation for refractive elements
# ------------------------------------------------------------------

_CAVITY_KIRCHHOFF_TOL: float = 1e-4


@dataclass(frozen=True)
class CavityModel:
    """Per-surface cavity physics for a refractive optical element.

    Computes system transmittance, system reflectance, and effective
    emissivity from surface coatings (R1, T1, R2, T2), bulk absorption
    coefficient (alpha), refractive index (n_refr), and substrate
    thickness (thickness_m).

    All spectral inputs must share the same wavelength grid.
    This class contains NO geometry or thermal properties — it is
    a pure radiometric computation.

    Parameters
    ----------
    R1, T1:
        Entry surface reflectance and transmittance.
    R2, T2:
        Exit surface reflectance and transmittance.
    alpha:
        Bulk absorption coefficient [1/m].
    n_refr:
        Refractive index (dimensionless).
    thickness_m:
        Substrate thickness [m].
    """

    R1: SpectralData
    T1: SpectralData
    R2: SpectralData
    T2: SpectralData
    alpha: SpectralData
    n_refr: SpectralData
    thickness_m: float

    def __post_init__(self) -> None:
        # Validate all share the same wavelength grid.
        ref_wl = self.R1.wavelength_um
        for name, sd in [
            ("T1", self.T1), ("R2", self.R2), ("T2", self.T2),
            ("alpha", self.alpha), ("n_refr", self.n_refr),
        ]:
            if not np.array_equal(sd.wavelength_um, ref_wl):
                raise ValueError(
                    f"CavityModel: '{name}' wavelength grid does not match R1."
                )

        # Surface energy conservation: R + T <= 1 at each surface.
        for label, r_sd, t_sd in [("surface 1", self.R1, self.T1),
                                   ("surface 2", self.R2, self.T2)]:
            total = r_sd.values + t_sd.values
            if np.any(total > 1.0 + _CAVITY_KIRCHHOFF_TOL):
                worst = float(np.max(total))
                raise KirchhoffViolationError(
                    f"CavityModel {label}: R + T = {worst:.6g} > 1. "
                    "Surface energy conservation requires R + T <= 1."
                )

        # Absorption coefficient must be non-negative.
        if np.any(self.alpha.values < 0.0):
            raise ValueError(
                "CavityModel: absorption coefficient alpha must be >= 0 "
                f"(gain is not physical). Min value: {float(self.alpha.values.min()):.6g}."
            )

        # Refractive index must be >= 1.
        if np.any(self.n_refr.values < 1.0):
            raise ValueError(
                "CavityModel: refractive index n must be >= 1. "
                f"Min value: {float(self.n_refr.values.min()):.6g}."
            )

        # Thickness must be non-negative.
        if self.thickness_m < 0.0:
            raise ValueError(
                f"CavityModel: thickness_m must be >= 0, got {self.thickness_m}."
            )

        # Energy conservation: T_sys + R_sys <= 1 (absorptance >= 0).
        t_sys = self.T_sys.values
        r_sys = self.R_sys.values
        total = t_sys + r_sys
        if np.any(total > 1.0 + _CAVITY_KIRCHHOFF_TOL):
            worst = float(np.max(total))
            raise KirchhoffViolationError(
                f"CavityModel: energy violation — T_sys + R_sys = {worst:.6g} > 1. "
                "Check surface coating values."
            )

    @property
    def wavelength_um(self) -> np.ndarray:
        """Wavelength grid shared by all spectral inputs."""
        return self.R1.wavelength_um

    @property
    def beer(self) -> np.ndarray:
        """Beer-Lambert bulk transmission: exp(-alpha * d)."""
        return np.exp(-self.alpha.values * self.thickness_m)

    @property
    def denom(self) -> np.ndarray:
        """Cavity denominator: 1 - R1 * R2 * beer^2."""
        b = self.beer
        return 1.0 - self.R1.values * self.R2.values * b * b

    @property
    def T_sys(self) -> SpectralData:
        """System transmittance: T1 * beer * T2 / denom."""
        b = self.beer
        vals = self.T1.values * b * self.T2.values / self.denom
        return SpectralData(
            name="cavity.T_sys",
            wavelength_um=self.wavelength_um.copy(),
            values=vals,
            unit="",
            source="Cavity model: T1 * beer * T2 / denom",
        )

    @property
    def R_sys(self) -> SpectralData:
        """System reflectance: R1 + T1^2 * R2 * beer^2 / denom."""
        b = self.beer
        vals = self.R1.values + (
            self.T1.values ** 2 * self.R2.values * b * b / self.denom
        )
        return SpectralData(
            name="cavity.R_sys",
            wavelength_um=self.wavelength_um.copy(),
            values=vals,
            unit="",
            source="Cavity model: R1 + T1^2 * R2 * beer^2 / denom",
        )

    @property
    def eps_eff(self) -> SpectralData:
        """Effective cavity emissivity: T2 * n^2 * (1 - beer) / denom."""
        b = self.beer
        vals = self.T2.values * self.n_refr.values ** 2 * (1.0 - b) / self.denom
        return SpectralData(
            name="cavity.eps_eff",
            wavelength_um=self.wavelength_um.copy(),
            values=vals,
            unit="",
            source="Cavity model: T2 * n^2 * (1 - beer) / denom",
        )


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
        """
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


# ------------------------------------------------------------------
# Factory helpers
# ------------------------------------------------------------------


def _scalar_to_spectral(
    value: float | SpectralData,
    wavelength_um: np.ndarray | None,
    name: str,
) -> SpectralData:
    """Convert a scalar to flat SpectralData, or pass through SpectralData."""
    if isinstance(value, SpectralData):
        return value
    if wavelength_um is None:
        raise ValueError(
            f"'{name}': wavelength_um is required when input is a scalar. "
            "Provide a wavelength grid to broadcast the scalar value."
        )
    return SpectralData(
        name=name,
        wavelength_um=wavelength_um.copy(),
        values=np.full_like(wavelength_um, float(value)),
        unit="",
        source=f"Scalar {float(value)} broadcast ({name})",
    )


def make_lumped_element(
    transmission: SpectralData,
    temperature_K: float,
    diameter_m: float,
    distance_to_fpa_m: float,
    name: str = "lumped",
) -> OpticalElement:
    """Create a LUMPED refractive element with the given transmission.

    Emissivity is zero (simple refractive — absorption unknown).
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


def make_reflective_element(
    name: str,
    reflectance: float | SpectralData,
    *,
    wavelength_um: np.ndarray | None = None,
    temperature_K: float = 0.0,
    diameter_m: float = 1.0,
    distance_to_fpa_m: float = 1.0,
) -> OpticalElement:
    """Create a REFLECTIVE mirror element.

    Parameters
    ----------
    name:
        Human-readable label.
    reflectance:
        Mirror reflectance — scalar (float) or spectral (SpectralData).
    wavelength_um:
        Required when reflectance is a scalar.
    temperature_K:
        Element temperature [K] for nearfield calculation.
    diameter_m:
        Clear aperture diameter [m] for nearfield geometry.
    distance_to_fpa_m:
        Distance to FPA [m] for nearfield geometry.

    Returns
    -------
    OpticalElement
        With transfer_mode=REFLECTIVE, eps = 1 - R.
    """
    rho = _scalar_to_spectral(reflectance, wavelength_um, f"{name}.reflectance")
    wl = rho.wavelength_um
    zero_tau = SpectralData(
        name=f"{name}.transmittance",
        wavelength_um=wl.copy(),
        values=np.zeros_like(wl),
        unit="",
        source=f"Mirror zero transmittance ({name})",
    )
    return OpticalElement(
        name=name,
        kind=ElementKind.MIRROR,
        temperature_K=temperature_K,
        transmittance=zero_tau,
        reflectance=rho,
        diameter_m=diameter_m,
        distance_to_fpa_m=distance_to_fpa_m,
        transfer_mode=ElementTransferMode.REFLECTIVE,
    )


def make_refractive_element(
    name: str,
    transmittance: float | SpectralData,
    *,
    kind: ElementKind = ElementKind.LENS,
    wavelength_um: np.ndarray | None = None,
    temperature_K: float = 0.0,
    diameter_m: float = 1.0,
    distance_to_fpa_m: float = 1.0,
) -> OpticalElement:
    """Create a simple REFRACTIVE element with known transmittance.

    Emissivity is zero — when only T is known, the remaining 1-T
    is predominantly reflection, not absorption.

    Parameters
    ----------
    name:
        Human-readable label.
    transmittance:
        Element transmittance — scalar (float) or spectral (SpectralData).
    kind:
        Element type (LENS, WINDOW, FILTER, etc.). Must not be MIRROR.
    wavelength_um:
        Required when transmittance is a scalar.
    temperature_K:
        Element temperature [K] for nearfield calculation.
    diameter_m:
        Clear aperture diameter [m] for nearfield geometry.
    distance_to_fpa_m:
        Distance to FPA [m] for nearfield geometry.

    Returns
    -------
    OpticalElement
        With transfer_mode=REFRACTIVE, eps = 0.
    """
    if kind in (ElementKind.MIRROR, ElementKind.COLD_STOP):
        raise ValueError(
            f"make_refractive_element: kind={kind.value} is not refractive. "
            "Use make_reflective_element for mirrors."
        )
    tau = _scalar_to_spectral(transmittance, wavelength_um, f"{name}.transmittance")
    wl = tau.wavelength_um
    zero_rho = SpectralData(
        name=f"{name}.reflectance",
        wavelength_um=wl.copy(),
        values=np.zeros_like(wl),
        unit="",
        source=f"Simple refractive zero reflectance ({name})",
    )
    return OpticalElement(
        name=name,
        kind=kind,
        temperature_K=temperature_K,
        transmittance=tau,
        reflectance=zero_rho,
        diameter_m=diameter_m,
        distance_to_fpa_m=distance_to_fpa_m,
        transfer_mode=ElementTransferMode.REFRACTIVE,
    )


def make_refractive_cavity_element(
    name: str,
    R1: float | SpectralData,
    T1: float | SpectralData,
    R2: float | SpectralData,
    T2: float | SpectralData,
    alpha: float | SpectralData,
    n_refr: float | SpectralData,
    thickness_m: float,
    *,
    kind: ElementKind = ElementKind.LENS,
    wavelength_um: np.ndarray | None = None,
    temperature_K: float = 0.0,
    diameter_m: float = 1.0,
    distance_to_fpa_m: float = 1.0,
) -> OpticalElement:
    """Create a REFRACTIVE element with full cavity model.

    Computes system transmittance, reflectance, and emissivity from
    per-surface coatings, bulk absorption, and refractive index.

    Parameters
    ----------
    name:
        Human-readable label.
    R1, T1:
        Entry surface reflectance and transmittance (scalar or spectral).
    R2, T2:
        Exit surface reflectance and transmittance (scalar or spectral).
    alpha:
        Bulk absorption coefficient [1/m] (scalar or spectral).
    n_refr:
        Refractive index (scalar or spectral).
    thickness_m:
        Substrate thickness [m].
    kind:
        Element type (LENS, WINDOW, FILTER, etc.). Must not be MIRROR.
    wavelength_um:
        Required when any input is a scalar.
    temperature_K:
        Element temperature [K] for nearfield calculation.
    diameter_m:
        Clear aperture diameter [m] for nearfield geometry.
    distance_to_fpa_m:
        Distance to FPA [m] for nearfield geometry.

    Returns
    -------
    OpticalElement
        With transfer_mode=REFRACTIVE, cavity model, and eps = eps_eff.
    """
    if kind in (ElementKind.MIRROR, ElementKind.COLD_STOP):
        raise ValueError(
            f"make_refractive_cavity_element: kind={kind.value} is not refractive. "
            "Use make_reflective_element for mirrors."
        )

    r1_sd = _scalar_to_spectral(R1, wavelength_um, f"{name}.R1")
    t1_sd = _scalar_to_spectral(T1, wavelength_um, f"{name}.T1")
    r2_sd = _scalar_to_spectral(R2, wavelength_um, f"{name}.R2")
    t2_sd = _scalar_to_spectral(T2, wavelength_um, f"{name}.T2")
    alpha_sd = _scalar_to_spectral(alpha, wavelength_um, f"{name}.alpha")
    n_sd = _scalar_to_spectral(n_refr, wavelength_um, f"{name}.n_refr")

    cavity = CavityModel(
        R1=r1_sd, T1=t1_sd, R2=r2_sd, T2=t2_sd,
        alpha=alpha_sd, n_refr=n_sd, thickness_m=thickness_m,
    )

    return OpticalElement(
        name=name,
        kind=kind,
        temperature_K=temperature_K,
        transmittance=cavity.T_sys,
        reflectance=cavity.R_sys,
        diameter_m=diameter_m,
        distance_to_fpa_m=distance_to_fpa_m,
        transfer_mode=ElementTransferMode.REFRACTIVE,
        cavity=cavity,
    )
