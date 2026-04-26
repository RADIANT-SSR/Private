"""Factory functions for constructing OpticalElement instances.

Provides convenience constructors for common optical element types:

- ``make_lumped_element``: synthesized virtual element for Modes 1-4.
- ``make_reflective_element``: mirror with eps = 1 - R.
- ``make_refractive_element``: simple refractive element with eps = 0.
- ``make_refractive_cavity_element``: refractive with full cavity model.

See RADIANT_Optics.md section 6.1.
"""

from __future__ import annotations

import numpy as np

from radiant.core.spectral import SpectralData
from radiant.optics.cavity_model import CavityModel
from radiant.optics.element import (
    ElementKind,
    ElementTransferMode,
    OpticalElement,
)


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
        R1=r1_sd,
        T1=t1_sd,
        R2=r2_sd,
        T2=t2_sd,
        alpha=alpha_sd,
        n_refr=n_sd,
        thickness_m=thickness_m,
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
