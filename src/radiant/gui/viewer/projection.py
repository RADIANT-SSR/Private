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
    "dir_from_az_zen",
    "make_camera",
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


def make_camera(
    yaw_deg: float, pitch_deg: float, scale_px: float, cx: float, cy: float
) -> Camera:
    """Construct a :class:`Camera` (mirrors the ``geometry.js`` ``makeCamera`` factory)."""
    return Camera(yaw_deg=yaw_deg, pitch_deg=pitch_deg, scale_px=scale_px, cx=cx, cy=cy)
