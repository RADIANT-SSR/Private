"""Pin every numeric / string constant in ``scene/style.py`` to its v1 value.

PLAN_v2.md §6 (salvage): "every numeric constant in v1's
``visual_hierarchy.py`` has a corresponding constant in v2's
``scene/style.py``, and a unit test pins each value."

This test is the lock. A drift in any palette / line-width / glyph-size
constant fails immediately, surfacing the change for explicit review
rather than silently shifting the visual identity.

The Plotly-specific lighting dict (ambient/diffuse/specular/fresnel)
has no v2 equivalent — it's replaced by PyVista's PBR shader. The
``roughness`` value carries over and is pinned below.
"""

from __future__ import annotations

import math

from dev_tools.geometry_gui_v2.scene import style


# ---------------------------------------------------------------------------
# Tier 1 — Target body
# ---------------------------------------------------------------------------


def test_target_color() -> None:
    assert style.TARGET_COLOR == "#2EC4B6"


def test_target_opacity() -> None:
    assert style.TARGET_OPACITY == 0.92


def test_target_pbr_metallic() -> None:
    assert style.TARGET_PBR_METALLIC == 0.10


def test_target_pbr_roughness_carries_over_v1_value() -> None:
    """v1 ``TARGET_LIGHTING['roughness']`` was 0.45; v2 PBR roughness must match."""
    assert style.TARGET_PBR_ROUGHNESS == 0.45


def test_target_pbr_diffuse_color_equals_target_color() -> None:
    assert style.TARGET_PBR_DIFFUSE_COLOR == style.TARGET_COLOR


def test_target_light_position() -> None:
    assert style.TARGET_LIGHT_POSITION == (4.0, 4.0, 6.0)


def test_smooth_shading_flags_are_inverse_of_v1_flatshading() -> None:
    # v1: FACETED_FLATSHADING = True, SMOOTH_FLATSHADING = False
    # v2 inverts the sense (PyVista parameter is smooth_shading, not flatshading).
    assert style.FACETED_SMOOTH_SHADING is False
    assert style.SMOOTH_SHAPE_SMOOTH_SHADING is True


# ---------------------------------------------------------------------------
# Tier 2 — Active-edit accent
# ---------------------------------------------------------------------------


def test_accent_color() -> None:
    assert style.ACCENT_COLOR == "#FF6B35"


def test_accent_line_width() -> None:
    assert style.ACCENT_LINE_WIDTH == 2.5


def test_accent_dash() -> None:
    assert style.ACCENT_DASH == "dash"


# ---------------------------------------------------------------------------
# Tier 3 — Geometric vector families
# ---------------------------------------------------------------------------


def test_vector_family_colors() -> None:
    assert style.SATELLITE_FAMILY == "#3A6FAA"
    assert style.SURFACE_FAMILY == "#3A8A66"
    assert style.SOLAR_FAMILY == "#C28A1F"
    assert style.TARGET_VECTOR_FAMILY == "#5E8F8B"


def test_vector_line_widths() -> None:
    assert style.VECTOR_LINE_WIDTH == 1.5
    assert style.DASHED_COMPANION_LINE_WIDTH == 1.0


# ---------------------------------------------------------------------------
# Tier 4 — Reference frames
# ---------------------------------------------------------------------------


def test_reference_frame_colors() -> None:
    # T4 of the visual remediation moved the world frame to a corner
    # gnomon, so ``WORLD_AXES_COLOR`` is gone — the gnomon's per-axis
    # tints live in ``test_world_axes_gnomon_constants`` below.
    assert style.BODY_AXES_COLOR == "#7A8086"


def test_reference_line_width() -> None:
    assert style.REFERENCE_LINE_WIDTH == 1.0


def test_reference_axes_length_fractions() -> None:
    # ``WORLD_AXES_LENGTH_FRACTION`` was removed alongside the in-scene
    # world-axes triad (T4); only the body axes need a length fraction now.
    assert style.BODY_AXES_LENGTH_FRACTION == 0.15


# ---------------------------------------------------------------------------
# Tier 5 — Glyph sizes
# ---------------------------------------------------------------------------


def test_glyph_sizes() -> None:
    assert style.SAT_GLYPH_SIZE == 7
    assert style.SUN_DISC_SIZE == 9
    assert style.SUN_RAY_TIP_SIZE == 2


# ---------------------------------------------------------------------------
# Tier 6 — Ground grid + contact shadow
# ---------------------------------------------------------------------------


def test_grid_opacity() -> None:
    assert style.GRID_OPACITY == 0.08


def test_contact_shadow_constants() -> None:
    assert style.CONTACT_SHADOW_COLOR == "#000000"
    assert style.CONTACT_SHADOW_OPACITY == 0.18
    assert style.CONTACT_SHADOW_RADIUS_FACTOR == 1.05


def test_view_cube_constants() -> None:
    """T2 view-cube palette: subdued, never saturated."""
    assert style.VIEW_CUBE_FACE_COLOR == "#3a3d45"
    assert style.VIEW_CUBE_EDGE_COLOR == "#5a5d65"
    assert style.VIEW_CUBE_TEXT_COLOR == "#bcd0f0"
    assert style.VIEW_CUBE_PLUS_X_EDGE_COLOR == "#9a4040"
    assert style.VIEW_CUBE_PLUS_Y_EDGE_COLOR == style.SURFACE_FAMILY
    assert style.VIEW_CUBE_PLUS_Z_EDGE_COLOR == style.SATELLITE_FAMILY
    assert style.VIEW_CUBE_VIEWPORT == (0.86, 0.78, 0.99, 0.99)


def test_world_axes_gnomon_constants() -> None:
    """T4 corner gnomon: bottom-left viewport, family-tinted shafts."""
    assert style.WORLD_AXES_GNOMON_SHAFT_COLOR == "#5a5d65"
    assert style.WORLD_AXES_GNOMON_LABEL_COLOR == "#bcd0f0"
    # Shafts share the view-cube principal-edge palette so the two corner
    # widgets read as a coordinated set.
    assert style.WORLD_AXES_GNOMON_PLUS_X_COLOR == style.VIEW_CUBE_PLUS_X_EDGE_COLOR
    assert style.WORLD_AXES_GNOMON_PLUS_Y_COLOR == style.VIEW_CUBE_PLUS_Y_EDGE_COLOR
    assert style.WORLD_AXES_GNOMON_PLUS_Z_COLOR == style.VIEW_CUBE_PLUS_Z_EDGE_COLOR
    # Viewport is bottom-left and stays inside the [0, 1] normalized rect.
    vp = style.WORLD_AXES_GNOMON_VIEWPORT
    assert vp == (0.01, 0.01, 0.14, 0.22)
    x0, y0, x1, y1 = vp
    assert 0.0 <= x0 < x1 <= 1.0
    assert 0.0 <= y0 < y1 <= 1.0
    # Anchored to the bottom-left half of the frame, never floating mid-screen.
    assert x0 < 0.5 and y0 < 0.5


# ---------------------------------------------------------------------------
# Sanity: every fractional value is in [0, 1]
# ---------------------------------------------------------------------------


def test_all_opacity_and_fraction_values_are_in_unit_interval() -> None:
    fractional = (
        style.TARGET_OPACITY,
        style.TARGET_PBR_METALLIC,
        style.TARGET_PBR_ROUGHNESS,
        style.GRID_OPACITY,
        style.CONTACT_SHADOW_OPACITY,
        style.BODY_AXES_LENGTH_FRACTION,
    )
    for v in fractional:
        assert 0.0 <= v <= 1.0, f"{v} out of [0, 1]"


def test_color_constants_are_seven_char_hex() -> None:
    color_constants = (
        style.TARGET_COLOR,
        style.ACCENT_COLOR,
        style.SATELLITE_FAMILY,
        style.SURFACE_FAMILY,
        style.SOLAR_FAMILY,
        style.TARGET_VECTOR_FAMILY,
        style.BODY_AXES_COLOR,
        style.CONTACT_SHADOW_COLOR,
        style.VIEWPORT_BACKGROUND_COLOR,
        style.VIEW_CUBE_FACE_COLOR,
        style.VIEW_CUBE_EDGE_COLOR,
        style.VIEW_CUBE_TEXT_COLOR,
        style.VIEW_CUBE_PLUS_X_EDGE_COLOR,
        style.VIEW_CUBE_PLUS_Y_EDGE_COLOR,
        style.VIEW_CUBE_PLUS_Z_EDGE_COLOR,
        style.WORLD_AXES_GNOMON_SHAFT_COLOR,
        style.WORLD_AXES_GNOMON_LABEL_COLOR,
        style.WORLD_AXES_GNOMON_PLUS_X_COLOR,
        style.WORLD_AXES_GNOMON_PLUS_Y_COLOR,
        style.WORLD_AXES_GNOMON_PLUS_Z_COLOR,
    )
    for c in color_constants:
        assert len(c) == 7 and c.startswith("#"), f"{c!r} is not a #RRGGBB hex"
        # Every char after the # must be a hex digit.
        int(c[1:], 16)


def test_no_nan_or_inf_in_numeric_constants() -> None:
    for name in dir(style):
        if name.startswith("_"):
            continue
        v = getattr(style, name)
        if isinstance(v, float):
            assert math.isfinite(v), f"{name} is not finite: {v!r}"
