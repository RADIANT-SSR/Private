"""Authoritative ADR-0006 input-mode manifest: family → modes → parameters.

The Geometry stage resolves the scene by **input mode** (ADR-0006 /
``RADIANT_Geometry.md``): the viewing geometry in one of V0–V4, the solar
geometry in one of S1–S3 (or night), and the platform kinematics as a direct
ground speed or a circular orbit (V6). Detection is by **provenance** — there
is no mode-switch parameter. That structure is *executed* by the resolver
chains in :mod:`radiant.geometry.modes`; this module states it as **data** so
non-physics layers (the GUI's Geometry screen, through the
:mod:`radiant.api.geometry_modes` bridge) can enumerate it without transcribing
it (CU-120 / Gap 70 one-source hygiene).

The manifest is hand-maintained next to the resolvers it describes; it cannot
drift silently because ``tests/test_mode_manifest.py`` proves, mode by mode,
that setting exactly that mode's parameter(s) makes the corresponding
``resolve_*`` select it and :func:`active_mode_key` report it, and reconciles
the grouping against the ``mode_entry`` / ``solar_site`` tags in
:mod:`radiant.geometry._schema`.

Display strings (family titles, mode labels) are deliberately absent — they
are view-layer concerns and live with the GUI (which keeps *only* those).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

# ---------------------------------------------------------------------------
# The three mode families (viewing / solar / kinematics)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GeometryMode:
    """One input mode within a family — a labelled door onto the canonical value.

    Attributes
    ----------
    key:
        Short mode id from the geometry doc (``"V2"``, ``"S3"``, ``"circular"``).
    params:
        The schema dot-path(s) this mode exposes as inputs. Empty for a mode
        that carries no field of its own.
    """

    key: str
    params: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GeometryModeFamily:
    """A selector: one canonical quantity, several mutually-preferred input modes.

    Attributes
    ----------
    key:
        Family id (``"viewing"`` / ``"solar"`` / ``"kinematics"``) — matches the
        ``*_mode`` stage-output family and the disagreement-error family word.
    anchor_params:
        Dot-path(s) that apply in **every** mode of this family (always
        settable), e.g. the sensor/target altitudes that anchor every viewing
        triangle.
    modes:
        The ordered input modes; exactly one is "active" at a time.
    default_mode_key:
        The mode the family sits in when no mode-entry parameter is user-set
        (the documented default door: nadir view, direct solar zenith, …).
    """

    key: str
    anchor_params: tuple[str, ...]
    modes: tuple[GeometryMode, ...]
    default_mode_key: str


VIEWING_FAMILY: Final[GeometryModeFamily] = GeometryModeFamily(
    key="viewing",
    anchor_params=("geometry.sensor_altitude_m", "geometry.target_altitude_m"),
    modes=(
        GeometryMode("V1", ("geometry.path_zenith_rad",)),
        GeometryMode("V2", ("geometry.sensor_off_nadir_rad",)),
        GeometryMode("V3", ("geometry.ground_range_m",)),
        GeometryMode("V4", ("geometry.elevation_angle_rad",)),
        GeometryMode("V0", ("geometry.target_range_m",)),
    ),
    default_mode_key="V1",
)

SOLAR_FAMILY: Final[GeometryModeFamily] = GeometryModeFamily(
    key="solar",
    anchor_params=("geometry.solar_illumination", "geometry.solar_azimuth_rad"),
    modes=(
        GeometryMode("S1", ("geometry.solar_zenith_rad",)),
        GeometryMode("S2", ("geometry.solar_elevation_rad",)),
        GeometryMode(
            "S3",
            (
                "geometry.site_latitude_rad",
                "geometry.day_of_year",
                "geometry.local_solar_time_h",
                "geometry.ltan_h",
            ),
        ),
    ),
    default_mode_key="S1",
)

KINEMATICS_FAMILY: Final[GeometryModeFamily] = GeometryModeFamily(
    key="kinematics",
    anchor_params=(),
    modes=(
        GeometryMode("direct", ("geometry.ground_speed_m_s",)),
        GeometryMode("circular", ("geometry.circular_orbit",)),
    ),
    default_mode_key="direct",
)

MODE_FAMILIES: Final[tuple[GeometryModeFamily, ...]] = (
    VIEWING_FAMILY,
    SOLAR_FAMILY,
    KINEMATICS_FAMILY,
)


def all_mode_params() -> tuple[str, ...]:
    """Every geometry dot-path the manifest names (anchors + mode fields).

    A view layer asserts each of these exists in the live schema at build time,
    so a schema rename/removal fails loudly rather than silently dropping a
    field; the coverage test proves the set equals the schema's input-mode
    parameters.
    """
    seen: list[str] = []
    for family in MODE_FAMILIES:
        for dotpath in family.anchor_params:
            if dotpath not in seen:
                seen.append(dotpath)
        for mode in family.modes:
            for dotpath in mode.params:
                if dotpath not in seen:
                    seen.append(dotpath)
    return tuple(seen)


# ---------------------------------------------------------------------------
# Active-mode detection (the display-side view of the resolvers' provenance
# detection — the same door-priority order radiant.geometry.modes applies)
# ---------------------------------------------------------------------------


def active_mode_key(
    family: GeometryModeFamily,
    is_provided: Callable[[str], bool],
    get_value: Callable[[str], Any],
) -> str:
    """The mode *family* currently sits in, decided from provenance.

    Mirrors the detection order in :mod:`radiant.geometry.modes` (proved by the
    per-mode round-trip test in ``tests/test_mode_manifest.py``):

    * **viewing** — the first user-set door among V2/V3/V4/V1, else V0 if only a
      direct range is set, else the default (V1, nadir).
    * **solar** — night when illumination is ``"night"``; else the first user-set
      door among S2/S3/S1, else the default (S1).
    * **kinematics** — circular when ``circular_orbit`` is set true, else direct.

    Parameters
    ----------
    is_provided:
        ``dotpath -> bool`` — True when the parameter resolved from an explicit
        input (provenance is not DEFAULT), so the detection matches the stage's
        own (ADR-0006 rule 1: defaults are inert).
    get_value:
        ``dotpath -> value`` — the resolved input value (used only for the night
        toggle and the circular-orbit flag).
    """
    if family.key == "viewing":
        for mode_key in ("V2", "V3", "V4", "V1"):
            mode = _mode(family, mode_key)
            if any(is_provided(p) for p in mode.params):
                return mode_key
        if is_provided("geometry.target_range_m"):
            return "V0"
        return family.default_mode_key
    if family.key == "solar":
        if str(get_value("geometry.solar_illumination")) == "night":
            return "night" if _has_mode(family, "night") else family.default_mode_key
        for mode_key in ("S2", "S3", "S1"):
            mode = _mode(family, mode_key)
            if any(is_provided(p) for p in mode.params):
                return mode_key
        return family.default_mode_key
    if family.key == "kinematics":
        if bool(get_value("geometry.circular_orbit")):
            return "circular"
        return "direct"
    return family.default_mode_key  # pragma: no cover - families are closed


def _mode(family: GeometryModeFamily, key: str) -> GeometryMode:
    for mode in family.modes:
        if mode.key == key:
            return mode
    raise KeyError(key)  # pragma: no cover - keys are internal constants


def _has_mode(family: GeometryModeFamily, key: str) -> bool:
    return any(mode.key == key for mode in family.modes)


__all__ = [
    "GeometryMode",
    "GeometryModeFamily",
    "VIEWING_FAMILY",
    "SOLAR_FAMILY",
    "KINEMATICS_FAMILY",
    "MODE_FAMILIES",
    "all_mode_params",
    "active_mode_key",
]
