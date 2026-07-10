"""System transmission — product of all optical element transmittances.

Per RADIANT_Optics.md §5, the system transmission is the product of
all element net transmittances on the wavelength grid.

See also ``nearfield_irradiance.py`` for warm-optics emission.
"""

from __future__ import annotations

import numpy as np

from radiant.core.spectral import SpectralData
from radiant.optics.element import OpticalElement
from radiant.optics.errors import OpticsValidationError


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
        raise OpticsValidationError(
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
