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

import re
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pyvista as pv
import vtk

from dev_tools.geometry_gui_v2.scene import style


# Estimated character cell at the chosen font size. The layout solver
# needs a label-box size in pixels; we estimate from len(text). A real
# bbox query would require rendering, which is a chicken-and-egg with
# the deconfliction. The estimate is conservative (oversized boxes →
# more separation), which is the right side to err on.
_CHAR_WIDTH_PX: float = 6.0  # 10-pt sans-serif average advance
_LINE_HEIGHT_PX: float = 13.0
_TEXT_HORIZ_PADDING_PX: float = 4.0
_TEXT_VERT_PADDING_PX: float = 2.0

# T10 of the visual remediation introduced VTK math-text strings like
# ``$\theta_{off}$`` whose ``$``, ``{``, ``}``, ``\`` characters are
# layout/markup, not rendered glyphs. Counting them as printable inflates
# the estimated box width and breaks the deconfliction solver. Strip the
# math-text markup before counting characters; LaTeX command tokens
# (``\theta``) collapse to one rendered glyph.
_MATHTEXT_BLOCK = re.compile(r"\$([^$]*)\$")
_LATEX_COMMAND = re.compile(r"\\[A-Za-z]+")
_LATEX_BRACES = re.compile(r"[{}]")


def _rendered_char_count(text: str) -> int:
    """Approximate the number of rendered glyphs in ``text``.

    Treats every ``$...$`` block as math-text: braces are stripped and
    each ``\\command`` collapses to one glyph (e.g. ``\\theta`` → ``θ``).
    Non-mathtext segments pass through unchanged.
    """
    def _collapse(match: re.Match[str]) -> str:
        inner = match.group(1)
        inner = _LATEX_COMMAND.sub("x", inner)  # one-glyph stand-in
        inner = _LATEX_BRACES.sub("", inner)
        return inner
    return len(_MATHTEXT_BLOCK.sub(_collapse, text))


@dataclass(frozen=True)
class LeaderLabel:
    name: str
    anchor_world: npt.NDArray[np.float64]
    text: str
    color: str  # hex string

    def estimated_screen_size_px(self) -> tuple[float, float]:
        width = _rendered_char_count(self.text) * _CHAR_WIDTH_PX + 2 * _TEXT_HORIZ_PADDING_PX
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
    tp.SetFontSize(10)
    tp.SetFontFamilyToArial()
    tp.SetColor(*_hex_to_rgb_float(label.color))
    tp.SetJustificationToCentered()
    tp.SetVerticalJustificationToCentered()
    # Phase-7 diet: tighter pill — darker, less opaque background so it
    # reads as a subtle annotation rather than a bold sticker.
    tp.SetBackgroundColor(0.078, 0.090, 0.110)  # one shade below viewport bg
    tp.SetBackgroundOpacity(0.65)
    plotter.add_actor(text_actor, name=f"{label.name}_text")

    # Leader line as a 2D vtkLeaderActor2D — both endpoints in display
    # (pixel) coords. Endpoint at label gets nudged toward the anchor so
    # the line doesn't pierce the text background.
    # Round-2 R6: every leader uses LEADER_LINE_COLOR (a single neutral
    # gray) rather than the per-label family color. Mixing leader color
    # with text color was visually noisy and made the connectors merge
    # into the family-coded vectors. The label text and pill keep the
    # family color; the connector is now clearly "annotation chrome".
    leader_color = _hex_to_rgb_float(style.LEADER_LINE_COLOR)
    leader = vtk.vtkLeaderActor2D()
    leader.GetPositionCoordinate().SetCoordinateSystemToDisplay()
    leader.GetPositionCoordinate().SetValue(
        float(anchor_screen_xy[0]), float(anchor_screen_xy[1])
    )
    leader.GetPosition2Coordinate().SetCoordinateSystemToDisplay()
    nudged = _nudge_toward(label_screen_xy, anchor_screen_xy, distance=12.0)
    leader.GetPosition2Coordinate().SetValue(float(nudged[0]), float(nudged[1]))
    leader.SetArrowPlacementToNone()
    leader.GetProperty().SetColor(*leader_color)
    leader.GetProperty().SetLineWidth(style.LEADER_LINE_WIDTH)
    leader.GetProperty().SetOpacity(style.LEADER_LINE_OPACITY)
    plotter.add_actor(leader, name=f"{label.name}_leader")

    # Anchor dot — a 3 px-diameter filled circle at the projected anchor
    # so the user can disambiguate which 3D point the leader points at.
    # Implemented as a screen-space vtkActor2D: a regular polygon with
    # ~12 sides reads as a circle at this size and skips the cost of a
    # texture-based glyph.
    _add_anchor_dot(plotter, anchor_screen_xy, leader_color, name=f"{label.name}_dot")


def _add_anchor_dot(
    plotter: pv.Plotter,
    anchor_screen_xy: tuple[float, float],
    color: tuple[float, float, float],
    name: str,
) -> None:
    radius_px = float(style.LEADER_ANCHOR_DOT_RADIUS_PX)
    n_sides = 12
    points = vtk.vtkPoints()
    polygon = vtk.vtkPolygon()
    polygon.GetPointIds().SetNumberOfIds(n_sides)
    cx, cy = float(anchor_screen_xy[0]), float(anchor_screen_xy[1])
    for i in range(n_sides):
        theta = 2.0 * np.pi * i / n_sides
        points.InsertNextPoint(
            cx + radius_px * float(np.cos(theta)),
            cy + radius_px * float(np.sin(theta)),
            0.0,
        )
        polygon.GetPointIds().SetId(i, i)
    cells = vtk.vtkCellArray()
    cells.InsertNextCell(polygon)
    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(cells)

    mapper = vtk.vtkPolyDataMapper2D()
    mapper.SetInputData(poly)
    coord = vtk.vtkCoordinate()
    coord.SetCoordinateSystemToDisplay()
    mapper.SetTransformCoordinate(coord)

    actor = vtk.vtkActor2D()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*color)
    actor.GetProperty().SetOpacity(style.LEADER_LINE_OPACITY)
    plotter.add_actor(actor, name=name)


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
