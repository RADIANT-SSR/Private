"""Circular aperture geometry.

Implements a circular clear aperture with optional central obscuration
per ``docs/architecture/RADIANT_Optics.md`` section 3.  Wavefront error, spiders,
apodization, pupil mask generation, and the full ``OpticsState`` contract
are deferred to later tasks.

All lengths are in SI metres. ``f_number`` is dimensionless.

The solid angle a single square pixel subtends when seen from the
aperture is::

    Omega_pixel = pixel_area / focal_length**2   [sr]

and the single-pixel etendue that drives the extended-source signal
equation is::

    Omega_pupil = pi / (4 * f/#**2)               [sr]

See section 7.1 of the optics document for the signal etendue bookkeeping.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CircularAperture:
    """Circular clear aperture with optional central obscuration.

    Implements the scalar-mode slice of RADIANT_Optics.md §3.1–3.3:
    unapodized, optional central obscuration and secondary-support
    spiders. Apodization and the full ``PupilDescription`` are deferred
    to later tasks.

    Parameters
    ----------
    aperture_diameter_m:
        Primary clear-aperture diameter in metres. Must be ``> 0``.
    obscuration_ratio:
        ``D_secondary / D_primary``. Must satisfy ``0 ≤ ε < 1``. An
        obscuration ratio of ``1`` (or greater) is unphysical — the
        secondary would occupy the entire aperture.
    n_spiders:
        Number of secondary-support spider arms (radial struts). 0 = none.
    spider_width_m:
        Width of each spider arm in metres (0 = no area removed).
    name:
        Optional human-readable label for provenance/logging.
    """

    aperture_diameter_m: float
    obscuration_ratio: float = 0.0
    n_spiders: int = 0
    spider_width_m: float = 0.0
    name: str = "circular_aperture"
    _kind: str = field(default="circular", init=False, repr=False)

    def __post_init__(self) -> None:
        if not math.isfinite(self.aperture_diameter_m) or self.aperture_diameter_m <= 0.0:
            raise ValueError(
                f"CircularAperture '{self.name}': aperture_diameter_m = "
                f"{self.aperture_diameter_m} is invalid. The clear primary "
                "diameter must be a positive finite number in metres."
            )
        if not math.isfinite(self.obscuration_ratio) or not (0.0 <= self.obscuration_ratio < 1.0):
            raise ValueError(
                f"CircularAperture '{self.name}': obscuration_ratio = "
                f"{self.obscuration_ratio} is invalid. Must satisfy "
                "0 ≤ ε < 1 (0 for unobscured; 1 would be a fully-blocked "
                "pupil)."
            )
        width_bad = not math.isfinite(self.spider_width_m) or self.spider_width_m < 0.0
        if self.n_spiders < 0 or width_bad:
            raise ValueError(
                f"CircularAperture '{self.name}': n_spiders = {self.n_spiders}, "
                f"spider_width_m = {self.spider_width_m} are invalid. Both must "
                "be ≥ 0."
            )

    # ------------------------------------------------------------------
    # Derived quantities
    # ------------------------------------------------------------------

    @property
    def primary_area_m2(self) -> float:
        """Geometric primary area ``π D² / 4`` [m²]."""
        return math.pi * (self.aperture_diameter_m / 2.0) ** 2

    @property
    def clear_area_m2(self) -> float:
        """Clear area after removing the obscuration and spider arms [m²].

        ``A_clear = (π/4) · D² · (1 − ε²) − A_spiders`` where
        ``A_spiders ≈ n · width · (D/2 − D_secondary/2)`` is the radial
        strut area between the secondary edge and the primary rim, per
        RADIANT_Optics.md §3.2–3.3. Struts crossing the obscuration are
        not double-counted (the length runs from the secondary rim out).
        A_clear is floored at 0.
        """
        d = self.aperture_diameter_m
        eps = self.obscuration_ratio
        a_circ = (math.pi / 4.0) * d * d * (1.0 - eps * eps)
        if self.n_spiders <= 0 or self.spider_width_m <= 0.0:
            return a_circ
        strut_len = 0.5 * d * (1.0 - eps)  # secondary rim to primary rim
        a_spiders = self.n_spiders * self.spider_width_m * strut_len
        return max(0.0, a_circ - a_spiders)

    def solid_angle_at_focal_length(self, focal_length_m: float) -> float:
        """Approximate solid angle ``π / (4 · f/#²)`` [sr].

        This is the "ratio form" of the single-pixel étendue at the
        Nyquist pixel, equivalent to the small-angle approximation of
        the cone of light collected from an on-axis point source. For
        ``f/1`` this returns ``π/4`` (≈ 0.785 sr). For very slow
        systems (``f/∞``) the solid angle tends to zero.

        Parameters
        ----------
        focal_length_m:
            Effective focal length in metres. Must be ``> 0``.

        Returns
        -------
        float
            Solid angle in steradians.
        """
        if not math.isfinite(focal_length_m) or focal_length_m <= 0.0:
            raise ValueError(
                f"CircularAperture '{self.name}': focal_length_m = "
                f"{focal_length_m} is invalid for solid-angle computation. "
                "Must be a positive finite number in metres."
            )
        f_num = focal_length_m / self.aperture_diameter_m
        return math.pi / (4.0 * f_num * f_num)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "kind": "circular",
            "name": self.name,
            "aperture_diameter_m": float(self.aperture_diameter_m),
            "obscuration_ratio": float(self.obscuration_ratio),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CircularAperture:
        """Deserialize from a dict produced by :meth:`to_dict`."""
        if d.get("kind", "circular") != "circular":
            raise ValueError(
                f"CircularAperture.from_dict: expected kind='circular', got {d.get('kind')!r}."
            )
        return cls(
            aperture_diameter_m=float(d["aperture_diameter_m"]),
            obscuration_ratio=float(d.get("obscuration_ratio", 0.0)),
            name=str(d.get("name", "circular_aperture")),
        )
