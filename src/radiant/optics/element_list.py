"""Element list computations — system transmission and nearfield irradiance.

Per RADIANT_Optics.md sections 5 and 7, the element list is the canonical
internal representation for all five transmission input modes.  This module
computes:

1. **System transmission**: product of all element net transmittances.
2. **Nearfield (warm-optics) irradiance at the FPA**: per-element
   graybody emission attenuated by all downstream elements, summed over
   the list and scaled by cold-stop efficiency.

Dimensional audit for nearfield:
    epsilon(dimless) x B(W/m^2/sr/um) x Omega(sr) x tau_down(dimless) = W/m^2/um
"""

from __future__ import annotations

import logging

import numpy as np

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.spectral import SpectralData
from radiant.optics.element import OpticalElement

logger = logging.getLogger(__name__)


def compute_system_transmission(
    elements: tuple[OpticalElement, ...],
    wavelength_um: np.ndarray,
) -> SpectralData:
    """Product of all element net transmittances on the given wavelength grid.

    Parameters
    ----------
    elements:
        Ordered tuple of optical elements (entrance pupil to FPA).
    wavelength_um:
        Wavelength grid in microns.

    Returns
    -------
    SpectralData
        System transmission, dimensionless [0, 1].
    """
    if not elements:
        raise ValueError(
            "compute_system_transmission: element list must not be empty. "
            "Even scalar-mode optics requires at least one lumped element."
        )

    tau = np.ones_like(wavelength_um, dtype=np.float64)
    for elem in elements:
        tau = tau * elem.net_transmittance.values

    return SpectralData(
        name="optics.system_transmission",
        wavelength_um=wavelength_um.copy(),
        values=tau,
        unit="",
        source=f"Product of {len(elements)} element(s)",
    )


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
) -> SpectralData:
    """Total nearfield (warm-optics) irradiance at the FPA.

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
    SpectralData
        Nearfield irradiance at the FPA in W/m^2/um.
    """
    if not elements:
        raise ValueError("compute_nearfield_irradiance: element list must not be empty.")
    if not 0.0 <= cold_stop_efficiency <= 1.0:
        raise ValueError(
            f"compute_nearfield_irradiance: cold_stop_efficiency must be "
            f"in [0, 1], got {cold_stop_efficiency}."
        )

    e_nf = np.zeros_like(wavelength_um, dtype=np.float64)

    for i, elem in enumerate(elements):
        if elem.temperature_K == 0.0:
            continue

        eps = elem.emissivity.values
        b_lam = planck_spectral_radiance(wavelength_um, elem.temperature_K)
        omega = elem.nearfield_solid_angle_sr
        tau_down = compute_downstream_transmission(elements, i, wavelength_um)

        # eps(dimless) * B(W/m2/sr/um) * omega(sr) * tau_down(dimless) = W/m2/um
        e_nf += eps * b_lam * omega * tau_down

    e_nf *= cold_stop_efficiency

    return SpectralData(
        name="optics.nearfield_irradiance_at_fpa",
        wavelength_um=wavelength_um.copy(),
        values=e_nf,
        unit="W/m^2/um",
        source=f"Nearfield emission from {len(elements)} element(s), "
        f"eta_cold={cold_stop_efficiency}",
    )
