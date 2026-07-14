"""Physics-domain glyph palette — the scene's semantic color layer (ADR-0007 §8.5).

This is the **one** module under ``radiant.gui`` allowed to hold color literals outside
``themes/`` (ADR-0007 §3; the token-discipline test in ``tests/test_theme.py``
allowlists exactly this file). The colors here are **not chrome** — they encode
*physical meaning* and are stable across the light/dark app theme:

* **sun = amber**, **sensor/satellite = blue**, **surface normal = green**,
  **target body = teal**, **phase/target-vector = desaturated teal** — the mockup's
  physics color roles (ADR-0007 §3, ``radiant_geometry_handoff.md`` §7).
* the point-source annotation accent, the sun-disc fill, the satellite face fill, and
  the contact-shadow black are the glyph fills those roles render with.

Chrome that *must* follow the app theme (viewport background, grid, axes, leader/label
pill) is resolved from the active :class:`~radiant.gui.themes.tokens.Theme` in the
schematic canvas (:mod:`radiant.gui.viewer.schematic_view`) — it is **not** here. Keeping
the two apart is what lets the Phase-9 theme toggle restyle the viewport without touching
these semantic constants (ADR-0007 §3).

This is the sole surviving module of the retired VTK scene library (CU-132); the 2D
``QPainter`` schematic imports these glyph-colour constants directly. Every value is a
verbatim carry-over from the prototype ``scene/style.py`` (hues unchanged) so the glyphs
render identically to the mockup.
"""

from __future__ import annotations

from typing import Final

# -- Target body (teal) ---------------------------------------------------------
TARGET_COLOR: Final[str] = "#2EC4B6"
TARGET_PBR_DIFFUSE_COLOR: Final[str] = TARGET_COLOR

# -- Geometric vector families (semantic hues) ----------------------------------
SATELLITE_FAMILY: Final[str] = "#3A6FAA"  # muted blue: satellite + boresight
SURFACE_FAMILY: Final[str] = "#3A8A66"  # muted green: n_B, surface normals
SOLAR_FAMILY: Final[str] = "#C28A1F"  # muted amber: s_t, s_B, sun glyph
TARGET_VECTOR_FAMILY: Final[str] = "#5E8F8B"  # desaturated teal: phase-angle family
# Azimuth / phase arc family — a deeper magenta, matching the mockup ``scene.jsx``
# ``phi`` role (arch §6.4: "phase/azimuth = magenta"). Semantic (which angle family),
# stable across the app theme — belongs here, not in the chrome layer.
AZIMUTH_FAMILY: Final[str] = "#A8358C"

# -- Annotation accent (point-source marker) ------------------------------------
# The point-source crosshair renders in this orange so the regime annotation reads as
# a deliberate marker distinct from the teal target and the ground grid.
ACCENT_COLOR: Final[str] = "#FF6B35"

# -- Target body-frame RPY triad (Part B) ---------------------------------------
# The on-target orientation gizmo color-codes its three body axes so the user reads
# roll/pitch/yaw at a glance (ADR-0007 §8.5, arch doc §6.2: pink=Roll, green=Pitch,
# purple=Yaw). These are *semantic* physics colors (which body axis is which), stable
# across the app theme — they belong here, not in the theme chrome layer.
BODY_AXIS_ROLL_COLOR: Final[str] = "#E56B9A"  # pink: roll (body +X, longitudinal)
BODY_AXIS_PITCH_COLOR: Final[str] = "#4FB07A"  # green: pitch (body +Y, lateral)
BODY_AXIS_YAW_COLOR: Final[str] = "#8E6FC7"  # purple: yaw (body +Z, vertical)

# -- Glyph fills ----------------------------------------------------------------
# Sun disc: a slightly brighter amber than ``SOLAR_FAMILY`` (same hue, lifted
# lightness) so the disc body stands out from its rays.
SUN_DISC_FILL: Final[str] = "#E5A732"
# Satellite diamond face — white, outlined in ``SATELLITE_FAMILY``.
OBSERVER_FILL: Final[str] = "#FFFFFF"
# Contact-shadow disc under the target body (neutral black, theme-independent).
CONTACT_SHADOW_COLOR: Final[str] = "#000000"


__all__ = [
    "TARGET_COLOR",
    "TARGET_PBR_DIFFUSE_COLOR",
    "SATELLITE_FAMILY",
    "SURFACE_FAMILY",
    "SOLAR_FAMILY",
    "TARGET_VECTOR_FAMILY",
    "AZIMUTH_FAMILY",
    "ACCENT_COLOR",
    "BODY_AXIS_ROLL_COLOR",
    "BODY_AXIS_PITCH_COLOR",
    "BODY_AXIS_YAW_COLOR",
    "SUN_DISC_FILL",
    "OBSERVER_FILL",
    "CONTACT_SHADOW_COLOR",
]
