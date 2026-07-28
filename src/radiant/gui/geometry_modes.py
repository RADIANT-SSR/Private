"""Stage-0 input-mode view helpers for the Geometry screen (GUI plan Phase 5, §4.4).

The Geometry stage resolves the scene by **input mode** (ADR-0006 /
``RADIANT_Geometry.md`` §2): the user expresses the viewing geometry in one of
V0–V4, the solar geometry in one of S1–S3 (or night), and the platform
kinematics as direct-speed or a circular orbit. Detection is by **provenance** —
there is no mode-switch parameter — so the GUI's mode selector is a *view* over
that structure, not a new degree of freedom.

**One source (CU-120).** The family → mode → parameter structure itself is owned
by :mod:`radiant.geometry.mode_manifest` and consumed here through the public
:mod:`radiant.api.geometry_modes` bridge (the Gap 96 ``metric_groups``
precedent) — nothing about the grouping, the default doors, or the active-mode
detection order is transcribed in the GUI anymore. This module keeps only what
is genuinely view-layer:

* :data:`FAMILY_TITLES` / :data:`MODE_LABELS` — the human wording for each
  family and mode key (checked complete against the manifest at import, so a
  new mode added in ``radiant.geometry`` fails loudly here until it gets a
  label);
* :func:`implicated_families` — which family(ies) a
  :class:`~radiant.geometry.errors.GeometrySpecificationError` names, so the
  screen can highlight the offending selector (Phase 5 task 3).

Everything a field actually *shows* (value, unit, bounds, description, editor
kind) is read from the live schema via :meth:`Sensor.parameter_def` — never
transcribed (Gap 70). :func:`all_mode_params` (re-exported from the manifest)
lets the form assert at build time that every dot-path still exists in the
schema.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from radiant.api.geometry_modes import (
    KINEMATICS_FAMILY,
    LOS_RATE_FAMILY,
    MODE_FAMILIES,
    SOLAR_FAMILY,
    VIEWING_FAMILY,
    GeometryMode,
    GeometryModeFamily,
    active_mode_key,
    all_mode_params,
)

# ---------------------------------------------------------------------------
# Display wording (the only mode knowledge that lives GUI-side)
# ---------------------------------------------------------------------------

FAMILY_TITLES: Final[Mapping[str, str]] = {
    "viewing": "Viewing geometry",
    "solar": "Solar geometry",
    "kinematics": "Platform kinematics",
    "los_rate": "Line-of-sight rate",
}

MODE_LABELS: Final[Mapping[str, str]] = {
    # Viewing labels name the *direction-general* door (ADR-0011 decision 3):
    # every entered viewing angle is read at the path's LOWER endpoint, and the
    # reference axis is resolved from the altitudes, never declared. The labels
    # stay short — the ζ_low ↔ θ_o relationship and the axis resolution are the
    # schema description the editor dialog shows, not combo text.
    "V1": "Path zenith at lower endpoint (V1)",
    "V2": "Off-boresight angle (V2)",
    "V3": "Ground range (V3)",
    "V4": "Elevation angle, signed (V4)",
    "V0": "Direct slant range (V0)",
    "S1": "Solar zenith θ_s (S1)",
    "S2": "Solar elevation (S2)",
    "S3": "Site + time (S3)",
    "direct": "Direct ground speed",
    "circular": "Circular orbit (V6)",
    "K0": "Platform motion only (derived)",
    "K1": "Direct LOS rate (K1)",
    "K2": "Target velocity (K2)",
}

# Import-time drift guard (developer invariant, not user input): a mode or
# family added to the manifest without wording here must fail the GUI import
# loudly, not render a blank selector entry.
_UNLABELLED: Final[tuple[str, ...]] = tuple(
    mode.key for family in MODE_FAMILIES for mode in family.modes if mode.key not in MODE_LABELS
)
_UNTITLED: Final[tuple[str, ...]] = tuple(
    family.key for family in MODE_FAMILIES if family.key not in FAMILY_TITLES
)
assert not _UNLABELLED, f"geometry modes without a GUI label: {_UNLABELLED}"
assert not _UNTITLED, f"geometry families without a GUI title: {_UNTITLED}"


def family_title(family_key: str) -> str:
    """The selector heading for *family_key* (KeyError on an unknown family)."""
    return FAMILY_TITLES[family_key]


def mode_label(mode_key: str) -> str:
    """The combo label for *mode_key* (KeyError on an unknown mode)."""
    return MODE_LABELS[mode_key]


# ---------------------------------------------------------------------------
# Error → implicated family (for the conflict highlight, Phase 5 task 3)
# ---------------------------------------------------------------------------


# Every geometry parameter (and the short context keys the stage's errors use) →
# the family whose selector the GUI highlights when that key appears in a
# GeometrySpecificationError's context. Built from the manifest so it cannot
# drift from the family grouping; the short keys are the ones
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
    "LOS_RATE_FAMILY",
    "MODE_FAMILIES",
    "FAMILY_TITLES",
    "MODE_LABELS",
    "family_title",
    "mode_label",
    "all_mode_params",
    "active_mode_key",
    "implicated_families",
]
