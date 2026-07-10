"""Thermal (self-emission) spectral radiance source.

Implements ``ThermalSource`` from RADIANT_Source_Target_System.md §3.2:

    L_th(λ) = ε(λ) · B(λ, T)

where ``B`` is the Planck spectral radiance and ``ε`` is the spectral
emissivity of the emitting surface. Emissivity may be a scalar (a
graybody) or a full :class:`~radiant.core.spectral.SpectralData` table.

This module implements self-emission only; reflected solar contribution
lives in a separate source type, and the Kirchhoff-consistent
``CombinedSource`` composes the two.

Assumptions
-----------
- Local thermodynamic equilibrium (single well-defined temperature).
- Lambertian (isotropic) emission: ``ε`` is direction-independent.
- Unpolarized radiation.

These are the standard assumptions for thermal emission from solid
surfaces in sensor performance modeling. They fail for non-LTE plasmas,
specular grazing-angle emission, and polarization-sensitive
applications — none of which are in the v1 scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.spectral import SpectralData
from radiant.source.errors import SourceValidationError


@dataclass(frozen=True)
class ThermalSource:
    """Thermal self-emission source: ``L(λ) = ε(λ) · B(λ, T)``.

    Parameters
    ----------
    temperature_K:
        Surface temperature in kelvin. Must be ``≥ 0``.
    emissivity:
        Either a scalar in ``[0, 1]`` (graybody) or a
        :class:`~radiant.core.spectral.SpectralData` object with values
        in ``[0, 1]`` and unit ``""`` (dimensionless).
    name:
        Optional human-readable label for provenance/logging.

    Notes
    -----
    ``ThermalSource`` is frozen and immutable. It holds no references
    to external spectral stores; evaluation is pure.
    """

    temperature_K: float
    emissivity: float | SpectralData
    name: str = "thermal_source"
    _tag: str = field(default="thermal", init=False, repr=False)

    def __post_init__(self) -> None:
        if self.temperature_K < 0.0:
            raise SourceValidationError(
                f"ThermalSource '{self.name}': temperature_K = {self.temperature_K} K "
                "is invalid. Temperature must be non-negative (use 0 for a zero-"
                "radiance source)."
            )
        if isinstance(self.emissivity, SpectralData):
            vals = self.emissivity.values
            if np.any(vals < 0.0) or np.any(vals > 1.0):
                raise SourceValidationError(
                    f"ThermalSource '{self.name}': spectral emissivity "
                    f"'{self.emissivity.name}' has values outside [0, 1] "
                    f"(min={vals.min():g}, max={vals.max():g}). Emissivity is "
                    "a dimensionless fraction bounded by Kirchhoff's law."
                )
        else:
            # Scalar path — coerce to float and validate.
            eps = float(self.emissivity)
            if not (0.0 <= eps <= 1.0):
                raise SourceValidationError(
                    f"ThermalSource '{self.name}': emissivity = {eps} is outside "
                    "[0, 1]. Emissivity is a dimensionless fraction bounded by "
                    "Kirchhoff's law (ε ≤ 1)."
                )
            # Re-store as plain float so downstream code needn't branch twice.
            object.__setattr__(self, "emissivity", eps)

    # ------------------------------------------------------------------
    # Protocol: SpectralRadianceSource
    # ------------------------------------------------------------------

    def spectral_radiance(self, wavelength_um: np.ndarray) -> np.ndarray:
        """Return ``ε(λ) · B(λ, T)`` on ``wavelength_um`` in W/m²/sr/µm.

        Parameters
        ----------
        wavelength_um:
            1-D ascending wavelength grid in µm, strictly positive.

        Returns
        -------
        numpy.ndarray
            Spectral radiance in W/m²/sr/µm, same length as
            ``wavelength_um``.
        """
        lam = np.asarray(wavelength_um, dtype=np.float64)
        B = planck_spectral_radiance(lam, self.temperature_K)

        if isinstance(self.emissivity, SpectralData):
            # Interpolate ε onto the requested grid (linear). Out-of-range
            # is an error — we do not silently extrapolate a physical
            # material property.
            eps_wl = self.emissivity.wavelength_um
            if lam[0] < eps_wl[0] or lam[-1] > eps_wl[-1]:
                raise SourceValidationError(
                    f"ThermalSource '{self.name}': requested wavelength range "
                    f"[{lam[0]:.4f}, {lam[-1]:.4f}] µm extends outside the "
                    f"emissivity table range [{eps_wl[0]:.4f}, {eps_wl[-1]:.4f}] µm. "
                    "Extend the emissivity data or trim the evaluation grid."
                )
            eps = np.interp(lam, eps_wl, self.emissivity.values)
            return np.asarray(eps * B, dtype=np.float64)

        # Scalar graybody.
        return np.asarray(float(self.emissivity) * B, dtype=np.float64)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        if isinstance(self.emissivity, SpectralData):
            eps_payload: Any = {"kind": "spectral", "data": self.emissivity.to_dict()}
        else:
            eps_payload = {"kind": "scalar", "value": float(self.emissivity)}
        return {
            "name": self.name,
            "temperature_K": float(self.temperature_K),
            "emissivity": eps_payload,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ThermalSource:
        """Deserialize from a dict produced by :meth:`to_dict`."""
        eps_payload = d["emissivity"]
        eps: float | SpectralData
        if eps_payload["kind"] == "spectral":
            eps = SpectralData.from_dict(eps_payload["data"])
        elif eps_payload["kind"] == "scalar":
            eps = float(eps_payload["value"])
        else:
            raise SourceValidationError(
                f"ThermalSource.from_dict: unknown emissivity kind "
                f"'{eps_payload['kind']}'. Expected 'scalar' or 'spectral'."
            )
        return cls(
            temperature_K=float(d["temperature_K"]),
            emissivity=eps,
            name=str(d.get("name", "thermal_source")),
        )
