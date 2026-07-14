"""``SchematicView`` — the 2D orthographic geometry schematic (QPainter canvas).

A faithful Qt port of the React/SVG mockup
``dev_tools/gui_mockups/geometry_viewer/scene.jsx`` + ``shapes.jsx``: a crisp,
antialiased line-schematic of the sun / sensor / target geometry, drawn with
:class:`~PySide6.QtGui.QPainter` over the ported orthographic projection
(:mod:`radiant.gui.viewer.projection`). It replaces the PyVista/VTK raster viewer
(ADR-0007, superseded 2026-07-14) — the VTK raster could not match the mockup's crisp
SVG line-art, and a pure-Qt 2D canvas has **no** VTK/OpenGL dependency, so it renders and
tests identically headless (``QWidget.grab``) with no segfault-prone live interactor.

**Pass 1 (this file) is the renderer core — the *look*.** It draws, faithfully per the
mockup: the light background, a faint ground grid, the ``X``/``Y`` ground axes and the
vertical zenith (``Z``) axis with arrowheads + labels, the four labelled vectors
(sun→target amber solid, sensor→target blue solid, sun→ground amber dashed, zenith grey),
the sun and sensor glyphs, a wireframe target (sphere great-circles / box / point
reticle), the ground-projection dashed drop-lines, and the VECTORS legend overlay. It
supports orthographic yaw/pitch rotation by mouse drag. **Deferred to Pass 2** (each a
tracked CU): the θ_v/φ_v/θ_s angle arcs, the h_s / altitude leader labels, the full shape
library + dimension inputs, the RPY body triad, and the angle-truth consistency test.

**Not-to-scale (owner-endorsed, binding — ADR-0007 §4 / arch doc §6.1):** glyphs sit at
*fixed abstract* display distances; the schematic is **never** rescaled or translated by
the raw metric altitude/range. A 600 km slant range and a 1 m target cannot share a
linear scale; true magnitudes are annotated as leader-label text (the label text is
Pass 2). Direction (the angles) is preserved; magnitude is not.

Token discipline (§4.9): chrome colours (background, grid, axes, labels, the neutral
zenith grey, the legend pill) come from the active :class:`~radiant.gui.themes.tokens.Theme`;
the physics vector colours (sun = amber, sensor = blue, target = teal) come from the one
allowlisted :mod:`radiant.gui.viewer.scene.palette` module. This file holds no colour or
font literal. Fonts inherit the application font (no family literal).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from radiant.gui.themes.tokens import LIGHT, Theme
from radiant.gui.viewer.projection import Camera, ProjectedPoint, dir_from_az_zen, make_camera
from radiant.gui.viewer.scene import palette
from radiant.gui.viewer.viewer_state import ViewerState

__all__ = ["SchematicView", "SchematicScene", "build_scene"]

# -- Camera defaults (mockup app.jsx: iso preset yaw=35, pitch=22) --------------
DEFAULT_YAW_DEG: float = 35.0
DEFAULT_PITCH_DEG: float = 22.0
# Pitch clamp + drag sensitivities (mockup app.jsx onMouseMove).
_PITCH_MIN_DEG: float = 2.0
_PITCH_MAX_DEG: float = 89.0
_YAW_PER_PX: float = 0.4
_PITCH_PER_PX: float = 0.3

# -- Abstract scene distances (scene units; NEVER derived from metric range) ----
# The four fixed radii the mockup uses so the schematic reads clearly regardless of the
# true (wildly non-linear) metric magnitudes — the not-to-scale rule made concrete.
_SUN_DIST: float = 4.5
_SENSOR_DIST: float = 3.5
_AXIS_LEN: float = 2.4  # X/Y ground axes half-length
_ZENITH_LEN: float = 2.6  # +Z zenith axis length
_TARGET_AIRBORNE_Z: float = 0.9  # abstract lift for an airborne target (on/off ground cue)
_GRID_N: int = 8
_GRID_STEP: float = 0.8

# -- Target wireframe abstract sizes (scene units; dimensions are Pass 2) --------
_SPHERE_R: float = 0.55
_BOX_W: float = 1.2
_BOX_D: float = 0.9
_BOX_H: float = 0.7

# -- Line weights (px), mirroring the mockup stroke conventions -----------------
_W_GRID: float = 0.6
_W_AXIS: float = 1.0
_W_VECTOR: float = 2.0
_W_DROP: float = 0.9
_W_TARGET: float = 1.1

_ARROW_LEN_PX: float = 10.0  # arrowhead length in pixels


@dataclass(frozen=True, slots=True)
class SchematicScene:
    """Engine-independent world-space scene built from a :class:`ViewerState`.

    All positions are **abstract scene units** (not metres) per the not-to-scale rule.
    ``sun_dir`` / ``sensor_dir`` are the true unit directions (angles preserved); the
    positions place the glyphs at fixed abstract radii along those directions. Consumed by
    :class:`SchematicView` for drawing; separated out so it is testable without a canvas.
    """

    sun_dir: np.ndarray
    sensor_dir: np.ndarray
    sun_pos: np.ndarray
    sensor_pos: np.ndarray
    target_top: np.ndarray  # where the sun/sensor vectors land (top of the body)
    target_z: float
    ground_point: np.ndarray  # sensor-LOS → ground intersection (origin if on ground)
    airborne: bool
    target_shape: str
    target_edges: tuple[tuple[np.ndarray, np.ndarray], ...]
    is_point: bool


def _origin() -> np.ndarray:
    return np.zeros(3, dtype=np.float64)


def _sphere_edges(cz: float, r: float, n: int = 40) -> list[tuple[np.ndarray, np.ndarray]]:
    """Three great circles (``z``/``y``/``x`` planes) — the mockup's clean sphere look."""
    edges: list[tuple[np.ndarray, np.ndarray]] = []
    for axis in ("z", "y", "x"):
        pts: list[np.ndarray] = []
        for i in range(n):
            t = (i / n) * 2 * math.pi
            c, s = math.cos(t), math.sin(t)
            if axis == "z":
                pts.append(np.array([r * c, r * s, cz], dtype=np.float64))
            elif axis == "y":
                pts.append(np.array([r * c, 0.0, cz + r * s], dtype=np.float64))
            else:
                pts.append(np.array([0.0, r * c, cz + r * s], dtype=np.float64))
        for i in range(n):
            edges.append((pts[i], pts[(i + 1) % n]))
    return edges


def _box_edges(cz: float, w: float, d: float, h: float) -> list[tuple[np.ndarray, np.ndarray]]:
    """The 12 edges of an axis-aligned box sitting on ``z = cz`` (mockup ``box``)."""
    x0, x1 = -w / 2, w / 2
    y0, y1 = -d / 2, d / 2
    z0, z1 = cz, cz + h
    c = [
        np.array([x0, y0, z0]), np.array([x1, y0, z0]),
        np.array([x1, y1, z0]), np.array([x0, y1, z0]),
        np.array([x0, y0, z1]), np.array([x1, y0, z1]),
        np.array([x1, y1, z1]), np.array([x0, y1, z1]),
    ]
    idx = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]
    return [(c[a].astype(np.float64), c[b].astype(np.float64)) for a, b in idx]


def build_scene(state: ViewerState) -> SchematicScene:
    """Build the abstract world-space :class:`SchematicScene` from a bound *state*.

    Directions come from the stage-derived angles (``solar_zenith_rad``,
    ``relative_azimuth_rad``, ``observer_look_angle_rad``); the sensor is placed at
    azimuth 0 and the sun at the relative azimuth, so the *relative* geometry (the
    radiometrically-relevant quantity) is faithful. Distances are the fixed abstract radii
    above — **never** the raw metric altitude/range (not-to-scale rule).
    """
    sun_az = math.degrees(state.relative_azimuth_rad)
    sun_zen = math.degrees(state.solar_zenith_rad)
    sen_zen = math.degrees(state.observer_look_angle_rad)

    sun_dir = dir_from_az_zen(sun_az, sun_zen)
    sensor_dir = dir_from_az_zen(0.0, sen_zen)
    sun_pos = sun_dir * _SUN_DIST
    sensor_pos = sensor_dir * _SENSOR_DIST

    airborne = state.target_altitude_m > 0.0
    target_z = _TARGET_AIRBORNE_Z if airborne else 0.0

    shape = state.target_shape
    edges: list[tuple[np.ndarray, np.ndarray]] = []
    is_point = False
    if shape == "sphere":
        edges = _sphere_edges(target_z + _SPHERE_R, _SPHERE_R)
        top_z = target_z + 2 * _SPHERE_R
    elif shape == "box":
        edges = _box_edges(target_z, _BOX_W, _BOX_D, _BOX_H)
        top_z = target_z + _BOX_H
    elif shape in ("cylinder", "cone", "flat_plate"):
        # Pass-1 stand-in wireframes: a box footprint keeps a discrete body on screen; the
        # full shape library (true cylinder/cone/plate wireframes) is Pass 2 (CU-131).
        edges = _box_edges(target_z, _BOX_W, _BOX_D, _BOX_H)
        top_z = target_z + _BOX_H
    else:
        # "none" (extended / sub-pixel scene) or unknown → a point reticle at the target.
        is_point = True
        top_z = target_z

    target_top = np.array([0.0, 0.0, top_z], dtype=np.float64)

    # Ground illumination point: where the sensor→target ray, extended, meets z = 0.
    # For a ground target this is the origin; for an airborne target it walks out.
    ground_point = _origin()
    if airborne:
        dz = sensor_pos[2] - target_top[2]
        if abs(dz) > 1e-6:
            t = sensor_pos[2] / dz
            ground_point = sensor_pos + t * (target_top - sensor_pos)
            ground_point[2] = 0.0

    return SchematicScene(
        sun_dir=sun_dir,
        sensor_dir=sensor_dir,
        sun_pos=sun_pos,
        sensor_pos=sensor_pos,
        target_top=target_top,
        target_z=target_z,
        ground_point=ground_point,
        airborne=airborne,
        target_shape=shape,
        target_edges=tuple(edges),
        is_point=is_point,
    )


class SchematicView(QWidget):
    """The QPainter canvas that draws a :class:`SchematicScene` orthographically.

    Bind a scene with :meth:`set_state` (called by :class:`GeometryViewer` after each
    evaluate); the widget repaints on the next event loop. Drag with the left mouse button
    to rotate the orthographic camera (yaw about ``Z``, pitch about ``X``) exactly like the
    mockup — no free-orbit or perspective.

    Parameters
    ----------
    parent:
        The owning widget, if any.
    theme:
        The design-system :class:`Theme` the chrome follows (default: the light launch
        theme). :meth:`set_theme` swaps it and repaints.
    """

    def __init__(self, parent: QWidget | None = None, theme: Theme | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("geometrySchematic")
        self._theme: Theme = theme if theme is not None else LIGHT
        self._state: ViewerState | None = None
        self._scene: SchematicScene | None = None
        self._yaw: float = DEFAULT_YAW_DEG
        self._pitch: float = DEFAULT_PITCH_DEG
        self._drag_anchor: tuple[float, float, float, float] | None = None
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(False)

    # -- state / theme ------------------------------------------------------

    def set_state(self, state: ViewerState) -> None:
        """Bind *state*, rebuild the abstract scene, and schedule a repaint."""
        self._state = state
        self._scene = build_scene(state)
        self.update()

    def set_theme(self, theme: Theme) -> None:
        """Adopt *theme* and repaint (Phase-9 theme toggle)."""
        self._theme = theme
        self.update()

    @property
    def theme(self) -> Theme:
        """The active chrome theme."""
        return self._theme

    @property
    def scene(self) -> SchematicScene | None:
        """The bound abstract scene (``None`` before the first :meth:`set_state`)."""
        return self._scene

    @property
    def yaw_deg(self) -> float:
        """The camera yaw about ``Z`` (degrees)."""
        return self._yaw

    @property
    def pitch_deg(self) -> float:
        """The camera pitch about ``X`` (degrees, clamped to ``[2, 89]``)."""
        return self._pitch

    def set_orientation(self, yaw_deg: float, pitch_deg: float) -> None:
        """Set the camera yaw/pitch (pitch clamped) and repaint — for Pass-2 controls."""
        self._yaw = yaw_deg
        self._pitch = max(_PITCH_MIN_DEG, min(_PITCH_MAX_DEG, pitch_deg))
        self.update()

    # -- mouse orbit (orthographic; mockup app.jsx) -------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 — Qt override
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            self._drag_anchor = (pos.x(), pos.y(), self._yaw, self._pitch)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 — Qt override
        if self._drag_anchor is None:
            super().mouseMoveEvent(event)
            return
        x0, y0, yaw0, pitch0 = self._drag_anchor
        pos = event.position()
        dx = pos.x() - x0
        dy = pos.y() - y0
        self._yaw = yaw0 + dx * _YAW_PER_PX
        self._pitch = max(_PITCH_MIN_DEG, min(_PITCH_MAX_DEG, pitch0 - dy * _PITCH_PER_PX))
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 — Qt override
        if event.button() == Qt.MouseButton.LeftButton and self._drag_anchor is not None:
            self._drag_anchor = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # -- projection helpers -------------------------------------------------

    def _camera(self) -> Camera:
        """The orthographic camera fit to the current widget size (scale-to-fit)."""
        w = max(1, self.width())
        h = max(1, self.height())
        cx = w / 2.0
        cy = h * 0.72  # scene origin sits low so the zenith axis has headroom (mockup 0.78)
        scale = max(60.0, min(w / 7.5, h / 5.6))
        return make_camera(self._yaw, self._pitch, scale, cx, cy)

    @staticmethod
    def _pt(p: ProjectedPoint) -> QPointF:
        return QPointF(p.x, p.y)

    # -- drawing ------------------------------------------------------------

    def paintEvent(self, _event: object) -> None:  # noqa: N802 — Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.fillRect(self.rect(), QColor(self._theme.bg))

        if self._scene is None:
            self._draw_empty(painter)
            painter.end()
            return

        cam = self._camera()
        scene = self._scene
        self._draw_ground_grid(painter, cam)
        self._draw_axes(painter, cam)
        self._draw_drop_lines(painter, cam, scene)
        self._draw_ground_vectors(painter, cam, scene)
        self._draw_target(painter, cam, scene)
        self._draw_glyphs(painter, cam, scene)
        self._draw_main_vectors(painter, cam, scene)
        self._draw_legend(painter)
        painter.end()

    def _draw_empty(self, painter: QPainter) -> None:
        painter.setPen(QPen(QColor(self._theme.muted)))
        painter.drawText(
            self.rect(), Qt.AlignmentFlag.AlignCenter, "Evaluate to render the geometry schematic"
        )

    def _pen(self, color: str, width: float, *, dashed: bool = False) -> QPen:
        pen = QPen(QColor(color))
        pen.setWidthF(width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCosmetic(True)
        if dashed:
            pen.setDashPattern([4.0, 3.0])
        return pen

    def _polyline(
        self, painter: QPainter, cam: Camera, pts: list[np.ndarray], pen: QPen
    ) -> None:
        painter.setPen(pen)
        poly = QPolygonF([self._pt(cam.project(p)) for p in pts])
        painter.drawPolyline(poly)

    def _line(
        self, painter: QPainter, cam: Camera, a: np.ndarray, b: np.ndarray, pen: QPen
    ) -> None:
        painter.setPen(pen)
        painter.drawLine(self._pt(cam.project(a)), self._pt(cam.project(b)))

    def _vector(
        self,
        painter: QPainter,
        cam: Camera,
        a: np.ndarray,
        b: np.ndarray,
        color: str,
        width: float,
        *,
        dashed: bool = False,
    ) -> None:
        """Draw a→b with a filled arrowhead at b (the mockup's ``Vector``)."""
        pa = cam.project(a)
        pb = cam.project(b)
        self._line(painter, cam, a, b, self._pen(color, width, dashed=dashed))
        # Arrowhead in screen space so it is a constant pixel size (mockup head = 9–10 px).
        dx = pb.x - pa.x
        dy = pb.y - pa.y
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux
        base_x = pb.x - ux * _ARROW_LEN_PX
        base_y = pb.y - uy * _ARROW_LEN_PX
        half = _ARROW_LEN_PX * 0.45
        left = QPointF(base_x + nx * half, base_y + ny * half)
        right = QPointF(base_x - nx * half, base_y - ny * half)
        head = QPolygonF([QPointF(pb.x, pb.y), left, right])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPolygon(head)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _text(self, painter: QPainter, x: float, y: float, text: str, color: str) -> None:
        painter.setPen(QPen(QColor(color)))
        painter.drawText(QPointF(x, y), text)

    def _draw_ground_grid(self, painter: QPainter, cam: Camera) -> None:
        pen = self._pen(self._theme.line, _W_GRID)
        span = _GRID_N * _GRID_STEP
        for i in range(-_GRID_N, _GRID_N + 1):
            y = i * _GRID_STEP
            self._line(
                painter, cam,
                np.array([-span, y, 0.0]), np.array([span, y, 0.0]), pen,
            )
            x = i * _GRID_STEP
            self._line(
                painter, cam,
                np.array([x, -span, 0.0]), np.array([x, span, 0.0]), pen,
            )

    def _draw_axes(self, painter: QPainter, cam: Camera) -> None:
        axis_color = self._theme.muted_2
        dim = self._pen(axis_color, _W_AXIS, dashed=True)
        # +X / +Y solid arrowed, negative halves dashed.
        self._vector(painter, cam, _origin(), np.array([_AXIS_LEN, 0.0, 0.0]), axis_color, _W_AXIS)
        self._line(painter, cam, _origin(), np.array([-_AXIS_LEN, 0.0, 0.0]), dim)
        self._vector(painter, cam, _origin(), np.array([0.0, _AXIS_LEN, 0.0]), axis_color, _W_AXIS)
        self._line(painter, cam, _origin(), np.array([0.0, -_AXIS_LEN, 0.0]), dim)
        # +Z zenith axis — the neutral grey vector (one of the four labelled vectors).
        self._vector(
            painter, cam, _origin(), np.array([0.0, 0.0, _ZENITH_LEN]), self._theme.muted, _W_AXIS
        )
        # Axis labels.
        px = cam.project(np.array([_AXIS_LEN + 0.25, 0.0, 0.0]))
        py = cam.project(np.array([0.0, _AXIS_LEN + 0.25, 0.0]))
        pz = cam.project(np.array([0.0, 0.0, _ZENITH_LEN + 0.18]))
        self._text(painter, px.x - 3, px.y + 4, "X", self._theme.muted)
        self._text(painter, py.x - 3, py.y + 4, "Y", self._theme.muted)
        self._text(painter, pz.x - 3, pz.y - 6, "Z", self._theme.muted)

    def _draw_drop_lines(self, painter: QPainter, cam: Camera, scene: SchematicScene) -> None:
        pen = self._pen(self._theme.muted, _W_DROP, dashed=True)
        for pos in (scene.sun_pos, scene.sensor_pos):
            sub = np.array([pos[0], pos[1], 0.0])
            self._line(painter, cam, pos, sub, pen)  # vertical drop to sub-point
            self._line(painter, cam, _origin(), sub, pen)  # radial to origin

    def _draw_ground_vectors(self, painter: QPainter, cam: Camera, scene: SchematicScene) -> None:
        if not scene.airborne:
            return
        # Sun → ground illumination point (amber dashed) + the ground-point marker.
        self._vector(
            painter, cam, scene.sun_pos, scene.ground_point,
            palette.SOLAR_FAMILY, _W_TARGET + 0.3, dashed=True,
        )
        # Sensor LOS extension: target → ground point (blue dashed).
        self._vector(
            painter, cam, scene.target_top, scene.ground_point,
            palette.SATELLITE_FAMILY, _W_TARGET, dashed=True,
        )
        gp = cam.project(scene.ground_point)
        painter.setPen(self._pen(palette.SOLAR_FAMILY, 1.0))
        painter.setBrush(QColor(palette.SOLAR_FAMILY))
        painter.drawEllipse(QPointF(gp.x, gp.y), 2.0, 2.0)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_target(self, painter: QPainter, cam: Camera, scene: SchematicScene) -> None:
        if scene.is_point:
            p = cam.project(scene.target_top)
            painter.setPen(self._pen(self._theme.ink, _W_TARGET))
            painter.setBrush(QColor(self._theme.ink))
            painter.drawEllipse(QPointF(p.x, p.y), 2.5, 2.5)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for radius in (8.0, 14.0):
                painter.setPen(self._pen(self._theme.ink, 0.6))
                painter.drawEllipse(QPointF(p.x, p.y), radius, radius)
        else:
            pen = self._pen(palette.TARGET_COLOR, _W_TARGET)
            painter.setPen(pen)
            for a, b in scene.target_edges:
                painter.drawLine(self._pt(cam.project(a)), self._pt(cam.project(b)))
        # TARGET label at the body top.
        p = cam.project(scene.target_top)
        self._text(painter, p.x + 10, p.y + 4, "TARGET", self._theme.ink)

    def _draw_glyphs(self, painter: QPainter, cam: Camera, scene: SchematicScene) -> None:
        # Sun glyph: amber disc + ray ticks.
        sp = cam.project(scene.sun_pos)
        self._draw_star_glyph(
            painter, sp, palette.SUN_DISC_FILL, palette.SOLAR_FAMILY,
            6.0, (0, 60, 120, 180, 240, 300),
        )
        self._text(painter, sp.x + 20, sp.y - 8, "SUN", palette.SOLAR_FAMILY)
        # Sensor glyph: blue disc + 4 cardinal ticks (fewer ticks → distinct from sun).
        np_ = cam.project(scene.sensor_pos)
        self._draw_star_glyph(
            painter, np_, palette.SATELLITE_FAMILY, palette.SATELLITE_FAMILY, 5.0, (0, 90, 180, 270)
        )
        self._text(painter, np_.x + 16, np_.y - 6, "SENSOR", palette.SATELLITE_FAMILY)

    def _draw_star_glyph(
        self,
        painter: QPainter,
        p: ProjectedPoint,
        fill: str,
        ring: str,
        radius: float,
        angles_deg: tuple[int, ...],
    ) -> None:
        center = QPointF(p.x, p.y)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(fill))
        painter.drawEllipse(center, radius, radius)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(self._pen(ring, 0.7))
        painter.drawEllipse(center, radius + 4, radius + 4)
        painter.setPen(self._pen(ring, 1.0))
        for a in angles_deg:
            r = math.radians(a)
            inner = radius + 5
            outer = radius + 9
            painter.drawLine(
                QPointF(p.x + math.cos(r) * inner, p.y + math.sin(r) * inner),
                QPointF(p.x + math.cos(r) * outer, p.y + math.sin(r) * outer),
            )

    def _draw_main_vectors(self, painter: QPainter, cam: Camera, scene: SchematicScene) -> None:
        # Sun → target (amber solid) and sensor → target (blue solid).
        self._vector(
            painter, cam, scene.sun_pos, scene.target_top, palette.SOLAR_FAMILY, _W_VECTOR
        )
        self._vector(
            painter, cam, scene.sensor_pos, scene.target_top, palette.SATELLITE_FAMILY, _W_VECTOR
        )

    def _draw_legend(self, painter: QPainter) -> None:
        """The VECTORS legend overlay (top-left), drawn in screen space (mockup overlay)."""
        entries = (
            ("SUN → TARGET", palette.SOLAR_FAMILY, False),
            ("SENSOR → TARGET", palette.SATELLITE_FAMILY, False),
            ("SUN → GROUND", palette.SOLAR_FAMILY, True),
            ("ZENITH", self._theme.muted, False),
        )
        x0, y0 = 14.0, 14.0
        row_h = 18.0
        box_w = 168.0
        box_h = row_h * (len(entries) + 1) + 8.0
        path = QPainterPath()
        path.addRoundedRect(x0, y0, box_w, box_h, 6.0, 6.0)
        painter.setPen(self._pen(self._theme.line, 1.0))
        painter.setBrush(QColor(self._theme.panel))
        painter.drawPath(path)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        self._text(painter, x0 + 12, y0 + row_h, "VECTORS", self._theme.ink)
        for i, (label, color, dashed) in enumerate(entries):
            ry = y0 + row_h * (i + 2)
            painter.setPen(self._pen(color, 2.0, dashed=dashed))
            painter.drawLine(QPointF(x0 + 12, ry - 4), QPointF(x0 + 40, ry - 4))
            self._text(painter, x0 + 50, ry, label, self._theme.ink_2)
