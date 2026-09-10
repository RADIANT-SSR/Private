"""Nearfield (warm-optics) irradiance at the FPA.

Per RADIANT_Optics.md §7 (Gap 128 model, owner-ratified 2026-09-09), every
in-beam warm element is seen through the *same* geometry — the étendue
acceptance cone the working f/# sets (``etendue_cone.py``) — and each emits as
a graybody attenuated by everything downstream of it:

``E_nf(λ) = Ω_cone · Σ_i [ ε_i(λ) · B(λ, T_i) · τ_down_i(λ) ]``   [W/m²/µm]

There is no cold-stop attenuation factor: in-cone emission arrives through the
imaging path itself and cannot be blocked, while out-of-cone warm structure is
taken to be blocked completely (the model always assumes a cold stop). What a
cold stop *does* control is the size of the pupil, hence ``N_eff`` and hence
``Ω_cone`` — see ``effective_pupil.py``.

Superseded (Gap 128): each element formerly carried a private
``Ω_i = π (D_i/2)² / d_i²``, which the Lagrange invariant does not permit — a
0.3 m mirror 1.0 m from the FPA claimed 0.0707 sr against an f/6 cone of
0.0217 sr.

Dimensional audit:
    Omega_cone(sr) × epsilon(dimless) × B(W/m²/sr/µm) × tau_down(dimless)
    = W/m²/µm

See also ``system_transmission.py`` for total transmission.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.spectral import SpectralData
from radiant.optics.element import OpticalElement
from radiant.optics.errors import OpticsValidationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NearfieldResult:
    """Nearfield irradiance with per-element breakdown.

    Attributes
    ----------
    total:
        Total nearfield irradiance at the FPA [W/m²/µm], summed over
        all elements.
    per_element:
        Per-element contributions [W/m²/µm], keyed by element name.
        Summing all values equals ``total``.
    """

    total: SpectralData
    per_element: dict[str, SpectralData]


def compute_downstream_transmission(
    elements: tuple[OpticalElement, ...],
    index: int,
    wavelength_um: np.ndarray,
) -> np.ndarray:
    """Product of net transmittance for elements downstream of *index*.

    ``downstream(i) = product_{j=i+1}^{N} tau_j``

    For the last element, returns ones (nothing downstream).

    Parameters
    ----------
    elements:
        Ordered tuple from entrance pupil to FPA.
    index:
        Index of the element whose downstream transmission to compute.
    wavelength_um:
        Wavelength grid.

    Returns
    -------
    np.ndarray
        Downstream transmission array, dimensionless.
    """
    tau_down = np.ones_like(wavelength_um, dtype=np.float64)
    for j in range(index + 1, len(elements)):
        tau_down = tau_down * elements[j].net_transmittance.values
    return tau_down


def compute_nearfield_irradiance(
    elements: tuple[OpticalElement, ...],
    wavelength_um: np.ndarray,
    omega_cone_sr: float,
) -> NearfieldResult:
    """Total nearfield (warm-optics) irradiance at the FPA with per-element breakdown.

    Per RADIANT_Optics.md section 7 (Gap 128):

    ``E_nf(lam) = Omega_cone * sum_i [ eps_i(lam) * B(lam, T_i) * tau_down_i(lam) ]``

    One geometry for every element: the acceptance cone. An element cannot fill
    more of the FPA's view than the Lagrange invariant permits, however close to
    the focal plane it sits.

    Parameters
    ----------
    elements:
        Ordered tuple from entrance pupil to FPA.
    wavelength_um:
        Wavelength grid in microns.
    omega_cone_sr:
        The étendue acceptance cone [sr] at the working f/#, from
        :func:`radiant.optics.etendue_cone.etendue_cone_solid_angle_sr`.
        Must satisfy ``0 < Omega_cone <= 2*pi``.

    Returns
    -------
    NearfieldResult
        Contains ``total`` (SpectralData, W/m²/µm) and ``per_element``
        (dict mapping element name to its contribution, also W/m²/µm).
    """
    if not elements:
        raise OpticsValidationError("compute_nearfield_irradiance: element list must not be empty.")
    if not math.isfinite(omega_cone_sr) or not 0.0 < omega_cone_sr <= 2.0 * math.pi:
        raise OpticsValidationError(
            f"compute_nearfield_irradiance: omega_cone_sr = {omega_cone_sr} sr is "
            "invalid. The acceptance cone must satisfy 0 < Omega_cone <= 2*pi sr "
            "(a hemisphere); it is derived from the working f/# by "
            "radiant.optics.etendue_cone.etendue_cone_solid_angle_sr."
        )

    e_nf = np.zeros_like(wavelength_um, dtype=np.float64)
    per_element: dict[str, SpectralData] = {}

    for i, elem in enumerate(elements):
        if elem.temperature_K == 0.0:
            continue

        eps = elem.emissivity.values
        b_lam = planck_spectral_radiance(wavelength_um, elem.temperature_K)
        tau_down = compute_downstream_transmission(elements, i, wavelength_um)

        # omega(sr) * eps(dimless) * B(W/m2/sr/um) * tau_down(dimless) = W/m2/um
        contribution = omega_cone_sr * eps * b_lam * tau_down
        e_nf += contribution

        per_element[elem.name] = SpectralData(
            name=f"optics.nearfield.{elem.name}",
            wavelength_um=wavelength_um.copy(),
            values=contribution,
            unit="W/m^2/um",
            source=f"Nearfield emission from {elem.name} (T={elem.temperature_K} K), "
            f"Omega_cone={omega_cone_sr:.6g} sr",
        )

    total = SpectralData(
        name="optics.nearfield_irradiance_at_fpa",
        wavelength_um=wavelength_um.copy(),
        values=e_nf,
        unit="W/m^2/um",
        source=f"Nearfield emission from {len(elements)} element(s), "
        f"Omega_cone={omega_cone_sr:.6g} sr",
    )

    return NearfieldResult(total=total, per_element=per_element)
