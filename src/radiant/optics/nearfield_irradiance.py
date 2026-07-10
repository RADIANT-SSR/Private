"""Nearfield (warm-optics) irradiance at the FPA.

Per RADIANT_Optics.md §7, each warm optical element emits as a graybody
attenuated by all downstream elements, summed and scaled by cold-stop
efficiency:

``E_nf(λ) = η_cold · Σ_i [ ε_i(λ) · B(λ, T_i) · Ω_i · τ_down_i(λ) ]``

Dimensional audit:
    epsilon(dimless) × B(W/m²/sr/µm) × Omega(sr) × tau_down(dimless) = W/m²/µm

See also ``system_transmission.py`` for total transmission.
"""

from __future__ import annotations

import logging
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
        all elements and scaled by cold-stop efficiency.
    per_element:
        Per-element contributions [W/m²/µm], keyed by element name.
        Each contribution includes the cold-stop efficiency scaling.
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
    cold_stop_efficiency: float = 1.0,
) -> NearfieldResult:
    """Total nearfield (warm-optics) irradiance at the FPA with per-element breakdown.

    Per RADIANT_Optics.md section 7:

    ``E_nf(lam) = eta_cold * sum_i [ eps_i(lam) * B(lam, T_i) * Omega_i * tau_down_i(lam) ]``

    Parameters
    ----------
    elements:
        Ordered tuple from entrance pupil to FPA.
    wavelength_um:
        Wavelength grid in microns.
    cold_stop_efficiency:
        Fraction of the FPA hemisphere filled by warm elements [0, 1].
        Unity for uncooled instruments.

    Returns
    -------
    NearfieldResult
        Contains ``total`` (SpectralData, W/m²/µm) and ``per_element``
        (dict mapping element name to its contribution, also W/m²/µm).
        Both include the cold-stop efficiency scaling.
    """
    if not elements:
        raise OpticsValidationError("compute_nearfield_irradiance: element list must not be empty.")
    if not 0.0 <= cold_stop_efficiency <= 1.0:
        raise OpticsValidationError(
            f"compute_nearfield_irradiance: cold_stop_efficiency must be "
            f"in [0, 1], got {cold_stop_efficiency}."
        )

    e_nf = np.zeros_like(wavelength_um, dtype=np.float64)
    per_element: dict[str, SpectralData] = {}

    for i, elem in enumerate(elements):
        if elem.temperature_K == 0.0:
            continue

        eps = elem.emissivity.values
        b_lam = planck_spectral_radiance(wavelength_um, elem.temperature_K)
        omega = elem.nearfield_solid_angle_sr
        tau_down = compute_downstream_transmission(elements, i, wavelength_um)

        # eps(dimless) * B(W/m2/sr/um) * omega(sr) * tau_down(dimless) = W/m2/um
        contribution = eps * b_lam * omega * tau_down
        e_nf += contribution

        # Store per-element contribution (scaled by cold-stop below).
        per_element[elem.name] = SpectralData(
            name=f"optics.nearfield.{elem.name}",
            wavelength_um=wavelength_um.copy(),
            values=contribution * cold_stop_efficiency,
            unit="W/m^2/um",
            source=f"Nearfield emission from {elem.name} (T={elem.temperature_K} K), "
            f"eta_cold={cold_stop_efficiency}",
        )

    e_nf *= cold_stop_efficiency

    total = SpectralData(
        name="optics.nearfield_irradiance_at_fpa",
        wavelength_um=wavelength_um.copy(),
        values=e_nf,
        unit="W/m^2/um",
        source=f"Nearfield emission from {len(elements)} element(s), "
        f"eta_cold={cold_stop_efficiency}",
    )

    return NearfieldResult(total=total, per_element=per_element)
