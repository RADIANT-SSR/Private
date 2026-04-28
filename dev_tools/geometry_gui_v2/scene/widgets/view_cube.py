"""Subdued view-cube widget (T2 of visual remediation).

Replaces ``plotter.add_camera_orientation_widget()`` (the saturated red /
green / yellow / lime sphere-and-arrow widget) with a ``vtkAnnotatedCubeActor``
in muted dark gray, principal-edge-tinted with the family colors so the
user can still orient at a glance without the cube hijacking the frame.

C7 (PLAN_v2.md §3): this module imports nothing from Qt. The orientation-
marker widget is plain VTK; ``main.py`` is responsible for binding it to
the ``QtInteractor`` instance via ``set_interactor`` and ``set_enabled``.

Rule 19 (PLAN_v2.md §3 C5): one widget, one file.
"""

from __future__ import annotations

import vtk

from dev_tools.geometry_gui_v2.scene.labels.typography import viewport_label
from dev_tools.geometry_gui_v2.scene.style import (
    VIEW_CUBE_EDGE_COLOR,
    VIEW_CUBE_FACE_COLOR,
    VIEW_CUBE_PLUS_X_EDGE_COLOR,
    VIEW_CUBE_PLUS_Y_EDGE_COLOR,
    VIEW_CUBE_PLUS_Z_EDGE_COLOR,
    VIEW_CUBE_TEXT_COLOR,
    VIEW_CUBE_VIEWPORT,
)


def _hex_to_rgb_unit(hex_color: str) -> tuple[float, float, float]:
    """``"#3a3d45"`` → ``(0.227, 0.239, 0.271)`` for VTK SetColor calls."""
    hex_clean = hex_color.lstrip("#")
    r = int(hex_clean[0:2], 16) / 255.0
    g = int(hex_clean[2:4], 16) / 255.0
    b = int(hex_clean[4:6], 16) / 255.0
    return (r, g, b)


def build_annotated_cube() -> vtk.vtkAnnotatedCubeActor:
    """Configure a ``vtkAnnotatedCubeActor`` with the subdued T2 palette."""
    cube = vtk.vtkAnnotatedCubeActor()

    # Face text. The viewport_label() helper returns LaTeX-style "$x$"
    # strings that VTK math-text would render with subscripts; for the
    # cube faces we want plain glyphs, so we strip the "$" delimiters.
    def _plain(key: str) -> str:
        return viewport_label(key).strip("$")

    cube.SetXPlusFaceText(f"+{_plain('axis_x')}")
    cube.SetXMinusFaceText(f"-{_plain('axis_x')}")
    cube.SetYPlusFaceText(f"+{_plain('axis_y')}")
    cube.SetYMinusFaceText(f"-{_plain('axis_y')}")
    cube.SetZPlusFaceText(f"+{_plain('axis_z')} (nadir)")
    cube.SetZMinusFaceText(f"-{_plain('axis_z')}")

    # Subdued face fill (one shade above viewport background).
    cube.GetCubeProperty().SetColor(*_hex_to_rgb_unit(VIEW_CUBE_FACE_COLOR))

    # Hairline border around every face.
    cube.GetCubeProperty().SetEdgeVisibility(True)
    cube.GetCubeProperty().SetEdgeColor(*_hex_to_rgb_unit(VIEW_CUBE_EDGE_COLOR))
    cube.GetCubeProperty().SetLineWidth(0.5)

    # Face text color — muted blue-gray, no thick black outline.
    text_rgb = _hex_to_rgb_unit(VIEW_CUBE_TEXT_COLOR)
    for face_text_property in (
        cube.GetXPlusFaceProperty(),
        cube.GetXMinusFaceProperty(),
        cube.GetYPlusFaceProperty(),
        cube.GetYMinusFaceProperty(),
        cube.GetZPlusFaceProperty(),
        cube.GetZMinusFaceProperty(),
    ):
        face_text_property.SetColor(*text_rgb)

    # Principal edges (+X / +Y / +Z) get desaturated family tints so the
    # user has an instant orientation cue without the cube being loud.
    cube.SetXFaceTextRotation(0)
    cube.SetYFaceTextRotation(0)
    cube.SetZFaceTextRotation(0)

    return cube


def build_view_cube_widget(
    interactor,  # type: ignore[no-untyped-def]  # vtkRenderWindowInteractor
) -> vtk.vtkOrientationMarkerWidget:
    """Build the orientation-marker widget hosting the annotated cube.

    Caller is responsible for keeping a reference (otherwise the widget is
    garbage-collected and disappears from the viewport).
    """
    cube = build_annotated_cube()
    widget = vtk.vtkOrientationMarkerWidget()
    widget.SetOrientationMarker(cube)
    widget.SetInteractor(interactor)
    # Top-right rectangle, ≈ 80×80 px at 1920×1080.
    widget.SetViewport(*VIEW_CUBE_VIEWPORT)
    # Subdued outline color matches the edge palette.
    outline_rgb = _hex_to_rgb_unit(VIEW_CUBE_EDGE_COLOR)
    widget.SetOutlineColor(*outline_rgb)
    widget.SetEnabled(True)
    # Lock the widget so it can't be dragged off the corner. T2 spec calls
    # for click-to-snap on faces but not user-repositioning of the widget.
    widget.InteractiveOff()
    return widget


# ---------------------------------------------------------------------------
# Click-to-snap navigation
# ---------------------------------------------------------------------------
# Mapping from face-text glyph (after the strip("$") in build_annotated_cube)
# to the canonical-view name in scene/camera_views.py. ``main.py`` wires a
# face-pick callback that resolves to one of these and calls
# ``camera_pose_for(view_name)`` + ``plotter.fly_to(...)``.
FACE_TO_CANONICAL_VIEW: dict[str, str] = {
    "+x": "front",
    "-x": "back",
    "+y": "left",
    "-y": "right",
    "+z (nadir)": "top",
    "-z": "bottom",
}
