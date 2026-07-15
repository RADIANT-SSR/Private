"""``SchematicView`` — the 2D orthographic geometry schematic (QPainter canvas).

A faithful Qt port of the React/SVG mockup
``dev_tools/gui_mockups/geometry_viewer/scene.jsx`` + ``shapes.jsx``: a crisp,
antialiased line-schematic of the sun / sensor / target geometry, drawn with
:class:`~PySide6.QtGui.QPainter` over the ported orthographic projection
(:mod:`radiant.gui.viewer.projection`). It replaces the PyVista/VTK raster viewer
(ADR-0007, superseded 2026-07-14) — the VTK raster could not match the mockup's crisp
SVG line-art, and a pure-Qt 2D canvas has **no** VTK/OpenGL dependency, so it renders and
tests identically headless (``QWidget.grab``) with no segfault-prone live interactor.

It draws, faithfully per the mockup: the light background, a faint ground grid, the
``X``/``Y`` ground axes and the vertical zenith (``Z``) axis with arrowheads + labels, the
four labelled vectors (sun→target amber solid, sensor→target blue solid, sun→ground amber
dashed, zenith grey), the sun and sensor glyphs, the full **shape-library** wireframe
target (sphere great-circles / box / cylinder / cone / flat-plate / point reticle), the
ground-projection dashed drop-lines, and the VECTORS legend overlay. It supports
orthographic yaw/pitch rotation by mouse drag.

**Pass 2 (shipped) adds the annotations + interactions:** the revealable angle arcs
(off-nadir η, sun-zenith θ_s, relative-azimuth Δφ, phase α_t) each with a DEGREE value
pill sourced verbatim from ``stage_outputs["geometry"]`` (§6.3 — never recomputed from the
scene; the arc *geometry* uses the ported projection math, the arc *value* comes from the
stage), the h_s / h_t altitude leader labels (§6.1 not-to-scale magnitude annotation), the
target body-axes **RPY triad** (roll/pitch/yaw, CU-130) with the body wireframe rotated by
its ZYX Euler orientation, and the schema-driven per-shape dimension inputs (CU-131, wired
in the side panel). The angle-truth consistency test (:mod:`radiant.gui.viewer.angle_truth`)
proves the scene angle recomputation agrees with the stage within an explicit tolerance.

**Not-to-scale (owner-endorsed, binding — ADR-0007 §4 / arch doc §6.1):** glyphs sit at
*fixed abstract* display distances; the schematic is **never** rescaled or translated by
the raw metric altitude/range. A 600 km slant range and a 1 m target cannot share a
linear scale; true magnitudes are annotated as leader-label text (h_s / h_t pills).
Direction (the angles) is preserved; magnitude is not.

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
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from radiant.gui.themes.tokens import LIGHT, Theme
from radiant.gui.viewer import angle_catalog
from radiant.gui.viewer.projection import (
    Camera,
    ProjectedPoint,
    arc_between,
    dir_from_az_zen,
    ground_azimuth_arc,
    make_camera,
)
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

# -- Target wireframe abstract proportions (scene units; NEVER metric magnitude) -
# The full shape library (CU-131) draws each primitive at an *abstract* size that
# reflects only the shape's own aspect ratio (the ratios among its dimension params),
# never the raw metres — the not-to-scale rule (§6.1). A fully-dimensioned shape maps its
# largest relevant dim to ``_SHAPE_UNIT`` and the rest proportionally, each clamped to
# ``[_EXT_MIN, _EXT_MAX]`` so a very thin plate / long cylinder still reads; an
# under-specified shape (a dim at the ``0.0`` sentinel) falls back to the per-shape default
# proportions below.
_SHAPE_UNIT: float = 1.0
_EXT_MIN: float = 0.35
_EXT_MAX: float = 1.25

# Per-shape default abstract extents (used when the metric dims are unset). Aligned with
# the mockup ``shapes.jsx`` proportions. Keys are the dims the shape uses (see
# ``_SHAPE_DIMS``); order matches ``_SHAPE_DIMS``.
_DEFAULT_EXTENTS: dict[str, tuple[float, ...]] = {
    "sphere": (0.55,),  # (radius,)
    "cylinder": (0.5, 1.1),  # (radius, length→height)
    "cone": (0.65, 1.2),  # (base_radius, height)
    "box": (1.1, 0.85, 0.7),  # (length→X, width→Y, height→Z)
    "flat_plate": (1.5, 1.0),  # (length→X, width→Y)
}

# Shape → the ``ViewerState`` metric-dimension fields it consumes, in extent order.
_SHAPE_DIMS: dict[str, tuple[str, ...]] = {
    "sphere": ("target_radius_m",),
    "cylinder": ("target_radius_m", "target_length_m"),
    "cone": ("target_base_radius_m", "target_height_m"),
    "box": ("target_length_m", "target_width_m", "target_height_m"),
    "flat_plate": ("target_length_m", "target_width_m"),
}

# Stage-output key → the ``ViewerState`` field the angle arc reads its DISPLAY value from.
# ``ViewerState`` binds each field verbatim from ``stage_outputs["geometry"]`` (§6.7), so
# reading it here honours §6.3 (the value comes from the stage, never a scene recomputation);
# the value is converted radians → degrees at the display boundary only (task-sanctioned).
_STAGE_VALUE_FIELDS: dict[str, str] = {
    "eta_rad": "observer_look_angle_rad",
    "theta_s_rad": "solar_zenith_rad",
    "delta_phi_rad": "relative_azimuth_rad",
}

# RPY body-axis name → (glyph, palette colour) for the on-target triad (CU-130).
_TRIAD_AXES: dict[str, tuple[str, str]] = {
    "roll": ("X′", palette.BODY_AXIS_ROLL_COLOR),
    "pitch": ("Y′", palette.BODY_AXIS_PITCH_COLOR),
    "yaw": ("Z′", palette.BODY_AXIS_YAW_COLOR),
}


def _format_km(km: float) -> str:
    """Format an altitude/range magnitude with a sensible unit (owner showed '705 km')."""
    if km >= 100.0:
        return f"{km:.0f} km"
    if km >= 1.0:
        return f"{km:.1f} km"
    return f"{km * 1000.0:.0f} m"


# -- Line weights (px), mirroring the mockup stroke conventions -----------------
_W_GRID: float = 0.6
_W_AXIS: float = 1.0
_W_VECTOR: float = 2.0
_W_DROP: float = 0.9
_W_TARGET: float = 1.1
_W_ARC: float = 1.2  # angle-arc stroke (dashed)
_W_TRIAD: float = 1.8  # RPY body-axis stroke

_ARROW_LEN_PX: float = 10.0  # arrowhead length in pixels
_ARC_RADIUS: float = 1.0  # zenith/phase arc radius (scene units)
_GROUND_ARC_RADIUS: float = 1.4  # relative-azimuth ground arc radius
_TRIAD_LEN: float = 0.85  # RPY body-axis length (scene units)
_LABEL_FONT_PX: float = 10.0  # value/leader pill font size

# -- Fit-to-viewport constants (the scene is centred in the live paint rect) -----
# The orthographic camera scales the projected scene bounding box to fill the current
# widget rect with a symmetric margin, then translates so the bbox centre lands on the rect
# centre — so the schematic stays centred and framed at any window size / aspect (owner
# report 2026-07-14: the scene was bottom-anchored on a too-tall canvas). Recomputed every
# paint from ``self.width()``/``self.height()`` so it tracks live resizes.
_FIT_MARGIN_FRAC: float = 0.12  # symmetric margin as a fraction of the smaller rect side
_MIN_SCALE: float = 40.0  # floor on scene-unit → px so a tiny rect never collapses the scene
_EMPTY_SCALE: float = 80.0  # scale used before the first scene is bound (empty canvas)
# The canvas fills its tab viewport (Expanding policy); these bound its self-reported size so
# it neither collapses nor balloons taller than the viewport (owner report 2026-07-14).
_MIN_SIDE_PX: int = 360
_HINT_W_PX: int = 520
_HINT_H_PX: int = 480


@dataclass(frozen=True, slots=True)
class SchematicScene:
    """Engine-independent world-space scene built from a :class:`ViewerState`.

    All positions are **abstract scene units** (not metres) per the not-to-scale rule.
    ``sun_dir`` / ``sensor_dir`` are the true unit directions (angles preserved); the
    positions place the glyphs at fixed abstract radii along those directions. Consumed by
    :class:`SchematicView` for drawing; separated out so it is testable without a canvas.

    ``target_edges`` are already rotated by the target body's RPY (ZYX Euler); ``body_axes``
    holds the three post-rotation body-axis unit directions (roll +X′, pitch +Y′, yaw +Z′)
    for the on-target triad; ``target_center`` is the body's rotation pivot (also the triad
    origin). ``altitude_km`` / ``target_altitude_km`` are the leader-label magnitudes read
    verbatim from the stage-bound state (§6.1 not-to-scale annotation).
    """

    sun_dir: np.ndarray
    sensor_dir: np.ndarray
    sun_pos: np.ndarray
    sensor_pos: np.ndarray
    target_top: np.ndarray  # where the sun/sensor vectors land (top of the body)
    target_z: float
    target_center: np.ndarray  # body rotation pivot + triad origin
    ground_point: np.ndarray  # sensor-LOS → ground intersection (origin if on ground)
    airborne: bool
    target_shape: str
    target_edges: tuple[tuple[np.ndarray, np.ndarray], ...]
    body_axes: tuple[tuple[str, np.ndarray], ...]  # (roll/pitch/yaw name, unit dir)
    is_point: bool
    altitude_km: float
    target_altitude_km: float


def _origin() -> np.ndarray:
    return np.zeros(3, dtype=np.float64)


def _ring(cz: float, r: float, axis: str, n: int = 40) -> list[np.ndarray]:
    """A circle of *n* points, radius *r*, centred at ``(0, 0, cz)`` on the given plane."""
    pts: list[np.ndarray] = []
    for i in range(n):
        t = (i / n) * 2 * math.pi
        c, s = math.cos(t), math.sin(t)
        if axis == "z":
            pts.append(np.array([r * c, r * s, cz], dtype=np.float64))
        elif axis == "y":
            pts.append(np.array([r * c, 0.0, cz + r * s], dtype=np.float64))
        else:  # "x"
            pts.append(np.array([0.0, r * c, cz + r * s], dtype=np.float64))
    return pts


def _close(pts: list[np.ndarray]) -> list[tuple[np.ndarray, np.ndarray]]:
    """Edges closing a ring of points into a loop."""
    return [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def _sphere_edges(cz: float, r: float) -> list[tuple[np.ndarray, np.ndarray]]:
    """Three great circles (``z``/``y``/``x`` planes) — the mockup's clean sphere look."""
    edges: list[tuple[np.ndarray, np.ndarray]] = []
    for axis in ("z", "y", "x"):
        edges.extend(_close(_ring(cz, r, axis)))
    return edges


def _box_edges(cz: float, w: float, d: float, h: float) -> list[tuple[np.ndarray, np.ndarray]]:
    """The 12 edges of an axis-aligned box sitting on ``z = cz`` (mockup ``box``)."""
    x0, x1 = -w / 2, w / 2
    y0, y1 = -d / 2, d / 2
    z0, z1 = cz, cz + h
    c = [
        np.array([x0, y0, z0]),
        np.array([x1, y0, z0]),
        np.array([x1, y1, z0]),
        np.array([x0, y1, z0]),
        np.array([x0, y0, z1]),
        np.array([x1, y0, z1]),
        np.array([x1, y1, z1]),
        np.array([x0, y1, z1]),
    ]
    idx = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    ]
    return [(c[a].astype(np.float64), c[b].astype(np.float64)) for a, b in idx]


def _cylinder_edges(
    cz: float, r: float, h: float, n: int = 28
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Top + bottom rings plus four silhouette generators (mockup ``cylinder``)."""
    top = _ring(cz + h, r, "z", n)
    bot = _ring(cz, r, "z", n)
    edges = _close(top) + _close(bot)
    for k in range(4):
        idx = round((k / 4) * n) % n
        edges.append((bot[idx], top[idx]))
    return edges


def _cone_edges(cz: float, r: float, h: float, n: int = 28) -> list[tuple[np.ndarray, np.ndarray]]:
    """Base ring plus four slant generators up to the apex (mockup ``cone``)."""
    base = _ring(cz, r, "z", n)
    apex = np.array([0.0, 0.0, cz + h], dtype=np.float64)
    edges = _close(base)
    for k in range(4):
        idx = round((k / 4) * n) % n
        edges.append((base[idx], apex))
    return edges


def _plate_edges(cz: float, w: float, d: float) -> list[tuple[np.ndarray, np.ndarray]]:
    """A thin rectangular panel: outline + both diagonals (mockup ``plate``)."""
    x0, x1 = -w / 2, w / 2
    y0, y1 = -d / 2, d / 2
    corners = [
        np.array([x0, y0, cz]),
        np.array([x1, y0, cz]),
        np.array([x1, y1, cz]),
        np.array([x0, y1, cz]),
    ]
    edges = _close(corners)
    edges.append((corners[0], corners[2]))
    edges.append((corners[1], corners[3]))
    return edges


def _extents(shape: str, state: ViewerState) -> tuple[float, ...]:
    """Abstract wireframe extents for *shape* — its aspect ratio, never metric magnitude.

    When every dimension the shape uses is set (``> 0``), the largest maps to
    ``_SHAPE_UNIT`` and the rest proportionally (each clamped to ``[_EXT_MIN, _EXT_MAX]``);
    otherwise the per-shape default proportions are used. The not-to-scale rule (§6.1): the
    body reflects the ratio of its own dims, but the raw metres never set the on-screen size.
    """
    defaults = _DEFAULT_EXTENTS[shape]
    metric = tuple(float(getattr(state, field)) for field in _SHAPE_DIMS[shape])
    if all(v > 0.0 for v in metric):
        biggest = max(metric)
        return tuple(min(_EXT_MAX, max(_EXT_MIN, _SHAPE_UNIT * (v / biggest))) for v in metric)
    return defaults


def _euler_zyx_matrix(yaw: float, pitch: float, roll: float) -> np.ndarray:
    """The ZYX Tait–Bryan rotation ``Rz(yaw)·Ry(pitch)·Rx(roll)`` (Rule 3; mockup scene.jsx).

    Columns are the body axes expressed in the scene frame: column 0 = body +X (roll axis),
    column 1 = body +Y (pitch axis), column 2 = body +Z (yaw axis).
    """
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    return np.array(
        [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ],
        dtype=np.float64,
    )


def _shape_edges(
    shape: str, state: ViewerState, target_z: float
) -> tuple[list[tuple[np.ndarray, np.ndarray]], float]:
    """Build the base (unrotated) wireframe for *shape*; return ``(edges, top_z)``."""
    ext = _extents(shape, state)
    if shape == "sphere":
        (r,) = ext
        return _sphere_edges(target_z + r, r), target_z + 2 * r
    if shape == "cylinder":
        r, h = ext
        return _cylinder_edges(target_z, r, h), target_z + h
    if shape == "cone":
        r, h = ext
        return _cone_edges(target_z, r, h), target_z + h
    if shape == "box":
        w, d, h = ext
        return _box_edges(target_z, w, d, h), target_z + h
    if shape == "flat_plate":
        w, d = ext
        # A flat panel has no height; lift the vector-landing point a hair above the plate
        # so the sun/sensor vectors and label do not collapse onto the ground plane.
        return _plate_edges(target_z, w, d), target_z + _EXT_MIN * 0.5
    return [], target_z


def _rotate_edges(
    edges: list[tuple[np.ndarray, np.ndarray]], matrix: np.ndarray, center: np.ndarray
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Rotate every edge vertex about *center* by *matrix* (target body RPY)."""

    def rot(p: np.ndarray) -> np.ndarray:
        return matrix @ (p - center) + center

    return [(rot(a), rot(b)) for a, b in edges]


def build_scene(state: ViewerState) -> SchematicScene:
    """Build the abstract world-space :class:`SchematicScene` from a bound *state*.

    Directions come from the stage-derived angles (``solar_zenith_rad``,
    ``relative_azimuth_rad``, ``observer_look_angle_rad``); the sensor is placed at
    azimuth 0 and the sun at the relative azimuth, so the *relative* geometry (the
    radiometrically-relevant quantity) is faithful. Distances are the fixed abstract radii
    above — **never** the raw metric altitude/range (not-to-scale rule). The target body is
    drawn from the full shape library (CU-131) and rotated by its RPY (CU-130).
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
    is_point = shape not in _SHAPE_DIMS
    if is_point:
        base_edges: list[tuple[np.ndarray, np.ndarray]] = []
        top_z = target_z
    else:
        base_edges, top_z = _shape_edges(shape, state, target_z)

    target_center = np.array([0.0, 0.0, (target_z + top_z) * 0.5], dtype=np.float64)

    # Rotate the body + derive its post-rotation triad axes (ZYX Euler, Rule 3).
    matrix = _euler_zyx_matrix(state.target_yaw_rad, state.target_pitch_rad, state.target_roll_rad)
    edges = _rotate_edges(base_edges, matrix, target_center) if base_edges else base_edges
    body_axes: tuple[tuple[str, np.ndarray], ...] = (
        ("roll", matrix[:, 0].copy()),
        ("pitch", matrix[:, 1].copy()),
        ("yaw", matrix[:, 2].copy()),
    )

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
        target_center=target_center,
        ground_point=ground_point,
        airborne=airborne,
        target_shape=shape,
        target_edges=tuple(edges),
        body_axes=body_axes,
        is_point=is_point,
        altitude_km=state.observer_altitude_m / 1000.0,
        target_altitude_km=state.target_altitude_m / 1000.0,
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
        # Pass-2 annotation state: which angle arcs are revealed + the RPY-triad toggle.
        self._revealed: set[str] = set()
        self._show_triad: bool = False
        self.setMinimumSize(_MIN_SIDE_PX, _MIN_SIDE_PX)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(False)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt override
        """A sensible default size — the canvas *fills* its viewport (Expanding), never grows.

        The concrete hint (with the Expanding policy + :data:`_MIN_SIDE_PX` minimum) keeps the
        canvas filling its tab viewport rather than reporting an unbounded/degenerate size
        that a scroll area would inflate (owner report 2026-07-14: the schematic ballooned
        taller than the viewport and the scene ended up bottom-anchored)."""
        return QSize(_HINT_W_PX, _HINT_H_PX)

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

    # -- angle-arc / triad reveal (CU-128 / CU-130) -------------------------

    def set_revealed_angles(self, names: set[str]) -> None:
        """Set which angle arcs are drawn (by annotation name) and repaint."""
        self._revealed = set(names)
        self.update()

    def set_triad_visible(self, visible: bool) -> None:
        """Show/hide the on-target RPY triad and repaint."""
        self._show_triad = visible
        self.update()

    @property
    def revealed_angles(self) -> frozenset[str]:
        """The angle arcs currently drawn."""
        return frozenset(self._revealed)

    @property
    def triad_visible(self) -> bool:
        """True when the RPY triad is drawn."""
        return self._show_triad

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

    def _fit_points(self, scene: SchematicScene) -> list[np.ndarray]:
        """World points whose projected bounding box the fit-to-viewport centres on.

        The semantic scene extremes — the ground axes, the zenith top, the sun/sensor glyphs,
        the target body + its ground point — so centring frames the *content*. The faint
        ground grid (larger than the content) deliberately extends past the rect edges as a
        background rather than shrinking the scene to fit its corners.
        """
        pts: list[np.ndarray] = [
            _origin(),
            np.array([_AXIS_LEN, 0.0, 0.0]),
            np.array([-_AXIS_LEN, 0.0, 0.0]),
            np.array([0.0, _AXIS_LEN, 0.0]),
            np.array([0.0, -_AXIS_LEN, 0.0]),
            np.array([0.0, 0.0, _ZENITH_LEN]),
            scene.sun_pos,
            scene.sensor_pos,
            scene.target_top,
            scene.ground_point,
        ]
        for a, b in scene.target_edges:
            pts.append(a)
            pts.append(b)
        return pts

    def _camera(self) -> Camera:
        """The orthographic camera that fits + centres the scene in the live paint rect.

        The projected bounding box of :meth:`_fit_points` is scaled to fill the current
        ``width()``×``height()`` rect (minus a symmetric margin) and translated so the bbox
        centre lands on the rect centre. Reading the live size every paint keeps the scene
        centred and framed on resize, at any aspect (owner report 2026-07-14: the scene was
        anchored to the bottom of a too-tall canvas)."""
        w = max(1, self.width())
        h = max(1, self.height())
        if self._scene is None:
            return make_camera(self._yaw, self._pitch, _EMPTY_SCALE, w / 2.0, h / 2.0)
        # Probe the projection at unit scale / zero offset to read each point's (x2, -z2).
        probe = make_camera(self._yaw, self._pitch, 1.0, 0.0, 0.0)
        projected = [probe.project(p) for p in self._fit_points(self._scene)]
        xs = [p.x for p in projected]
        ys = [p.y for p in projected]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        raw_w = max(max_x - min_x, 1e-6)
        raw_h = max(max_y - min_y, 1e-6)
        margin = _FIT_MARGIN_FRAC * min(w, h)
        avail_w = max(1.0, w - 2.0 * margin)
        avail_h = max(1.0, h - 2.0 * margin)
        scale = max(_MIN_SCALE, min(avail_w / raw_w, avail_h / raw_h))
        center_raw_x = (min_x + max_x) / 2.0
        center_raw_y = (min_y + max_y) / 2.0
        # Place the bbox centre on the rect centre: screen = (cx + x2·s, cy + (-z2)·s).
        cx = w / 2.0 - center_raw_x * scale
        cy = h / 2.0 - center_raw_y * scale
        return make_camera(self._yaw, self._pitch, scale, cx, cy)

    def projected_content_bounds(self) -> tuple[float, float, float, float] | None:
        """The projected scene bbox ``(min_x, min_y, max_x, max_y)`` in the live paint rect.

        The bounding box of :meth:`_fit_points` after the fit-to-viewport camera — its centre
        lands on the rect centre and it clears the rect edges by the fit margin. ``None`` before
        the first :meth:`set_state`. Exposed so a test can assert the scene is centred + framed
        rather than bottom-anchored (owner report 2026-07-14)."""
        if self._scene is None:
            return None
        cam = self._camera()
        projected = [cam.project(p) for p in self._fit_points(self._scene)]
        xs = [p.x for p in projected]
        ys = [p.y for p in projected]
        return (min(xs), min(ys), max(xs), max(ys))

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
        self._draw_angle_arcs(painter, cam, scene)
        if self._show_triad and not scene.is_point:
            self._draw_triad(painter, cam, scene)
        self._draw_leader_labels(painter, cam, scene)
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

    def _polyline(self, painter: QPainter, cam: Camera, pts: list[np.ndarray], pen: QPen) -> None:
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

    def _label_font(self) -> QFont:
        """A small font for value/leader pills (inherits the app family; size only)."""
        font = QFont(self.font())
        font.setPointSizeF(_LABEL_FONT_PX)
        return font

    def _label_pill(self, painter: QPainter, x: float, y: float, text: str, color: str) -> None:
        """A boxed value/leader label: rounded rect (theme fill, coloured stroke) + text.

        Mirrors the mockup's boxed value labels (``scene.jsx`` ``AngleArc``/leader pills).
        The fill is the theme background so the pill stays legible over the grid; the
        stroke and text take the caller's semantic colour.
        """
        painter.setFont(self._label_font())
        metrics = painter.fontMetrics()
        pad_x, pad_y = 5.0, 3.0
        text_w = metrics.horizontalAdvance(text)
        text_h = metrics.height()
        rect = QRectF(x, y - text_h + pad_y, text_w + 2 * pad_x, text_h + pad_y)
        path = QPainterPath()
        path.addRoundedRect(rect, 3.0, 3.0)
        painter.setPen(self._pen(color, 0.6))
        painter.setBrush(QColor(self._theme.bg))
        painter.drawPath(path)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(color)))
        painter.drawText(QPointF(x + pad_x, y - metrics.descent()), text)
        painter.setFont(self.font())

    def _arc_label_text(self, ann: angle_catalog.AngleAnnotation) -> str:
        """The pill text for an arc: ``symbol NN.N°`` from the stage value, or symbol alone.

        A ``None`` stage_key (the phase angle) renders **symbol-only** — there is no
        stage-output phase angle, so §6.3 forbids fabricating a number.
        """
        if ann.stage_key is None or self._state is None:
            return ann.symbol
        field = _STAGE_VALUE_FIELDS.get(ann.stage_key)
        if field is None:
            return ann.symbol
        deg = math.degrees(float(getattr(self._state, field)))
        return f"{ann.symbol} {deg:.1f}°"

    def _arc_points(self, scene: SchematicScene, name: str) -> list[np.ndarray]:
        """The world-space arc polyline for annotation *name* (empty if not drawable)."""
        zenith = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        if name == "off_nadir":
            return [
                p + scene.target_top for p in arc_between(zenith, scene.sensor_dir, _ARC_RADIUS)
            ]
        if name == "sun_zenith":
            return [
                p + scene.target_top for p in arc_between(zenith, scene.sun_dir, _ARC_RADIUS * 1.15)
            ]
        if name == "phase_angle":
            return [
                p + scene.target_top
                for p in arc_between(scene.sun_dir, scene.sensor_dir, _ARC_RADIUS * 0.85)
            ]
        if name == "relative_azimuth" and self._state is not None:
            return ground_azimuth_arc(0.0, self._state.relative_azimuth_rad, _GROUND_ARC_RADIUS)
        return []

    def _draw_angle_arcs(self, painter: QPainter, cam: Camera, scene: SchematicScene) -> None:
        """Draw each revealed angle arc + its degree pill (CU-128).

        The arc GEOMETRY is placed by the ported projection math; the arc VALUE comes from
        ``ViewerState`` (bound verbatim from ``stage_outputs["geometry"]``, §6.3) and is
        shown in degrees. The phase arc is symbol-only (no stage truth).
        """
        for ann in angle_catalog.annotations():
            if ann.name not in self._revealed:
                continue
            pts = self._arc_points(scene, ann.name)
            if not pts:
                continue
            self._polyline(painter, cam, pts, self._pen(ann.color, _W_ARC, dashed=True))
            mid = cam.project(pts[len(pts) // 2])
            self._label_pill(painter, mid.x + 6, mid.y - 4, self._arc_label_text(ann), ann.color)

    def _draw_triad(self, painter: QPainter, cam: Camera, scene: SchematicScene) -> None:
        """Draw the on-target RPY body-axes triad (roll +X′, pitch +Y′, yaw +Z′) — CU-130."""
        center = scene.target_center
        pc = cam.project(center)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._theme.ink))
        painter.drawEllipse(QPointF(pc.x, pc.y), 2.2, 2.2)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for name, direction in scene.body_axes:
            glyph, color = _TRIAD_AXES[name]
            tip = center + direction * _TRIAD_LEN
            self._vector(painter, cam, center, tip, color, _W_TRIAD)
            pt = cam.project(tip)
            self._text(painter, pt.x + 4, pt.y, glyph, color)

    def _draw_leader_labels(self, painter: QPainter, cam: Camera, scene: SchematicScene) -> None:
        """Draw the not-to-scale altitude leader pills (h_s always; h_t when airborne) — CU-129.

        The magnitudes are read verbatim from the stage-bound state and shown in km/m; the
        geometry is never rescaled by them (§6.1 not-to-scale rule).
        """
        sp = cam.project(scene.sensor_pos)
        self._label_pill(
            painter,
            sp.x + 18,
            sp.y + 16,
            f"h_s  {_format_km(scene.altitude_km)}",
            self._theme.muted,
        )
        if scene.airborne:
            tp = cam.project(scene.target_top)
            self._label_pill(
                painter,
                tp.x + 12,
                tp.y + 22,
                f"h_t  {_format_km(scene.target_altitude_km)}",
                self._theme.muted,
            )

    def _draw_ground_grid(self, painter: QPainter, cam: Camera) -> None:
        pen = self._pen(self._theme.line, _W_GRID)
        span = _GRID_N * _GRID_STEP
        for i in range(-_GRID_N, _GRID_N + 1):
            y = i * _GRID_STEP
            self._line(
                painter,
                cam,
                np.array([-span, y, 0.0]),
                np.array([span, y, 0.0]),
                pen,
            )
            x = i * _GRID_STEP
            self._line(
                painter,
                cam,
                np.array([x, -span, 0.0]),
                np.array([x, span, 0.0]),
                pen,
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
            painter,
            cam,
            scene.sun_pos,
            scene.ground_point,
            palette.SOLAR_FAMILY,
            _W_TARGET + 0.3,
            dashed=True,
        )
        # Sensor LOS extension: target → ground point (blue dashed).
        self._vector(
            painter,
            cam,
            scene.target_top,
            scene.ground_point,
            palette.SATELLITE_FAMILY,
            _W_TARGET,
            dashed=True,
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
            painter,
            sp,
            palette.SUN_DISC_FILL,
            palette.SOLAR_FAMILY,
            6.0,
            (0, 60, 120, 180, 240, 300),
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
        self._vector(painter, cam, scene.sun_pos, scene.target_top, palette.SOLAR_FAMILY, _W_VECTOR)
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
