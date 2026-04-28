"""Visual-hierarchy palette and rendering-style registry (v2 port).

Single source of truth for every color, line width, and glyph-size
constant the PyVista scene builder uses. Six-tier saliency hierarchy
(descending weight): target body → active-edit accent → geometric
vectors → reference frames → glyphs → ground grid.

Ported from v1 ``visual_hierarchy.py`` per PLAN_v2.md §6:
  * Every color hex is unchanged.
  * Every line-width and glyph-size value is unchanged.
  * The Plotly ``TARGET_LIGHTING`` dict (ambient/diffuse/specular/roughness/
    fresnel) is replaced with PyVista PBR parameters (metallic/roughness/
    diffuse_color). The ``roughness`` value carries over directly; the
    other Plotly knobs are baked into PyVista's PBR shader and have no
    direct equivalent.
  * The Plotly ``TARGET_LIGHT_POSITION`` dict moves to a PyVista
    light-position 3-vector with the same x/y/z values.

C7 (PLAN_v2.md §3): this file imports nothing from Qt.

Tests: every numeric constant defined here is pinned by
``tests/test_style_constants.py`` so a future drift surfaces immediately.

Rule 19: own file. Pure constants — no functions that compute physics.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Tier 1 — Target body (full saturation, sharp edges, PBR shading).
# ---------------------------------------------------------------------------

TARGET_COLOR: Final[str] = "#2EC4B6"
TARGET_OPACITY: Final[float] = 0.92

# PyVista PBR parameters for the target body. Plotly's ``ambient``,
# ``diffuse``, ``specular``, and ``fresnel`` knobs from v1 don't have a
# direct equivalent in PyVista's physically-based renderer; the look is
# now controlled by ``metallic`` + ``roughness`` + a directional sun
# light + an ambient fill light (set up in scene/builder.py in Phase 2).
# ``roughness`` is carried over verbatim from v1 so the look is anchored.
TARGET_PBR_METALLIC: Final[float] = 0.10
TARGET_PBR_ROUGHNESS: Final[float] = 0.45  # matches v1 TARGET_LIGHTING["roughness"]
TARGET_PBR_DIFFUSE_COLOR: Final[str] = TARGET_COLOR

# Sun-side fill-light anchor in scene-frame meters. Carried over from v1
# ``TARGET_LIGHT_POSITION`` — the actual sun direction in Phase 2 comes
# from ``view_model``; this is only used as a fallback when the sun
# direction is unset (e.g. unit-test renders).
TARGET_LIGHT_POSITION: Final[tuple[float, float, float]] = (4.0, 4.0, 6.0)

# Faceted shapes set ``smooth_shading=False`` for sharp edge silhouettes;
# smooth shapes set ``smooth_shading=True`` so curvature reads as a
# continuous gradient. (Same intent as v1 ``flatshading``; the PyVista
# parameter sense is inverted, so the constant names are also inverted.)
FACETED_SMOOTH_SHADING: Final[bool] = False
SMOOTH_SHAPE_SMOOTH_SHADING: Final[bool] = True

# ---------------------------------------------------------------------------
# Tier 2 — Active-edit accent (overlay re-stroke).
# ---------------------------------------------------------------------------

ACCENT_COLOR: Final[str] = "#FF6B35"
ACCENT_LINE_WIDTH: Final[float] = 2.5
# v1 used Plotly's ``dash`` style string. PyVista line styles use a different
# vocabulary; the dash pattern is implemented via vtkLeaderActor / actor
# property in Phase 5. This constant stays in v1's vocabulary as a label.
ACCENT_DASH: Final[str] = "dash"

# ---------------------------------------------------------------------------
# Tier 3 — Geometric vector families.
# ---------------------------------------------------------------------------

SATELLITE_FAMILY: Final[str] = "#3A6FAA"      # muted blue: satellite + boresight
SURFACE_FAMILY: Final[str] = "#3A8A66"        # muted green: n_B, surface normals
SOLAR_FAMILY: Final[str] = "#C28A1F"          # muted amber: s_t, s_B, sun glyph
TARGET_VECTOR_FAMILY: Final[str] = "#5E8F8B"  # desaturated teal: phase-angle arc α_t
VECTOR_LINE_WIDTH: Final[float] = 1.5
DASHED_COMPANION_LINE_WIDTH: Final[float] = 1.0

# ---------------------------------------------------------------------------
# Tier 4 — Reference frames (neutral grays, ≈ 60 % saturation).
# ---------------------------------------------------------------------------

BODY_AXES_COLOR: Final[str] = "#7A8086"
WORLD_AXES_COLOR: Final[str] = "#9499A0"
REFERENCE_LINE_WIDTH: Final[float] = 1.0

# Reference-frame stub length is a fraction of the target characteristic
# length (TARGET_DISPLAY_RADIUS = 1.0). Body axes are intentionally short
# so they don't visually compete with the target body.
BODY_AXES_LENGTH_FRACTION: Final[float] = 0.15
WORLD_AXES_LENGTH_FRACTION: Final[float] = 0.30

# ---------------------------------------------------------------------------
# Tier 5 — Glyph sizes (screen-space px).
# ---------------------------------------------------------------------------

SAT_GLYPH_SIZE: Final[int] = 7
SUN_DISC_SIZE: Final[int] = 9
SUN_RAY_TIP_SIZE: Final[int] = 2

# ---------------------------------------------------------------------------
# Tier 6 — Ground grid (recede).
# ---------------------------------------------------------------------------

GRID_OPACITY: Final[float] = 0.08

# Contact-shadow constants (Tier 1 chrome — sits behind the target body).
CONTACT_SHADOW_COLOR: Final[str] = "#000000"
CONTACT_SHADOW_OPACITY: Final[float] = 0.18
CONTACT_SHADOW_RADIUS_FACTOR: Final[float] = 1.05

# ---------------------------------------------------------------------------
# Background / window chrome (v2-only).
# ---------------------------------------------------------------------------

# Viewport background — a faint cool gray so PBR-shaded surfaces have
# something to contrast against. Phase 6 may swap this when the dark/light
# theme switch lands.
VIEWPORT_BACKGROUND_COLOR: Final[str] = "#1F242B"
