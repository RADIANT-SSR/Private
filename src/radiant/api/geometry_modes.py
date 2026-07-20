"""Public API surface for the ADR-0006 geometry input-mode manifest (CU-120).

Re-exports the family → mode → parameter structure from
:mod:`radiant.geometry.mode_manifest` so that view layers — the GUI, the CLI —
can enumerate the viewing / solar / kinematics input modes and detect which
door a sensor currently sits in without importing a physics stage directly
(the import-linter contract forbids ``radiant.gui`` → ``radiant.geometry``;
``radiant.api`` is the sanctioned bridge, the same precedent as
:mod:`radiant.api.metric_groups`). The GUI's Geometry screen builds its mode
selectors from :data:`MODE_FAMILIES` and keeps only display labels of its own.
"""

from __future__ import annotations

from radiant.geometry.mode_manifest import (
    KINEMATICS_FAMILY,
    MODE_FAMILIES,
    SOLAR_FAMILY,
    VIEWING_FAMILY,
    GeometryMode,
    GeometryModeFamily,
    active_mode_key,
    all_mode_params,
)

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
