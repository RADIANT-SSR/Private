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

from radiant.core.spectral import SpectralData, SpectralGrid
from radiant.optics.cavity_model import CavityModel
from radiant.optics.element import (
    ElementKind,
    ElementTransferMode,
    OpticalElement,
)
from radiant.optics.errors import OpticsValidationError


def _scalar_to_spectral(
    value: float | SpectralData,
    wavelength_um: np.ndarray | None,
    name: str,
) -> SpectralData:
    """Convert a scalar to flat SpectralData, or align SpectralData to the grid.

    A spectral input carrying its own grid (a coating CSV, an inline λ-table) is
    resampled onto *wavelength_um* when one is given — element arithmetic in the
    optics stage requires a shared grid, and an off-grid spectrum previously
    broadcast-crashed at evaluate. ``SpectralData.resample`` interpolates linearly
    and raises (never extrapolates silently) when the run band extends beyond the
    source data's span.
    """
    if isinstance(value, SpectralData):
        if wavelength_um is not None and not np.array_equal(value.wavelength_um, wavelength_um):
            return value.resample(SpectralGrid(np.asarray(wavelength_um, dtype=np.float64)))
        return value
    if wavelength_um is None:
        raise OpticsValidationError(
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
    name: str = "lumped",
) -> OpticalElement:
    """Create a LUMPED refractive element with the given transmission.

    A lump is bookkeeping, not a surface: its emissivity is zero and it
    never contributes near-field emission (Gap 127). Warm-optics emission
    derives only from defined elements (mirrors ε = 1 − R, cavity
    refractives ε from bulk absorption).
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
    )


def make_reflective_element(
    name: str,
    reflectance: float | SpectralData,
    *,
    wavelength_um: np.ndarray | None = None,
    temperature_K: float = 0.0,
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
        transfer_mode=ElementTransferMode.REFLECTIVE,
    )


def make_refractive_element(
    name: str,
    transmittance: float | SpectralData,
    *,
    kind: ElementKind = ElementKind.LENS,
    wavelength_um: np.ndarray | None = None,
    temperature_K: float = 0.0,
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

    Returns
    -------
    OpticalElement
        With transfer_mode=REFRACTIVE, eps = 0.
    """
    if kind in (ElementKind.MIRROR, ElementKind.COLD_STOP):
        raise OpticsValidationError(
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
        transfer_mode=ElementTransferMode.REFRACTIVE,
    )


def _resolve_surface(
    name: str,
    surface: str,
    reflectance: float | SpectralData | None,
    transmittance: float | SpectralData | None,
    wavelength_um: np.ndarray | None,
) -> tuple[SpectralData, SpectralData]:
    """Resolve one lossless surface's (R, T) pair from either or both inputs.

    Surfaces hold Kirchhoff with no coating absorption (Gap 127 Rule 4):
    R + T = 1. Given one, the other is derived as its complement; given
    both, ``CavityModel`` validates their sum. Given neither, the surface
    is unspecified — an actionable error.
    """
    if reflectance is None and transmittance is None:
        raise OpticsValidationError(
            f"make_refractive_cavity_element '{name}': {surface} needs R or T. "
            "Surfaces are lossless (R + T = 1, Gap 127): specify either the "
            "reflectance or the transmittance and the other is derived."
        )
    if reflectance is not None:
        r_sd = _scalar_to_spectral(reflectance, wavelength_um, f"{name}.{surface}.R")
        if transmittance is not None:
            t_sd = _scalar_to_spectral(transmittance, wavelength_um, f"{name}.{surface}.T")
        else:
            t_sd = SpectralData(
                name=f"{name}.{surface}.T",
                wavelength_um=r_sd.wavelength_um.copy(),
                values=1.0 - r_sd.values,
                unit="",
                source=f"Derived 1 - R (lossless surface, {name}.{surface})",
            )
        return r_sd, t_sd
    t_sd = _scalar_to_spectral(transmittance, wavelength_um, f"{name}.{surface}.T")
    r_sd = SpectralData(
        name=f"{name}.{surface}.R",
        wavelength_um=t_sd.wavelength_um.copy(),
        values=1.0 - t_sd.values,
        unit="",
        source=f"Derived 1 - T (lossless surface, {name}.{surface})",
    )
    return r_sd, t_sd


def make_refractive_cavity_element(
    name: str,
    R1: float | SpectralData | None = None,
    T1: float | SpectralData | None = None,
    R2: float | SpectralData | None = None,
    T2: float | SpectralData | None = None,
    alpha: float | SpectralData = 0.0,
    n_refr: float | SpectralData = 1.5,
    thickness_m: float = 0.0,
    *,
    kind: ElementKind = ElementKind.LENS,
    wavelength_um: np.ndarray | None = None,
    temperature_K: float = 0.0,
) -> OpticalElement:
    """Create a REFRACTIVE element with full cavity model.

    Computes system transmittance, reflectance, and emissivity from
    per-surface coatings, bulk absorption, and refractive index.
    Surfaces are lossless by model rule (Gap 127 Rule 4): per surface,
    R + T = 1 — specify one and the other is derived; specify both and
    they must sum to 1. All absorption (and hence all emission) is bulk:
    ε_eff follows from alpha, thickness, and temperature (≈ α·t in the
    weak-absorption limit).

    Parameters
    ----------
    name:
        Human-readable label.
    R1, T1:
        Entry surface reflectance / transmittance (scalar or spectral);
        at least one — the other derives as its complement.
    R2, T2:
        Exit surface reflectance / transmittance; same rule.
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

    Returns
    -------
    OpticalElement
        With transfer_mode=REFRACTIVE, cavity model, and eps = eps_eff.
    """
    if kind in (ElementKind.MIRROR, ElementKind.COLD_STOP):
        raise OpticsValidationError(
            f"make_refractive_cavity_element: kind={kind.value} is not refractive. "
            "Use make_reflective_element for mirrors."
        )

    r1_sd, t1_sd = _resolve_surface(name, "surface1", R1, T1, wavelength_um)
    r2_sd, t2_sd = _resolve_surface(name, "surface2", R2, T2, wavelength_um)
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
        transfer_mode=ElementTransferMode.REFRACTIVE,
        cavity=cavity,
    )
