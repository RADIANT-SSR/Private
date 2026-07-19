"""Orthographic projection + direction math for the 2D geometry schematic.

Ported **verbatim** from the React/SVG mockup
``dev_tools/gui_mockups/geometry_viewer/geometry.js`` — the canonical reference for the
schematic's projection and vector conventions (``radiant_geometry_handoff.md`` §4/§7).
The mockup is an intentionally *not-to-scale* orthographic line-schematic; this module is
its Python port and holds the same math so the Qt canvas
(:mod:`radiant.gui.viewer.schematic_view`) reproduces the mockup's look exactly.

Conventions (identical to ``geometry.js``):

* **Coordinate frame:** ``+X = East``, ``+Y = North``, ``+Z = Up`` (zenith).
* **Camera:** orthographic. World points are rotated by *yaw* (about ``Z``) then *pitch*
  (about ``X``); ``Z`` is dropped. No perspective — a schematic, not a flight view.
* **Azimuth:** measured clockwise from ``+Y`` (North), in **degrees** in the public API.
* **Zenith angle:** measured from ``+Z``, in **degrees** in the public API.

Angles are degrees at the boundary and radians internally — exactly as ``geometry.js``.
This module holds **no physics** and imports only :mod:`numpy` and the stdlib; it is the
projection/camera math only (arch doc §6.3: the ported math is used for
camera/projection, never as a second angle authority — the stage owns angle truth).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

__all__ = [
    "ProjectedPoint",
    "Camera",
    "SceneAngles",
    "dir_from_az_zen",
    "make_camera",
    "compute_angles",
    "arc_between",
    "ground_azimuth_arc",
]


def dir_from_az_zen(az_deg: float, zen_deg: float) -> np.ndarray:
    """Unit direction vector from azimuth (deg, cw from ``+Y``/North) and zenith (deg).

    The remote-sensing convention (``geometry.js`` ``dirFromAzZen``):
    ``(sin ze · sin az, sin ze · cos az, cos ze)`` in the ``+X=East / +Y=North / +Z=Up``
    frame. Returns a length-3 ``float64`` array.
    """
    az = math.radians(az_deg)
    ze = math.radians(zen_deg)
    return np.array(
        [math.sin(ze) * math.sin(az), math.sin(ze) * math.cos(az), math.cos(ze)],
        dtype=np.float64,
    )


@dataclass(frozen=True, slots=True)
class ProjectedPoint:
    """A world point after orthographic projection to canvas pixels.

    ``x``/``y`` are canvas pixel coordinates (``y`` grows downward, as in Qt/SVG).
    ``depth`` is the post-pitch ``y`` component, exposed for painter's-order sorting
    (further-away edges first). It is not a perspective depth — this is orthographic.
    """

    x: float
    y: float
    depth: float


@dataclass(frozen=True, slots=True)
class Camera:
    """Orthographic camera: rotate by yaw about ``Z``, pitch about ``X``, drop ``Z``.

    A direct port of ``geometry.js`` ``makeCamera``. *yaw_deg* rotates about the world
    ``Z`` axis (0 = looking toward ``-Y``/from the south); *pitch_deg* tilts the scene
    forward toward the viewer (90 = top-down, 0 = horizon). *scale_px* is the
    scene-unit → pixel scale (orthographic scale-to-fit, chosen by the canvas);
    ``(cx, cy)`` is the canvas anchor the scene origin projects to.
    """

    yaw_deg: float
    pitch_deg: float
    scale_px: float
    cx: float
    cy: float

    def project(self, point: np.ndarray) -> ProjectedPoint:
        """Project a world *point* (length-3 array) to canvas pixels.

        Line-for-line the ``geometry.js`` ``project`` closure: yaw about ``Z``, then
        pitch about ``X``, then orthographic drop of the rotated ``Z`` with the canvas
        ``y`` axis flipped (screen ``y`` grows downward).
        """
        yaw = math.radians(self.yaw_deg)
        pitch = math.radians(self.pitch_deg)
        cy_ = math.cos(yaw)
        sy = math.sin(yaw)
        cp = math.cos(pitch)
        sp = math.sin(pitch)

        px = float(point[0])
        py = float(point[1])
        pz = float(point[2])

        # Yaw around Z.
        x1 = cy_ * px + sy * py
        y1 = -sy * px + cy_ * py
        z1 = pz
        # Pitch around X (tilt the scene forward toward the viewer).
        x2 = x1
        y2 = cp * y1 - sp * z1
        z2 = sp * y1 + cp * z1
        return ProjectedPoint(
            x=self.cx + x2 * self.scale_px,
            y=self.cy - z2 * self.scale_px,
            depth=y2,
        )


def make_camera(yaw_deg: float, pitch_deg: float, scale_px: float, cx: float, cy: float) -> Camera:
    """Construct a :class:`Camera` (mirrors the ``geometry.js`` ``makeCamera`` factory)."""
    return Camera(yaw_deg=yaw_deg, pitch_deg=pitch_deg, scale_px=scale_px, cx=cx, cy=cy)


# -- Angle recomputation + arc geometry (ported from geometry.js) ----------------
# NOTE (arch doc §6.3, binding): this math is for arc GEOMETRY/PLACEMENT and the
# angle-truth consistency check ONLY. The angle VALUES the schematic *displays* come
# from ``stage_outputs["geometry"]`` (bound verbatim into ``ViewerState``) — never from
# these functions. ``compute_angles`` exists so the angle-truth test can prove the scene
# math agrees with the stage (:mod:`radiant.gui.viewer.angle_truth`).


@dataclass(frozen=True, slots=True)
class SceneAngles:
    """Angles (radians) recomputed from the scene's sun/sensor unit directions.

    A verbatim port of ``geometry.js`` ``computeAngles`` (kept in radians here rather
    than the mockup's degrees, so the angle-truth check compares against the stage's
    canonical-radian outputs directly). ``theta_v`` is the view zenith (= off-nadir η in
    the scene's construction); ``delta_phi`` is the sensor-relative-to-sun azimuth in
    ``[0, π]``; ``phase`` is the sun→sensor phase angle g.
    """

    theta_s_rad: float
    phi_s_rad: float
    theta_v_rad: float
    phi_v_rad: float
    delta_phi_rad: float
    phase_rad: float


def compute_angles(sun_dir: np.ndarray, sensor_dir: np.ndarray) -> SceneAngles:
    """Recompute the scene angles (radians) from sun & sensor unit directions.

    Port of ``geometry.js`` ``computeAngles``: zenith angles from ``acos`` of the ``z``
    component, azimuths from ``atan2(x, y)`` (clockwise from ``+Y``/North), the relative
    azimuth folded to ``[0, π]``, and the phase angle from the spherical law of cosines.
    Used for arc placement + the angle-truth check only — **not** for display (§6.3).
    """
    sun = sun_dir / max(float(np.linalg.norm(sun_dir)), 1e-12)
    sen = sensor_dir / max(float(np.linalg.norm(sensor_dir)), 1e-12)
    theta_s = math.acos(float(np.clip(sun[2], -1.0, 1.0)))
    phi_s = math.atan2(float(sun[0]), float(sun[1])) % (2 * math.pi)
    theta_v = math.acos(float(np.clip(sen[2], -1.0, 1.0)))
    phi_v = math.atan2(float(sen[0]), float(sen[1])) % (2 * math.pi)
    dphi = abs(phi_v - phi_s)
    if dphi > math.pi:
        dphi = 2 * math.pi - dphi
    cos_phase = math.cos(theta_s) * math.cos(theta_v) + math.sin(theta_s) * math.sin(
        theta_v
    ) * math.cos(dphi)
    phase = math.acos(float(np.clip(cos_phase, -1.0, 1.0)))
    return SceneAngles(
        theta_s_rad=theta_s,
        phi_s_rad=phi_s,
        theta_v_rad=theta_v,
        phi_v_rad=phi_v,
        delta_phi_rad=dphi,
        phase_rad=phase,
    )


def arc_between(
    dir_a: np.ndarray, dir_b: np.ndarray, radius: float, n: int = 24
) -> list[np.ndarray]:
    """Sample a great-circle arc (``n + 1`` points) between two directions at *radius*.

    Port of ``geometry.js`` ``arcBetween`` — spherical-linear interpolation from ``dir_a``
    to ``dir_b``, scaled to ``radius``. Used to draw the θ (zenith) and phase arcs.
    """
    a = dir_a / max(float(np.linalg.norm(dir_a)), 1e-12)
    b = dir_b / max(float(np.linalg.norm(dir_b)), 1e-12)
    cos_t = float(np.clip(np.dot(a, b), -1.0, 1.0))
    theta = math.acos(cos_t)
    sin_t = math.sin(theta) or 1.0
    pts: list[np.ndarray] = []
    for i in range(n + 1):
        t = i / n
        s1 = math.sin((1 - t) * theta) / sin_t
        s2 = math.sin(t * theta) / sin_t
        pts.append((a * s1 + b * s2) * radius)
    return pts


def ground_azimuth_arc(
    from_rad: float, to_rad: float, radius: float, z: float = 0.0, n: int = 36
) -> list[np.ndarray]:
    """Sample the ground-plane azimuth sweep (``n + 1`` points) from *from_rad* to *to_rad*.

    Port of ``scene.jsx`` ``AngleGround``: an arc in the ``z = z`` plane, azimuth measured
    clockwise from ``+Y`` (North) as ``(sin φ, cos φ, z)``, sweeping the shorter way. Used
    for the relative-azimuth (Δφ) arc.
    """
    delta = to_rad - from_rad
    while delta > math.pi:
        delta -= 2 * math.pi
    while delta < -math.pi:
        delta += 2 * math.pi
    pts: list[np.ndarray] = []
    for i in range(n + 1):
        t = from_rad + delta * (i / n)
        pts.append(np.array([radius * math.sin(t), radius * math.cos(t), z], dtype=np.float64))
    return pts
