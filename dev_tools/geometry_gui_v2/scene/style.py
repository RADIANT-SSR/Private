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
REFERENCE_LINE_WIDTH: Final[float] = 1.0

# Reference-frame stub length is a fraction of the target characteristic
# length (TARGET_DISPLAY_RADIUS = 1.0). Body axes are intentionally short
# so they don't visually compete with the target body. World-axes
# constants used to live here too; T4 of the visual remediation moved
# the world frame to a screen-space corner gnomon, so the in-scene
# constants no longer have a consumer and were deleted.
BODY_AXES_LENGTH_FRACTION: Final[float] = 0.15

# ---------------------------------------------------------------------------
# Tier 5 — Glyph sizes (screen-space px).
# ---------------------------------------------------------------------------

SAT_GLYPH_SIZE: Final[int] = 7
SUN_DISC_SIZE: Final[int] = 9
SUN_RAY_TIP_SIZE: Final[int] = 2

# ---------------------------------------------------------------------------
# Tier 5b — Leader lines + anchor dots (label-to-anchor connectors).
# ---------------------------------------------------------------------------
# Round-2 R6 (PLAN_v2_remediation_round2.md §7): leader lines were rendered
# in the per-label family color at 0.75 px / 0.45 opacity, which all but
# vanished against the dark viewport. Tier 5b pins a single neutral color
# for every leader, bumped width and opacity so the connector is legible,
# and a per-label anchor dot so the user can disambiguate "which 3D point
# does this label point at" at a glance. Hover constants drive the
# Phase-5 hover-thicken behaviour.
LEADER_LINE_COLOR: Final[str] = "#6a6d75"
LEADER_LINE_HOVER_COLOR: Final[str] = "#bcd0f0"
LEADER_LINE_WIDTH: Final[float] = 1.0
LEADER_LINE_HOVER_WIDTH: Final[float] = 2.0
LEADER_LINE_OPACITY: Final[float] = 0.85
LEADER_ANCHOR_DOT_RADIUS_PX: Final[float] = 1.5  # 3 px diameter
# Hard cap on label-to-anchor screen distance. The deconfliction solver may
# push a label far away to resolve a cluster; round-2 R6 step 4 is explicit
# that "a label that's 400 px from the thing it labels is worse than a label
# that overlaps slightly". Solver runs first; this clamp runs last.
LABEL_MAX_ANCHOR_DISTANCE_PX: Final[float] = 240.0

# ---------------------------------------------------------------------------
# Tier 6 — Ground grid (recede).
# ---------------------------------------------------------------------------

GRID_OPACITY: Final[float] = 0.45

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

# ---------------------------------------------------------------------------
# View-cube widget (T2 of visual remediation).
# ---------------------------------------------------------------------------
# Subdued so the view-cube doesn't dominate the frame. Faces are a half-
# tone above the viewport background; edges are a hair lighter; +X / +Y /
# +Z principal edges pick up a desaturated family color (red / green /
# blue) so the user can still orient at a glance.
VIEW_CUBE_FACE_COLOR: Final[str] = "#3a3d45"          # one shade above bg
VIEW_CUBE_EDGE_COLOR: Final[str] = "#5a5d65"          # hairline border
VIEW_CUBE_TEXT_COLOR: Final[str] = "#bcd0f0"          # light blue-gray
VIEW_CUBE_PLUS_X_EDGE_COLOR: Final[str] = "#9a4040"   # desaturated red
VIEW_CUBE_PLUS_Y_EDGE_COLOR: Final[str] = SURFACE_FAMILY  # muted green
VIEW_CUBE_PLUS_Z_EDGE_COLOR: Final[str] = SATELLITE_FAMILY  # muted blue
# Top-right viewport rectangle — ~80×80 px at 1920×1080.
VIEW_CUBE_VIEWPORT: Final[tuple[float, float, float, float]] = (0.86, 0.78, 0.99, 0.99)

# ---------------------------------------------------------------------------
# Angle arcs (T6 of visual remediation).
# ---------------------------------------------------------------------------
# T6 widens arc tubes and arrowhead cones so the great-arc angle
# annotations actually read at typical zoom. Phase 1 used a 12 mm tube
# with a 100 mm × 50 mm cone, which disappeared against the target body
# at default camera distances. The new sizes are roughly 2× across the
# board; the arc-radius widening lives in ``_layout.py``.
ARC_TUBE_RADIUS_M: Final[float] = 0.022
ARC_TIP_HEIGHT_M: Final[float] = 0.16
ARC_TIP_RADIUS_M: Final[float] = 0.085

# ---------------------------------------------------------------------------
# World-axes corner gnomon (T4 of visual remediation).
# ---------------------------------------------------------------------------
# T4 moves the world-frame triad from the 3D origin (where it overlapped the
# body axes, producing a six-tube ball-of-yarn) to a screen-space gnomon in
# the bottom-left of the viewport. The widget reads as "this is the global
# frame the camera lives in" without any in-scene clutter.
#
# Subdued palette (a half-shade above the viewport bg) so the gnomon doesn't
# pull focus from the geometry itself; +X / +Y / +Z get the same desaturated
# family tints as the view-cube's principal edges so the two corner widgets
# share an axis-color vocabulary.
WORLD_AXES_GNOMON_SHAFT_COLOR: Final[str] = "#5a5d65"
WORLD_AXES_GNOMON_LABEL_COLOR: Final[str] = "#bcd0f0"
WORLD_AXES_GNOMON_PLUS_X_COLOR: Final[str] = VIEW_CUBE_PLUS_X_EDGE_COLOR
WORLD_AXES_GNOMON_PLUS_Y_COLOR: Final[str] = VIEW_CUBE_PLUS_Y_EDGE_COLOR
WORLD_AXES_GNOMON_PLUS_Z_COLOR: Final[str] = VIEW_CUBE_PLUS_Z_EDGE_COLOR
# Bottom-left viewport rectangle — ~120×120 px at 1920×1080. Mirrors the
# top-right view-cube footprint so the two corner widgets feel balanced.
WORLD_AXES_GNOMON_VIEWPORT: Final[tuple[float, float, float, float]] = (
    0.01,
    0.01,
    0.14,
    0.22,
)
