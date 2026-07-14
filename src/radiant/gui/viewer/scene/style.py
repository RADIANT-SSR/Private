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
* **Part-B constants dropped.** The view-cube, world-axes gnomon, body-axes, and
  angle-arc constants belong to modules deferred to Part B (interactions / RPY triad /
  angle annotations) and are not lifted here; they return with those modules.

Every numeric value is a verbatim carry-over so the lifted primitives render identically.
"""

from __future__ import annotations

from typing import Final

# Semantic glyph colors — re-exported from the palette so ``style.<NAME>`` keeps working
# in the lifted modules. The literals live only in ``palette.py`` (allowlisted).
from radiant.gui.viewer.scene.palette import (
    ACCENT_COLOR,
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


__all__ = [
    # re-exported colors (defined in palette.py)
    "TARGET_COLOR",
    "TARGET_PBR_DIFFUSE_COLOR",
    "SATELLITE_FAMILY",
    "SURFACE_FAMILY",
    "SOLAR_FAMILY",
    "TARGET_VECTOR_FAMILY",
    "ACCENT_COLOR",
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
]
