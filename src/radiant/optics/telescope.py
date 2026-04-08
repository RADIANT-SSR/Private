"""Scalar-mode telescope throughput container.

Implements the 2B.3 scalar cut of RADIANT_Optics.md §5.1 — Mode 1
(scalar transmission). The :class:`ScalarTelescope` composes a
:class:`~radiant.optics.aperture.CircularAperture`, a focal length,
and a wavelength-independent throughput into a single immutable
container the downstream stages can query for

- ``aperture_area_m2`` (``A_collect``) — the clear area used in the
  radiometric signal equation;
- ``f_number`` and ``focal_length_m`` — the consistency-group output
  derived by :func:`~radiant.optics.aperture.resolve_fnumber_group`;
- ``transmission(wavelength_um)`` — a flat spectrum broadcast to the
  requested grid.

Wavefront error, element-by-element prescriptions, filters, nearfield
emission, and stray light are deferred to later tasks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from radiant.core.spectral import SpectralData
from radiant.optics.aperture import CircularAperture, resolve_fnumber_group


@dataclass(frozen=True)
class ScalarTelescope:
    """Scalar-throughput telescope container (Mode 1 of RADIANT_Optics §5.1).

    The telescope is described by a clear aperture, a focal length,
    and a single wavelength-independent throughput ``τ_opt``. This is
    the minimum-fidelity optics container: no WFE, no filters, no
    per-element Kirchhoff bookkeeping, no nearfield emission. It is
    the Category B deliverable for 2B.3.

    Parameters
    ----------
    aperture:
        :class:`CircularAperture` describing the primary clear area.
    transmission_scalar:
        Flat broadband throughput ``τ_opt ∈ [0, 1]`` (dimensionless).
    focal_length_m:
        Effective focal length in metres. Must be ``> 0``. The
        ``(D, f, f/#)`` triple is resolved by
        :func:`resolve_fnumber_group` at construction time; the
        resolved ``f_number`` is stored on the instance.
    f_number:
        Optional. If supplied, must be consistent with
        ``focal_length_m / aperture.aperture_diameter_m`` to within
        ``FNUMBER_CONSISTENCY_RTOL``.
    name:
        Optional human-readable label.
    """

    aperture: CircularAperture
    transmission_scalar: float
    focal_length_m: float
    f_number: float | None = None
    name: str = "scalar_telescope"

    # Resolved values (populated by __post_init__)
    resolved_f_number: float = field(init=False, repr=False)
    aperture_area_m2: float = field(init=False, repr=False)
    solid_angle_sr: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not (0.0 <= self.transmission_scalar <= 1.0):
            raise ValueError(
                f"ScalarTelescope '{self.name}': transmission_scalar = "
                f"{self.transmission_scalar} is outside [0, 1]. Transmission "
                "is a dimensionless efficiency bounded by energy conservation."
            )

        # Resolve (D, f, f/#) — this enforces consistency when all three
        # are supplied and derives the third when only two are.
        _, resolved_f, resolved_fnum = resolve_fnumber_group(
            aperture_diameter_m=self.aperture.aperture_diameter_m,
            focal_length_m=self.focal_length_m,
            f_number=self.f_number,
        )
        object.__setattr__(self, "resolved_f_number", resolved_fnum)
        # The helper may slightly adjust focal_length_m to fit the
        # consistency group if the user supplied D + f/# only. We do
        # not re-assign it here because the two-input paths already
        # populate the field the caller expects; the check above
        # would have raised on any real inconsistency.
        object.__setattr__(self, "focal_length_m", float(resolved_f))

        object.__setattr__(self, "aperture_area_m2", self.aperture.clear_area_m2)
        object.__setattr__(
            self,
            "solid_angle_sr",
            self.aperture.solid_angle_at_focal_length(resolved_f),
        )

    # ------------------------------------------------------------------
    # Transmission
    # ------------------------------------------------------------------

    def transmission(self, wavelength_um: np.ndarray) -> SpectralData:
        """Return the flat throughput broadcast onto ``wavelength_um``.

        Parameters
        ----------
        wavelength_um:
            1-D ascending wavelength grid in µm, strictly positive.

        Returns
        -------
        SpectralData
            ``τ_opt(λ) = transmission_scalar`` on the requested grid,
            dimensionless (``unit=""``).
        """
        lam = np.asarray(wavelength_um, dtype=np.float64)
        if lam.ndim != 1:
            raise ValueError(
                f"ScalarTelescope '{self.name}': wavelength_um must be 1-D, got shape {lam.shape}."
            )
        if lam.size < 2:
            raise ValueError(
                f"ScalarTelescope '{self.name}': wavelength_um needs at "
                f"least two samples, got {lam.size}."
            )
        if not np.all(np.diff(lam) > 0):
            raise ValueError(
                f"ScalarTelescope '{self.name}': wavelength_um must be strictly ascending."
            )
        if np.any(lam <= 0.0):
            raise ValueError(
                f"ScalarTelescope '{self.name}': wavelength_um must be strictly positive."
            )

        values = np.full_like(lam, float(self.transmission_scalar))
        return SpectralData(
            name="optics.transmission.scalar",
            wavelength_um=lam,
            values=values,
            unit="",
            source="ScalarTelescope (Mode 1)",
            source_parameters={
                "transmission_scalar": float(self.transmission_scalar),
                "aperture_diameter_m": float(self.aperture.aperture_diameter_m),
                "obscuration_ratio": float(self.aperture.obscuration_ratio),
                "focal_length_m": float(self.focal_length_m),
                "f_number": float(self.resolved_f_number),
            },
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "name": self.name,
            "aperture": self.aperture.to_dict(),
            "transmission_scalar": float(self.transmission_scalar),
            "focal_length_m": float(self.focal_length_m),
            "f_number": float(self.resolved_f_number),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScalarTelescope:
        """Deserialize from a dict produced by :meth:`to_dict`."""
        aperture = CircularAperture.from_dict(d["aperture"])
        return cls(
            aperture=aperture,
            transmission_scalar=float(d["transmission_scalar"]),
            focal_length_m=float(d["focal_length_m"]),
            f_number=float(d["f_number"]) if d.get("f_number") is not None else None,
            name=str(d.get("name", "scalar_telescope")),
        )
