"""World-frame corner gnomon (T4 of visual remediation).

The Phase-1 design placed a three-tube world-axes triad at the world
origin. Because the v2 scene is target-centric, the world origin
coincides with the body origin, so the world axes overlapped the body
axes and the user saw a six-tube tangle right under the target. T4
relocates the world frame to a screen-space gnomon in the bottom-left
of the viewport — same role (here is the global frame the camera lives
in) without any 3D clutter.

C7 (PLAN_v2.md §3): pure VTK, zero Qt imports. ``app/main.py`` is
responsible for binding the widget to the ``QtInteractor`` instance.

Rule 19: one widget, one file (parallels ``view_cube.py``).
"""

from __future__ import annotations

import vtk

from dev_tools.geometry_gui_v2.scene.labels.typography import viewport_label
from dev_tools.geometry_gui_v2.scene.style import (
    WORLD_AXES_GNOMON_LABEL_COLOR,
    WORLD_AXES_GNOMON_PLUS_X_COLOR,
    WORLD_AXES_GNOMON_PLUS_Y_COLOR,
    WORLD_AXES_GNOMON_PLUS_Z_COLOR,
    WORLD_AXES_GNOMON_SHAFT_COLOR,
    WORLD_AXES_GNOMON_VIEWPORT,
)
from dev_tools.geometry_gui_v2.scene.widgets.view_cube import _hex_to_rgb_unit


def _plain_axis_glyph(key: str) -> str:
    """Strip math-text delimiters so VTK renders ``x`` not ``$x$``."""
    return viewport_label(key).strip("$")


def build_axes_actor() -> vtk.vtkAxesActor:
    """Configure a ``vtkAxesActor`` with the subdued T4 palette.

    The +X / +Y / +Z shafts pick up the same desaturated family tints
    as the view-cube principal edges so the two corner widgets share an
    axis-color vocabulary.
    """
    axes = vtk.vtkAxesActor()

    # Axis labels — plain glyphs (no LaTeX delimiters); the gnomon is a
    # screen-space orientation aid, not a place for subscripts.
    axes.SetXAxisLabelText(_plain_axis_glyph("axis_x"))
    axes.SetYAxisLabelText(_plain_axis_glyph("axis_y"))
    axes.SetZAxisLabelText(_plain_axis_glyph("axis_z"))

    # Shaft tube color per axis. vtkAxesActor exposes per-axis tip and
    # shaft properties via getter calls; we tint both to the family color.
    plus_x = _hex_to_rgb_unit(WORLD_AXES_GNOMON_PLUS_X_COLOR)
    plus_y = _hex_to_rgb_unit(WORLD_AXES_GNOMON_PLUS_Y_COLOR)
    plus_z = _hex_to_rgb_unit(WORLD_AXES_GNOMON_PLUS_Z_COLOR)
    for prop_getter, color in (
        (axes.GetXAxisShaftProperty, plus_x),
        (axes.GetXAxisTipProperty, plus_x),
        (axes.GetYAxisShaftProperty, plus_y),
        (axes.GetYAxisTipProperty, plus_y),
        (axes.GetZAxisShaftProperty, plus_z),
        (axes.GetZAxisTipProperty, plus_z),
    ):
        prop_getter().SetColor(*color)

    # Subdued label backgrounds so the glyph sits on a hairline plate
    # rather than glowing against the viewport.
    label_rgb = _hex_to_rgb_unit(WORLD_AXES_GNOMON_LABEL_COLOR)
    shaft_rgb = _hex_to_rgb_unit(WORLD_AXES_GNOMON_SHAFT_COLOR)
    for caption_actor in (
        axes.GetXAxisCaptionActor2D(),
        axes.GetYAxisCaptionActor2D(),
        axes.GetZAxisCaptionActor2D(),
    ):
        caption_actor.GetCaptionTextProperty().SetColor(*label_rgb)
        caption_actor.GetCaptionTextProperty().BoldOff()
        caption_actor.GetCaptionTextProperty().ItalicOff()
        caption_actor.GetCaptionTextProperty().ShadowOff()
        # Hairline border around the caption plate, matching the view
        # cube's edge color so the two corner widgets feel like a set.
        caption_actor.GetProperty().SetColor(*shaft_rgb)

    return axes


def build_world_axes_widget(
    interactor,  # type: ignore[no-untyped-def]  # vtkRenderWindowInteractor
) -> vtk.vtkOrientationMarkerWidget:
    """Build the bottom-left orientation-marker widget hosting the axes.

    Caller must keep a reference (otherwise the widget is garbage-
    collected and disappears from the viewport).
    """
    axes = build_axes_actor()
    widget = vtk.vtkOrientationMarkerWidget()
    widget.SetOrientationMarker(axes)
    widget.SetInteractor(interactor)
    widget.SetViewport(*WORLD_AXES_GNOMON_VIEWPORT)
    widget.SetOutlineColor(*_hex_to_rgb_unit(WORLD_AXES_GNOMON_SHAFT_COLOR))
    widget.SetEnabled(True)
    # Locked to the corner — unlike the view cube, this widget is purely
    # informational; there is no click-to-snap action attached.
    widget.InteractiveOff()
    return widget
