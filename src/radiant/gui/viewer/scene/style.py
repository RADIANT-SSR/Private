"""Scene rendering-style constants — sizes, widths, opacities, shading flags.

Lifted from the prototype ``scene/style.py`` (PLAN_v2 §6), trimmed to the constants the
**static** Part-A subset consumes. Two changes from the prototype accompany the lift:

* **Colors moved out.** Semantic glyph colors now live in
  :mod:`radiant.gui.viewer.scene.palette` (the ADR-0007 §8.5 domain layer); theme-bound
  chrome (viewport background, leader lines, label pill) lives in
  :mod:`radiant.gui.viewer.scene.chrome` and is resolved from the app :class:`Theme`.
  The color *names* are re-exported here so the lifted glyph modules keep reading
  ``style.TARGET_COLOR`` etc. unchanged, but **this file holds no color literal** — the
  token-discipline test (``tests/test_theme.py``) requires it.
* **Part-B constants (angle arcs + RPY triad) lifted.** The angle-arc tube/tip dimensions
  and the body-axes triad length fraction / accent stroke return with the Part-B modules
  (``arcs/``, ``frames/``, ``highlight.py``). The view-cube and world-axes gnomon corner
  widgets stay behind — they are not part of the Part-B interaction scope.

Every numeric value is a verbatim carry-over so the lifted primitives render identically.
"""

from __future__ import annotations

from typing import Final

# Semantic glyph colors — re-exported from the palette so ``style.<NAME>`` keeps working
# in the lifted modules. The literals live only in ``palette.py`` (allowlisted).
from radiant.gui.viewer.scene.palette import (
    ACCENT_COLOR,
    BODY_AXIS_PITCH_COLOR,
    BODY_AXIS_ROLL_COLOR,
    BODY_AXIS_YAW_COLOR,
    CONTACT_SHADOW_COLOR,
    SATELLITE_FAMILY,
    SOLAR_FAMILY,
    SURFACE_FAMILY,
    TARGET_COLOR,
    TARGET_PBR_DIFFUSE_COLOR,
    TARGET_VECTOR_FAMILY,
)

# ---------------------------------------------------------------------------
# Target body (PBR shading knobs + opacity).
# ---------------------------------------------------------------------------
TARGET_OPACITY: Final[float] = 0.92
TARGET_PBR_METALLIC: Final[float] = 0.10
TARGET_PBR_ROUGHNESS: Final[float] = 0.45  # matches prototype TARGET_LIGHTING["roughness"]

# Faceted shapes set ``smooth_shading=False`` for sharp silhouettes; smooth shapes set
# it ``True`` so curvature reads as a continuous gradient.
FACETED_SMOOTH_SHADING: Final[bool] = False
SMOOTH_SHAPE_SMOOTH_SHADING: Final[bool] = True

# ---------------------------------------------------------------------------
# Glyph sizes (screen-space px).
# ---------------------------------------------------------------------------
SAT_GLYPH_SIZE: Final[int] = 7

# ---------------------------------------------------------------------------
# Leader lines + anchor dots (label-to-anchor connectors).
# ---------------------------------------------------------------------------
LEADER_LINE_WIDTH: Final[float] = 1.0
LEADER_LINE_OPACITY: Final[float] = 0.85
LEADER_ANCHOR_DOT_RADIUS_PX: Final[float] = 1.5  # 3 px diameter
# Hard cap on label-to-anchor screen distance (the deconfliction solver runs first;
# this clamp runs last).
LABEL_MAX_ANCHOR_DISTANCE_PX: Final[float] = 240.0

# ---------------------------------------------------------------------------
# Ground grid (recede).
# ---------------------------------------------------------------------------
GRID_OPACITY: Final[float] = 0.45
GROUND_CAP_BASE_OPACITY: Final[float] = 0.20

# Contact-shadow disc (sits behind the target body).
CONTACT_SHADOW_OPACITY: Final[float] = 0.18
CONTACT_SHADOW_RADIUS_FACTOR: Final[float] = 1.05

# ---------------------------------------------------------------------------
# Angle-arc tube + arrowhead (Part B — ``arcs/``). The arc renders as a curved
# tube along the great circle between two unit vectors with a small cone tip.
# ---------------------------------------------------------------------------
ARC_TUBE_RADIUS_M: Final[float] = 0.022
ARC_TIP_HEIGHT_M: Final[float] = 0.16
ARC_TIP_RADIUS_M: Final[float] = 0.085
# Font size (screen px) of the numeric angle value pinned to a revealed arc.
ARC_VALUE_LABEL_FONT_SIZE: Final[int] = 13

# ---------------------------------------------------------------------------
# Target body-frame RPY triad (Part B — ``frames/body_axes.py``) + active-edit
# highlight stroke (``highlight.py``).
# ---------------------------------------------------------------------------
# Triad arm length as a fraction of the target's characteristic body length. > 1 so the
# gizmo protrudes clearly beyond the body silhouette rather than sitting inside it.
BODY_AXES_LENGTH_FRACTION: Final[float] = 1.6
# Minimum triad arm length (scene-m) so a tiny target still shows a legible gizmo.
BODY_AXES_MIN_LENGTH_M: Final[float] = 2.2
ACCENT_LINE_WIDTH: Final[float] = 2.5


__all__ = [
    # re-exported colors (defined in palette.py)
    "TARGET_COLOR",
    "TARGET_PBR_DIFFUSE_COLOR",
    "SATELLITE_FAMILY",
    "SURFACE_FAMILY",
    "SOLAR_FAMILY",
    "TARGET_VECTOR_FAMILY",
    "ACCENT_COLOR",
    "BODY_AXIS_ROLL_COLOR",
    "BODY_AXIS_PITCH_COLOR",
    "BODY_AXIS_YAW_COLOR",
    "CONTACT_SHADOW_COLOR",
    # numeric style constants
    "TARGET_OPACITY",
    "TARGET_PBR_METALLIC",
    "TARGET_PBR_ROUGHNESS",
    "FACETED_SMOOTH_SHADING",
    "SMOOTH_SHAPE_SMOOTH_SHADING",
    "SAT_GLYPH_SIZE",
    "LEADER_LINE_WIDTH",
    "LEADER_LINE_OPACITY",
    "LEADER_ANCHOR_DOT_RADIUS_PX",
    "LABEL_MAX_ANCHOR_DISTANCE_PX",
    "GRID_OPACITY",
    "GROUND_CAP_BASE_OPACITY",
    "CONTACT_SHADOW_OPACITY",
    "CONTACT_SHADOW_RADIUS_FACTOR",
    "ARC_TUBE_RADIUS_M",
    "ARC_TIP_HEIGHT_M",
    "ARC_TIP_RADIUS_M",
    "ARC_VALUE_LABEL_FONT_SIZE",
    "BODY_AXES_LENGTH_FRACTION",
    "BODY_AXES_MIN_LENGTH_M",
    "ACCENT_LINE_WIDTH",
]
