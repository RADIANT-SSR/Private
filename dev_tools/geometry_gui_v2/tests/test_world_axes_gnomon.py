"""T4 acceptance: bottom-left world-axes corner gnomon.

These tests touch only ``vtkAxesActor`` (pure VTK, no Qt) so they run
without ``RADIANT_GUI_FULL_WINDOW_TESTS=1``. Widget-installation against
a live ``vtkRenderWindowInteractor`` is verified manually per the T4
visual acceptance criterion (the QtInteractor offscreen-GL segfault on
this dev machine — CU-042 — blocks an automated end-to-end install).
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk")

from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene.widgets.view_cube import _hex_to_rgb_unit
from dev_tools.geometry_gui_v2.scene.widgets.world_axes_gnomon import (
    build_axes_actor,
)


def test_axis_label_text_uses_axis_glyphs() -> None:
    axes = build_axes_actor()
    assert axes.GetXAxisLabelText() == "x"
    assert axes.GetYAxisLabelText() == "y"
    assert axes.GetZAxisLabelText() == "z"


@pytest.mark.parametrize(
    ("shaft_getter_name", "tip_getter_name", "expected_color"),
    [
        ("GetXAxisShaftProperty", "GetXAxisTipProperty", style.WORLD_AXES_GNOMON_PLUS_X_COLOR),
        ("GetYAxisShaftProperty", "GetYAxisTipProperty", style.WORLD_AXES_GNOMON_PLUS_Y_COLOR),
        ("GetZAxisShaftProperty", "GetZAxisTipProperty", style.WORLD_AXES_GNOMON_PLUS_Z_COLOR),
    ],
)
def test_axis_shaft_and_tip_share_family_color(
    shaft_getter_name: str, tip_getter_name: str, expected_color: str
) -> None:
    """Each axis (+X / +Y / +Z) is uniformly tinted with its family color."""
    axes = build_axes_actor()
    expected = _hex_to_rgb_unit(expected_color)
    for getter_name in (shaft_getter_name, tip_getter_name):
        actual = getattr(axes, getter_name)().GetColor()
        for a, e in zip(actual, expected):
            assert abs(a - e) < 1e-3, (
                f"{getter_name}() color {actual} != {expected_color} ({expected})"
            )


def test_axis_label_color_is_subdued_blue_gray() -> None:
    """Labels use the subdued WORLD_AXES_GNOMON_LABEL_COLOR — not pure white."""
    axes = build_axes_actor()
    expected = _hex_to_rgb_unit(style.WORLD_AXES_GNOMON_LABEL_COLOR)
    for caption_getter in (
        axes.GetXAxisCaptionActor2D,
        axes.GetYAxisCaptionActor2D,
        axes.GetZAxisCaptionActor2D,
    ):
        actual = caption_getter().GetCaptionTextProperty().GetColor()
        for a, e in zip(actual, expected):
            assert abs(a - e) < 1e-3


def test_label_text_property_has_no_shadow_or_bold() -> None:
    """Subdued chrome — no shadow, no bold, no italic on the captions."""
    axes = build_axes_actor()
    for caption_getter in (
        axes.GetXAxisCaptionActor2D,
        axes.GetYAxisCaptionActor2D,
        axes.GetZAxisCaptionActor2D,
    ):
        prop = caption_getter().GetCaptionTextProperty()
        assert prop.GetShadow() == 0
        assert prop.GetBold() == 0
        assert prop.GetItalic() == 0


def test_no_saturated_axis_color() -> None:
    """No shaft channel above 0.7 — guards against returning to a saturated palette."""
    axes = build_axes_actor()
    for getter_name in (
        "GetXAxisShaftProperty",
        "GetYAxisShaftProperty",
        "GetZAxisShaftProperty",
    ):
        r, g, b = getattr(axes, getter_name)().GetColor()
        assert max(r, g, b) < 0.7, (
            f"{getter_name} color ({r:.3f}, {g:.3f}, {b:.3f}) too saturated"
        )
