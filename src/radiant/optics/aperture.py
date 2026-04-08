"""Aperture geometry and ``f/#`` consistency helpers.

Implements the geometric portion of ``docs/RADIANT_Optics.md`` §3
for the 2B.3 scalar-mode cut: a circular aperture with optional central
obscuration, and a consistency group over ``{aperture_diameter_m,
focal_length_m, f_number}``. Wavefront error, spiders, apodization,
pupil mask generation, and the full ``OpticsState`` contract are
deferred to later tasks.

All lengths are in SI metres. ``f_number`` is dimensionless.

The solid angle a single square pixel subtends when seen from the
aperture is::

    Ω_pixel = pixel_area / focal_length²   [sr]

and the single-pixel étendue that drives the extended-source signal
equation is::

    Ω_pupil ≈ π / (4 · f/#²)               [sr]

the latter being the "ratio form" that falls out of ``A_collect × Ω_pixel``
when ``A_collect = π D² / 4`` and ``Ω_pixel = (p / f)²`` are rearranged
at the Nyquist pixel. See §7.1 of the optics document for the signal
étendue bookkeeping.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Consistency group for (diameter, focal_length, f_number)
# ---------------------------------------------------------------------------

# Fractional tolerance at which the consistency group accepts the user
# over-specifying two entries plus a derivable third. Chosen to match
# MODTRAN-style rounding in datasheets (~0.1 %).
FNUMBER_CONSISTENCY_RTOL: float = 1e-3


def resolve_fnumber_group(
    aperture_diameter_m: float | None,
    focal_length_m: float | None,
    f_number: float | None,
) -> tuple[float, float, float]:
    """Resolve the ``(D, f, f/#)`` consistency group.

    Exactly two of the three inputs must be provided; the third is
    derived from ``f/# = f / D``. If all three are provided, they must
    be mutually consistent to within ``FNUMBER_CONSISTENCY_RTOL``.

    Parameters
    ----------
    aperture_diameter_m:
        Clear entrance-pupil diameter in metres. ``> 0`` if provided.
    focal_length_m:
        Effective focal length in metres. ``> 0`` if provided.
    f_number:
        Dimensionless ``f/#``. ``> 0`` if provided.

    Returns
    -------
    (aperture_diameter_m, focal_length_m, f_number)
        The resolved triple, all positive floats.

    Raises
    ------
    ValueError
        If fewer than two inputs are supplied; if any supplied input
        is non-positive; or if all three are supplied but disagree by
        more than ``FNUMBER_CONSISTENCY_RTOL``.
    """
    # Positivity check on whatever was supplied.
    for name, val in (
        ("aperture_diameter_m", aperture_diameter_m),
        ("focal_length_m", focal_length_m),
        ("f_number", f_number),
    ):
        if val is not None and (not math.isfinite(val) or val <= 0.0):
            raise ValueError(
                f"resolve_fnumber_group: {name} = {val} is invalid. "
                f"Must be a positive finite number."
            )

    supplied = sum(v is not None for v in (aperture_diameter_m, focal_length_m, f_number))
    if supplied < 2:
        raise ValueError(
            "resolve_fnumber_group: at least two of "
            "{aperture_diameter_m, focal_length_m, f_number} must be supplied. "
            "The third is derived from f/# = focal_length_m / aperture_diameter_m."
        )

    if supplied == 2:
        if aperture_diameter_m is None:
            assert focal_length_m is not None and f_number is not None
            aperture_diameter_m = focal_length_m / f_number
        elif focal_length_m is None:
            assert aperture_diameter_m is not None and f_number is not None
            focal_length_m = aperture_diameter_m * f_number
        else:
            assert aperture_diameter_m is not None and focal_length_m is not None
            f_number = focal_length_m / aperture_diameter_m
        return float(aperture_diameter_m), float(focal_length_m), float(f_number)

    # All three supplied — verify consistency.
    assert aperture_diameter_m is not None and focal_length_m is not None and f_number is not None
    derived = focal_length_m / aperture_diameter_m
    if not math.isclose(derived, f_number, rel_tol=FNUMBER_CONSISTENCY_RTOL):
        raise ValueError(
            f"resolve_fnumber_group: over-specified and inconsistent. "
            f"focal_length_m / aperture_diameter_m = "
            f"{focal_length_m} / {aperture_diameter_m} = {derived:.6f}, "
            f"but f_number = {f_number:.6f} "
            f"(relative discrepancy "
            f"{abs(derived - f_number) / f_number:.2e} > "
            f"{FNUMBER_CONSISTENCY_RTOL:.0e}). "
            "Remove one of the three inputs or fix the mismatch."
        )
    return float(aperture_diameter_m), float(focal_length_m), float(f_number)


# ---------------------------------------------------------------------------
# CircularAperture
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CircularAperture:
    """Circular clear aperture with optional central obscuration.

    Implements the scalar-mode slice of RADIANT_Optics.md §3.1–3.2:
    unapodized, no spiders, no pupil mask. Spiders, apodization, and
    the full ``PupilDescription`` are deferred to later tasks.

    Parameters
    ----------
    aperture_diameter_m:
        Primary clear-aperture diameter in metres. Must be ``> 0``.
    obscuration_ratio:
        ``D_secondary / D_primary``. Must satisfy ``0 ≤ ε < 1``. An
        obscuration ratio of ``1`` (or greater) is unphysical — the
        secondary would occupy the entire aperture.
    name:
        Optional human-readable label for provenance/logging.
    """

    aperture_diameter_m: float
    obscuration_ratio: float = 0.0
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

    # ------------------------------------------------------------------
    # Derived quantities
    # ------------------------------------------------------------------

    @property
    def primary_area_m2(self) -> float:
        """Geometric primary area ``π D² / 4`` [m²]."""
        return math.pi * (self.aperture_diameter_m / 2.0) ** 2

    @property
    def clear_area_m2(self) -> float:
        """Clear area after removing the central obscuration [m²].

        ``A_clear = (π/4) · D² · (1 − ε²)`` per RADIANT_Optics.md §3.2.
        """
        d = self.aperture_diameter_m
        eps = self.obscuration_ratio
        return (math.pi / 4.0) * d * d * (1.0 - eps * eps)

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
