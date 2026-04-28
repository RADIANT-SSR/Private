"""LeaderLabel — one screen-space text actor + one screen-space leader line.

PLAN_v2.md §12 step 1: pair a ``vtk.vtkTextActor`` (the label text in 2D
screen space) with a ``vtk.vtkLeaderActor2D``-style line drawn from the
projected anchor to the label position.

The pair shares a 3D world anchor (``anchor_world``). The label position
in screen space is decided by the layout solver
(``scene.labels.layout.solve_layout``); this module just *renders* the
result. Re-running the layout on every camera change is the Phase-5
interaction concern.

Rule 19: own file. Each ``LeaderLabel`` is a single primitive — a
text actor + leader line is one composite, not two separate
computations (Rule 19 carve-out for tightly coupled pairs).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pyvista as pv
import vtk


# Estimated character cell at the chosen font size. The layout solver
# needs a label-box size in pixels; we estimate from len(text). A real
# bbox query would require rendering, which is a chicken-and-egg with
# the deconfliction. The estimate is conservative (oversized boxes →
# more separation), which is the right side to err on.
_CHAR_WIDTH_PX: float = 7.0  # 12-pt sans-serif average advance
_LINE_HEIGHT_PX: float = 16.0
_TEXT_HORIZ_PADDING_PX: float = 6.0
_TEXT_VERT_PADDING_PX: float = 4.0


@dataclass(frozen=True)
class LeaderLabel:
    name: str
    anchor_world: npt.NDArray[np.float64]
    text: str
    color: str  # hex string

    def estimated_screen_size_px(self) -> tuple[float, float]:
        width = len(self.text) * _CHAR_WIDTH_PX + 2 * _TEXT_HORIZ_PADDING_PX
        height = _LINE_HEIGHT_PX + 2 * _TEXT_VERT_PADDING_PX
        return (width, height)


def project_world_to_display(
    plotter: pv.Plotter,
    world_xyz: npt.NDArray[np.float64],
) -> tuple[float, float]:
    """Project a 3D world point to 2D display (pixel) coordinates.

    Uses the plotter's renderer's vtkCoordinate to map world → display.
    Returns the pixel coordinates with origin at the lower-left of the
    viewport (VTK display coords).
    """
    coord = vtk.vtkCoordinate()
    coord.SetCoordinateSystemToWorld()
    coord.SetValue(float(world_xyz[0]), float(world_xyz[1]), float(world_xyz[2]))
    px = coord.GetComputedDisplayValue(plotter.renderer)
    return (float(px[0]), float(px[1]))


def add_leader_label(
    plotter: pv.Plotter,
    label: LeaderLabel,
    label_screen_xy: tuple[float, float],
    anchor_screen_xy: tuple[float, float],
) -> None:
    """Render one leader label: a text actor at the label position + a
    2D line from the anchor position to the label position."""

    text_actor = vtk.vtkTextActor()
    text_actor.SetInput(label.text)
    text_actor.SetPosition(float(label_screen_xy[0]), float(label_screen_xy[1]))
    tp = text_actor.GetTextProperty()
    tp.SetFontSize(12)
    tp.SetFontFamilyToArial()
    tp.SetColor(*_hex_to_rgb_float(label.color))
    tp.SetJustificationToCentered()
    tp.SetVerticalJustificationToCentered()
    tp.SetBackgroundColor(0.122, 0.141, 0.169)  # matches VIEWPORT_BACKGROUND_COLOR
    tp.SetBackgroundOpacity(0.85)
    plotter.add_actor(text_actor, name=f"{label.name}_text")

    # Leader line as a 2D vtkLeaderActor2D — both endpoints in display
    # (pixel) coords. Endpoint at label gets nudged toward the anchor so
    # the line doesn't pierce the text background.
    leader = vtk.vtkLeaderActor2D()
    leader.GetPositionCoordinate().SetCoordinateSystemToDisplay()
    leader.GetPositionCoordinate().SetValue(
        float(anchor_screen_xy[0]), float(anchor_screen_xy[1])
    )
    leader.GetPosition2Coordinate().SetCoordinateSystemToDisplay()
    nudged = _nudge_toward(label_screen_xy, anchor_screen_xy, distance=12.0)
    leader.GetPosition2Coordinate().SetValue(float(nudged[0]), float(nudged[1]))
    leader.SetArrowPlacementToNone()
    leader.GetProperty().SetColor(*_hex_to_rgb_float(label.color))
    leader.GetProperty().SetLineWidth(1.0)
    leader.GetProperty().SetOpacity(0.6)
    plotter.add_actor(leader, name=f"{label.name}_leader")


def _hex_to_rgb_float(hex_color: str) -> tuple[float, float, float]:
    s = hex_color.lstrip("#")
    r = int(s[0:2], 16) / 255.0
    g = int(s[2:4], 16) / 255.0
    b = int(s[4:6], 16) / 255.0
    return (r, g, b)


def _nudge_toward(
    a: tuple[float, float] | npt.NDArray[np.float64],
    b: tuple[float, float] | npt.NDArray[np.float64],
    distance: float,
) -> tuple[float, float]:
    a_arr = np.asarray(a, dtype=np.float64)
    b_arr = np.asarray(b, dtype=np.float64)
    delta = b_arr - a_arr
    n = float(np.linalg.norm(delta))
    if n < 1e-9:
        return (float(a_arr[0]), float(a_arr[1]))
    unit = delta / n
    out = a_arr + unit * min(distance, n * 0.5)
    return (float(out[0]), float(out[1]))
