"""Stage-0 input-mode manifest for the Geometry screen (GUI plan Phase 5, §4.4).

The Geometry stage resolves the scene by **input mode** (ADR-0006 /
``RADIANT_Geometry.md`` §2): the user expresses the viewing geometry in one of
V0–V4, the solar geometry in one of S1–S3 (or night), and the platform
kinematics as direct-speed or a circular orbit. Detection is by **provenance** —
there is no mode-switch parameter — so the GUI's mode selector is a *view* over
that structure, not a new degree of freedom.

This module is the single **Qt-free** source of that structure:

* :data:`MODE_FAMILIES` — the three families, each a selector with its ordered
  modes and the schema dot-path(s) each mode's field(s) expose.
* :func:`active_mode_key` — which mode a loaded sensor currently sits in, decided
  from provenance exactly as :mod:`radiant.geometry.modes` decides it (so the
  selector reflects the config, never guesses).
* :func:`implicated_families` — which family(ies) a
  :class:`~radiant.geometry.errors.GeometrySpecificationError` names, so the
  screen can highlight the offending selector (Phase 5 task 3).

**What is transcribed here vs. schema-driven.** The mode → dot-path *grouping*
(which parameter is the V2 door) is architectural knowledge from ADR-0006; the
GUI cannot import ``radiant.geometry`` (import rules), so the grouping is named
here — the same precedent as the geometry-readout key→symbol map. Everything a
field actually *shows* (value, unit, bounds, description, editor kind) is read
from the live schema via :meth:`Sensor.parameter_def` — never transcribed (Gap
70). :func:`all_mode_params` lists every dot-path the manifest names so the form
can assert, at build time, that each still exists in the schema (drift guard);
the coupling to the dot-path spelling is tracked as a CU.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
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
    label:
        Human label shown in the selector.
    params:
        The schema dot-path(s) this mode exposes as editable fields. Empty for a
        mode that carries no field of its own (the nadir/default viewing door).
    """

    key: str
    label: str
    params: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GeometryModeFamily:
    """A selector: one canonical quantity, several mutually-preferred input modes.

    Attributes
    ----------
    key:
        Family id (``"viewing"`` / ``"solar"`` / ``"kinematics"``) — matches the
        ``*_mode`` stage-output family and the disagreement-error family word.
    title:
        Human heading for the selector.
    anchor_params:
        Dot-path(s) that apply in **every** mode of this family (always editable),
        e.g. the sensor/target altitudes that anchor every viewing triangle.
    modes:
        The ordered input modes; exactly one is "active" at a time.
    default_mode_key:
        The mode the selector shows when no mode-entry parameter is user-set
        (the documented default door: nadir view, direct solar zenith, …).
    """

    key: str
    title: str
    anchor_params: tuple[str, ...]
    modes: tuple[GeometryMode, ...]
    default_mode_key: str


VIEWING_FAMILY: Final[GeometryModeFamily] = GeometryModeFamily(
    key="viewing",
    title="Viewing geometry",
    anchor_params=("geometry.sensor_altitude_m", "geometry.target_altitude_m"),
    modes=(
        GeometryMode("V1", "Path zenith θ_o (V1)", ("geometry.path_zenith_rad",)),
        GeometryMode("V2", "Off-nadir angle η (V2)", ("geometry.sensor_off_nadir_rad",)),
        GeometryMode("V3", "Ground range (V3)", ("geometry.ground_range_m",)),
        GeometryMode("V4", "Elevation angle (V4)", ("geometry.elevation_angle_rad",)),
        GeometryMode("V0", "Direct slant range (V0)", ("geometry.target_range_m",)),
    ),
    default_mode_key="V1",
)

SOLAR_FAMILY: Final[GeometryModeFamily] = GeometryModeFamily(
    key="solar",
    title="Solar geometry",
    anchor_params=("geometry.solar_illumination", "geometry.solar_azimuth_rad"),
    modes=(
        GeometryMode("S1", "Solar zenith θ_s (S1)", ("geometry.solar_zenith_rad",)),
        GeometryMode("S2", "Solar elevation (S2)", ("geometry.solar_elevation_rad",)),
        GeometryMode(
            "S3",
            "Site + time (S3)",
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
    title="Platform kinematics",
    anchor_params=(),
    modes=(
        GeometryMode("direct", "Direct ground speed", ("geometry.ground_speed_m_s",)),
        GeometryMode("circular", "Circular orbit (V6)", ("geometry.circular_orbit",)),
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

    The form asserts each of these exists in ``sensor.parameter_defs()`` at build
    time, so a schema rename/removal fails loudly here rather than silently
    dropping a field (the drift guard the module docstring describes).
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
# Active-mode detection (mirrors radiant.geometry.modes, by provenance)
# ---------------------------------------------------------------------------


def active_mode_key(
    family: GeometryModeFamily,
    is_provided: Callable[[str], bool],
    get_value: Callable[[str], Any],
) -> str:
    """The mode *family* currently sits in, decided from provenance.

    Mirrors the detection order in :mod:`radiant.geometry.modes`:

    * **viewing** — the first user-set door among V2/V3/V4/V1, else V0 if only a
      direct range is set, else the default (V1, nadir).
    * **solar** — night when illumination is ``"night"``; else the first user-set
      door among S2/S3/S1, else the default (S1).
    * **kinematics** — circular when ``circular_orbit`` is set true, else direct.

    Parameters
    ----------
    is_provided:
        ``dotpath -> bool`` — True when the parameter resolved from an explicit
        input (provenance is not DEFAULT). The GUI supplies this from the public
        provenance seam so the detection matches the stage's own.
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


# ---------------------------------------------------------------------------
# Error → implicated family (for the conflict highlight, Phase 5 task 3)
# ---------------------------------------------------------------------------


# Every geometry parameter (and the short context keys the stage's errors use) →
# the family whose selector the GUI highlights when that key appears in a
# GeometrySpecificationError's context. Built from the manifest so it cannot
# drift from the family grouping above; the short keys are the ones
# radiant.geometry.modes puts in a context dict that are not full dot-paths.
def _param_family_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for family in MODE_FAMILIES:
        for dotpath in (*family.anchor_params, *(p for m in family.modes for p in m.params)):
            mapping[dotpath] = family.key
            mapping[dotpath.split(".", 1)[1]] = family.key  # short (no "geometry.")
    # Extra short keys the stage's error contexts carry that are not parameters.
    mapping["implied_slant_range_m"] = "viewing"
    mapping["derived_m_s"] = "kinematics"
    mapping["explicit_m_s"] = "kinematics"
    return mapping


_PARAM_FAMILY: Final[Mapping[str, str]] = _param_family_map()

# Family-name words the stage puts in an error's `what` sentence, as a fallback
# when the context keys alone do not localise the family.
_WHAT_KEYWORDS: Final[tuple[tuple[str, str], ...]] = (
    ("viewing", "viewing"),
    ("solar", "solar"),
    ("ground-track", "kinematics"),
    ("circular_orbit", "kinematics"),
)


def implicated_families(what: str, context: Mapping[str, Any] | None) -> set[str]:
    """The family key(s) a geometry error names — the selector(s) to highlight.

    Reads the error's structured ``context`` keys first (each maps to a family via
    the manifest), then falls back to family words in the ``what`` sentence. Returns
    every implicated family (a range-vs-angle conflict is viewing; an ltan/lst
    conflict is solar; a circular-orbit speed conflict is kinematics), or an empty
    set for an error this screen does not localise.
    """
    families: set[str] = set()
    if context:
        for key in context:
            family = _PARAM_FAMILY.get(key) or _PARAM_FAMILY.get(str(key).split(".", 1)[-1])
            if family is not None:
                families.add(family)
    if not families:
        lowered = what.lower()
        for needle, family in _WHAT_KEYWORDS:
            if needle in lowered:
                families.add(family)
    return families


__all__ = [
    "GeometryMode",
    "GeometryModeFamily",
    "VIEWING_FAMILY",
    "SOLAR_FAMILY",
    "KINEMATICS_FAMILY",
    "MODE_FAMILIES",
    "all_mode_params",
    "active_mode_key",
    "implicated_families",
]
