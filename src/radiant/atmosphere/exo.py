"""Exo-atmospheric model — vacuum path.

For sensors above the atmosphere observing targets above the atmosphere
(typical space surveillance and satellite-to-satellite imaging) the
three spectral outputs are constants per
``docs/RADIANT_Atmosphere.md`` §3.3::

    τ_atm(λ)     ≡ 1.0
    L_path(λ)    ≡ 0.0
    L_atm_down(λ) ≡ 0.0

This is **not** "no atmosphere" — it is a deliberate statement that the
intervening medium (the cosmic vacuum) has unity transmittance and
zero path radiance to within a part in 10²⁰. The CMB is delivered as a
``BlackbodyBackground(T = 2.725)`` from ``SourceStage``, not from this
model.
"""

from __future__ import annotations

import numpy as np

from radiant.atmosphere.protocol import (
    AtmosphericGeometry,
    AtmosphericState,
)
from radiant.core.spectral import SpectralData


class ExoAtmosphere:
    """Vacuum atmosphere model: ``τ ≡ 1``, ``L_path ≡ 0``, ``L_atm_down ≡ 0``.

    This class implements the :class:`~radiant.atmosphere.protocol.Atmosphere`
    structural protocol and is the canonical choice for space-based
    observers viewing space-based targets.

    Parameters
    ----------
    name:
        Optional human-readable label for provenance.
    """

    def __init__(self, name: str = "exo_atmosphere") -> None:
        self.name = name

    def build_state(
        self,
        wavelength_um: np.ndarray,
        geometry: AtmosphericGeometry,
    ) -> AtmosphericState:
        """Return the trivial state ``(1, 0, 0)`` on ``wavelength_um``."""
        lam = np.asarray(wavelength_um, dtype=np.float64)
        if lam.ndim != 1:
            raise ValueError(
                f"ExoAtmosphere '{self.name}': wavelength_um must be 1-D, got shape {lam.shape}."
            )
        if lam.size < 2:
            raise ValueError(
                f"ExoAtmosphere '{self.name}': wavelength_um needs at least "
                f"two samples, got {lam.size}."
            )
        if not np.all(np.diff(lam) > 0):
            raise ValueError(
                f"ExoAtmosphere '{self.name}': wavelength_um must be strictly ascending."
            )
        if np.any(lam <= 0.0):
            raise ValueError(
                f"ExoAtmosphere '{self.name}': wavelength_um must be strictly positive."
            )

        ones = np.ones_like(lam)
        zeros = np.zeros_like(lam)

        transmittance = SpectralData(
            name="atm.transmittance.exo",
            wavelength_um=lam,
            values=ones,
            unit="",
            source="ExoAtmosphere (vacuum)",
            source_parameters={"model": "exo"},
        )
        path_radiance = SpectralData(
            name="atm.path_radiance.exo",
            wavelength_um=lam,
            values=zeros,
            unit="W/m²/sr/µm",
            source="ExoAtmosphere (vacuum)",
            source_parameters={"model": "exo"},
        )
        atm_emission_down = SpectralData(
            name="atm.emission_down.exo",
            wavelength_um=lam,
            values=zeros.copy(),
            unit="W/m²/sr/µm",
            source="ExoAtmosphere (vacuum)",
            source_parameters={"model": "exo"},
        )

        return AtmosphericState(
            transmittance=transmittance,
            path_radiance=path_radiance,
            atm_emission_down=atm_emission_down,
            geometry=geometry,
            derivation_chain=("ExoAtmosphere: τ≡1, L_path≡0, L_atm_down≡0",),
        )
