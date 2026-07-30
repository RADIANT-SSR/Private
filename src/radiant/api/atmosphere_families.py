"""Public accessor for the bundled interpolated-atmosphere family catalogue (CU-239).

The GUI may import :mod:`radiant.api` and :mod:`radiant.core` only, never a
physics package, so a family *picker* cannot read
:data:`radiant.atmosphere.interpolation_coverage.SHIPPED_FAMILIES` directly.
This module is the seam — the same one-GUI-action ↔ one-API-call pattern
:meth:`radiant.api.sensor.Sensor.validate_target_spec` established for CU-244.

The catalogue is what turns ``atmosphere.interpolation_axes`` from a free-text
field the operator has to reconstruct by hand into a closed, enumerable choice:
each row carries the exact axes string to write, the LOS direction it serves,
the atmosphere profile it was rendered with, and a plain-language coverage line
whose numbers always carry units (km, degrees).
"""

from __future__ import annotations

from radiant.atmosphere.interpolation_coverage import (
    SHIPPED_FAMILIES as _SHIPPED_FAMILIES,
)
from radiant.atmosphere.interpolation_coverage import (
    ShippedFamily,
    family_for,
    recommended_axes,
)

__all__ = [
    "ShippedFamily",
    "shipped_atmosphere_families",
    "shipped_family_for_axes",
    "suggested_interpolation_axes",
]


def shipped_atmosphere_families() -> tuple[ShippedFamily, ...]:
    """Every bundled interpolation family, in catalogue order.

    Each :class:`~radiant.atmosphere.interpolation_coverage.ShippedFamily`
    exposes ``name``, ``los_direction``, ``interpolation_axes`` (the exact
    string to write), ``profile``, ``coverage`` (units explicit) and a
    ``summary`` one-liner suitable as a picker label.
    """
    return _SHIPPED_FAMILIES


def shipped_family_for_axes(los_direction: str, interpolation_axes: str) -> ShippedFamily | None:
    """The family a ``(direction, axes)`` pair selects, or ``None`` if unshipped."""
    return family_for(los_direction, interpolation_axes)


def suggested_interpolation_axes(
    los_direction: str, target_altitude_m: float, path_zenith_rad: float
) -> str | None:
    """The ``interpolation_axes`` string a shipped family covers for this scene.

    A recommendation only — callers write the parameter themselves, because
    adopting a family can change the run's atmosphere profile (the
    ``profile`` field says which one, and
    :func:`radiant.atmosphere.interpolation_coverage.profile_change_warning`
    renders the caveat). ``None`` when no shipped family serves the geometry.
    """
    return recommended_axes(los_direction, target_altitude_m, path_zenith_rad)
