"""Reflectance descriptor protocol — Q4 stub base.

Per ``docs/RADIANT_Target_Definition_Matrix.md`` §4 Q4, today's scalar
ρ(λ) / albedo(λ) user inputs should normalize into a lightweight
``ReflectanceDescriptor`` base so BRDF concretions (Lambertian, Phong,
measured) can slot under it later without breaking
:class:`~radiant.core.descriptors.T2Reflective`.

This module ships the stub: a ``runtime_checkable`` protocol plus one
adapter (:class:`ScalarLambertianReflectance`) that wraps a scalar
:class:`SpectralData` ρ(λ) into the protocol.  Existing BRDF classes
(:class:`radiant.source.brdf_lambertian.LambertianBRDF` and
:class:`radiant.source.brdf_phong.PhongBRDF`) grow a ``reflectance_at``
method to satisfy the protocol without changing their
BRDF ``evaluate`` contract.

Per CLAUDE.md Rule 19, this module owns exactly the protocol + scalar
adapter; BRDF concretions stay under ``radiant.source``.  Per the import
rules for ``radiant.core``, only stdlib / numpy / ``radiant.core`` itself
may be imported here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

from radiant.core.spectral import SpectralData


@runtime_checkable
class ReflectanceDescriptor(Protocol):
    """Protocol for angle-resolved hemispherical reflectance ρ(λ, view, illum).

    Implementations return the directional-hemispherical reflectance (a
    dimensionless fraction in ``[0, 1]``) at the requested wavelengths and
    geometry.  This is **not** a BRDF (which has units of sr⁻¹); it is the
    scalar reflectance a radiometry model multiplies against the incident
    irradiance to get the reflected radiance contribution.

    Notes
    -----
    * Lambertian surfaces return ρ(λ) independent of view/illumination.
    * Phong and measured BRDF models may return a view- and illumination-
      dependent ρ by integrating the BRDF over the hemisphere implied by
      the model (or simply returning the total hemispherical ρ that the
      BRDF conserves — the latter matches the existing BRDF dataclasses
      in ``radiant.source`` and is what Step 6.1 wires up).

    The protocol is ``runtime_checkable`` so tests can assert that
    ``isinstance(brdf, ReflectanceDescriptor)`` holds without a registry.
    """

    def reflectance_at(
        self,
        wavelength_um: npt.NDArray[np.float64],
        view_dir: npt.NDArray[np.float64],
        illumination_dir: npt.NDArray[np.float64],
    ) -> npt.NDArray[np.float64]:
        """Evaluate ρ at the requested wavelengths and geometry.

        Parameters
        ----------
        wavelength_um:
            1-D wavelength grid in µm.
        view_dir, illumination_dir:
            Unit vectors in the scene frame (see RADIANT_Conventions.md §1).
            Lambertian implementations ignore these; anisotropic BRDFs use
            them to select a directional hemispherical reflectance.

        Returns
        -------
        ndarray
            ρ(λ) values on the requested grid, shape ``(len(wavelength_um),)``.
        """
        ...


@dataclass(frozen=True)
class ScalarLambertianReflectance:
    """Adapter wrapping a scalar ρ(λ) :class:`SpectralData` into the protocol.

    The adapter materializes the stored reflectance onto the requested
    wavelength grid (via :meth:`SpectralData.resample`) and returns the
    values independent of view / illumination direction — the Lambertian
    definition.

    Parameters
    ----------
    reflectance:
        Hemispherical reflectance ρ(λ), already in canonical units
        (dimensionless, ``[0, 1]``).  Constructed by the source-stage
        boundary converter (Phase 3) or by future inferrer wiring.
    """

    reflectance: SpectralData

    def __post_init__(self) -> None:
        vals = np.asarray(self.reflectance.values, dtype=np.float64)
        if vals.size == 0:
            raise ValueError("ScalarLambertianReflectance: reflectance has zero samples")
        if np.any(vals < 0.0) or np.any(vals > 1.0):
            raise ValueError(
                "ScalarLambertianReflectance: reflectance must be in [0, 1], "
                f"got min={float(vals.min())}, max={float(vals.max())}"
            )

    def reflectance_at(
        self,
        wavelength_um: npt.NDArray[np.float64],
        view_dir: npt.NDArray[np.float64],
        illumination_dir: npt.NDArray[np.float64],
    ) -> npt.NDArray[np.float64]:
        """Return ρ(λ) on the requested grid, angle-independent."""
        _ = view_dir, illumination_dir  # Lambertian ignores geometry.
        lam_query = np.asarray(wavelength_um, dtype=np.float64)
        lam_stored = np.asarray(self.reflectance.wavelength_um, dtype=np.float64)
        vals_stored = np.asarray(self.reflectance.values, dtype=np.float64)
        if lam_query.shape == lam_stored.shape and np.array_equal(lam_query, lam_stored):
            return vals_stored.copy()
        return np.asarray(np.interp(lam_query, lam_stored, vals_stored), dtype=np.float64)


__all__ = [
    "ReflectanceDescriptor",
    "ScalarLambertianReflectance",
]
