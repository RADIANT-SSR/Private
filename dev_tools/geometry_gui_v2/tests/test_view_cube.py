"""T2 acceptance: subdued view-cube widget configuration.

These tests touch only ``vtkAnnotatedCubeActor`` (pure VTK, no Qt) so they
run without ``RADIANT_GUI_FULL_WINDOW_TESTS=1``. Click-to-snap navigation
is wired in ``app/main.py`` and verified manually per the T2 visual
acceptance criterion.
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk")

from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene.widgets.view_cube import (
    FACE_TO_CANONICAL_VIEW,
    _hex_to_rgb_unit,
    build_annotated_cube,
)


def test_cube_face_text_uses_axis_glyphs() -> None:
    cube = build_annotated_cube()
    assert cube.GetXPlusFaceText() == "+x"
    assert cube.GetXMinusFaceText() == "-x"
    assert cube.GetYPlusFaceText() == "+y"
    assert cube.GetYMinusFaceText() == "-y"
    assert cube.GetZPlusFaceText() == "+z (nadir)"
    assert cube.GetZMinusFaceText() == "-z"


def test_cube_face_color_is_subdued() -> None:
    """Face fill matches the dark-gray VIEW_CUBE_FACE_COLOR — never saturated."""
    cube = build_annotated_cube()
    actual = cube.GetCubeProperty().GetColor()
    expected = _hex_to_rgb_unit(style.VIEW_CUBE_FACE_COLOR)
    for a, e in zip(actual, expected):
        assert abs(a - e) < 1e-3


def test_cube_text_color_is_subdued() -> None:
    cube = build_annotated_cube()
    expected = _hex_to_rgb_unit(style.VIEW_CUBE_TEXT_COLOR)
    for face_prop_getter in (
        cube.GetXPlusFaceProperty,
        cube.GetXMinusFaceProperty,
        cube.GetYPlusFaceProperty,
        cube.GetYMinusFaceProperty,
        cube.GetZPlusFaceProperty,
        cube.GetZMinusFaceProperty,
    ):
        actual = face_prop_getter().GetColor()
        for a, e in zip(actual, expected):
            assert abs(a - e) < 1e-3


def test_face_to_canonical_view_covers_six_faces() -> None:
    """All six face glyphs map to a known canonical view name."""
    expected_views = {"front", "back", "left", "right", "top", "bottom"}
    assert set(FACE_TO_CANONICAL_VIEW.values()) == expected_views


def test_no_saturated_red_green_or_yellow_in_face_color() -> None:
    """Sanity-check that the face palette is not the v0 saturated default.

    The first-cut screenshot used pure red / green / yellow / lime sphere
    glyphs. Any color channel above 0.6 in the face fill would put us back
    in that loud regime; the subdued #3a3d45 is well under that.
    """
    cube = build_annotated_cube()
    r, g, b = cube.GetCubeProperty().GetColor()
    assert max(r, g, b) < 0.6, (
        f"View-cube face color ({r:.3f}, {g:.3f}, {b:.3f}) too saturated"
    )
