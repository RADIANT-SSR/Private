"""Source protocol.

Defines the structural interface that every spectral radiance source in
RADIANT must satisfy. A source is a pure producer of spectral radiance
``L(λ)`` in W/m²/sr/µm evaluated on an arbitrary wavelength grid (µm).

Per RADIANT_Source_Target_System.md §3.1, sources are composable:
``ThermalSource``, ``ReflectedSolarSource``, ``CombinedSource``, and
``TabulatedRadianceSource`` all implement this protocol. Background
sources produce the same data and can be described with the same
protocol for the radiance-producing path.

Only structural conformance is required. Implementations do NOT need to
subclass ``SpectralRadianceSource`` — duck typing is sufficient.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class SpectralRadianceSource(Protocol):
    """Structural protocol for spectral radiance sources.

    Implementations must be pure: ``spectral_radiance`` must be a
    mathematical function of its inputs with no hidden state mutation.
    Calling it twice with the same grid must return the same values.

    Implementations must NOT perform file I/O or call other stages.
    All spectral data required at construction must already be on (or
    resampleable to) the global wavelength grid.
    """

    def spectral_radiance(self, wavelength_um: np.ndarray) -> np.ndarray:
        """Return spectral radiance ``L(λ)`` in W/m²/sr/µm.

        Parameters
        ----------
        wavelength_um:
            1-D array of wavelengths in µm, strictly ascending, all
            strictly positive.

        Returns
        -------
        numpy.ndarray
            1-D array of spectral radiance values in W/m²/sr/µm,
            same length as ``wavelength_um``. All values are finite
            and non-negative.
        """
        ...
