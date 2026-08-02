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

from radiant.atmosphere.errors import is_coverage_refusal as _is_coverage_refusal
from radiant.atmosphere.family_suitability import (
    AtmosphereFamilySuggestion,
    FamilyGap,
)
from radiant.atmosphere.interpolation_coverage import (
    BUNDLED_FAMILIES as _BUNDLED_FAMILIES,
)
from radiant.atmosphere.interpolation_coverage import (
    ShippedFamily,
    family_for,
    recommended_axes,
)

__all__ = [
    "AtmosphereFamilySuggestion",
    "FamilyGap",
    "ShippedFamily",
    "is_atmosphere_coverage_refusal",
    "shipped_atmosphere_families",
    "shipped_family_for_axes",
    "suggested_interpolation_axes",
]


def is_atmosphere_coverage_refusal(exc: BaseException) -> bool:
    """True when *exc* is an atmosphere **coverage** refusal, not a bad parameter.

    The seam a message surface routes on (CU-322). A coverage refusal says the
    configured atmosphere backend holds no measured column for this scene: the
    scene is legal, the inputs are legal, and the remedy is a different family or
    ``atmosphere.model='simple'``. It belongs beside the atmosphere inputs as an
    advisory, never in a modal headed "Parameter Rejected / Cannot set …", which
    is the wording for an input the framework refused to accept.

    Structural, never message text — see
    :func:`radiant.atmosphere.errors.is_coverage_refusal` for the two ways an
    error qualifies. This is the published alias, because the GUI may import
    :mod:`radiant.api` and :mod:`radiant.core` only.
    """
    return _is_coverage_refusal(exc)


def shipped_atmosphere_families() -> tuple[ShippedFamily, ...]:
    """Every bundled interpolation family, in catalogue order.

    Each :class:`~radiant.atmosphere.interpolation_coverage.ShippedFamily`
    exposes ``name``, ``los_direction``, ``interpolation_axes`` (the exact
    string to write), ``profile``, ``coverage`` (units explicit) and a
    ``summary`` one-liner suitable as a picker label.

    Rows with ``explicit_dir_only = True`` are bundled families whose
    ``(direction, axes)`` signature another family already owns, so writing
    their ``interpolation_axes`` alone selects the *other* family: adopting one
    means writing ``bundled_dir`` into ``atmosphere.interpolated_data_dir`` as
    well. ``midlat_summer_boost_ladder`` is the only such row today — 24
    committed MODTRAN runs that no axes key could reach until this catalogue
    published them (ex-CU-296).
    """
    return _BUNDLED_FAMILIES


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
