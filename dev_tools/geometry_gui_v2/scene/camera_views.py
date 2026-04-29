"""Canonical-view camera poses — front / back / left / right / top / bottom / iso.

Phase 5 (PLAN_v2.md §13 step 1): the view-cube widget animates the
camera to one of seven canonical poses on click. ``camera_pose_for``
returns the ``(position, focal_point, view_up)`` triple PyVista's
``Plotter.camera_position`` accepts.

R1 of round-2 visual remediation replaces the legacy iso pose
(elev = arctan(0.5) ≈ 26.6°, az = 35°) with the round-2 spec
isometric three-quarter view (elev = 25°, az = 45°). The new
convention separates the boresight, sun ray, and surface normal into
three distinct screen-space directions in the default cylinder frame
— the legacy pose stacked them onto a near-vertical column at low
elevation. ``CANONICAL_DISTANCE_M`` is unchanged; R2 will replace
the hardcoded distance with an extent-driven framing policy.

All poses look at the target centroid (origin) at a fixed schematic
distance. The distance is large enough that all Phase 4 anchors
(observer at z=6 m, sun at z=9 m, background at z=12 m) fit in frame
without zoom adjustment.

Pure function. No PyVista dependency on the inputs; the *output*
shape matches PyVista's expected ``camera_position`` tuple but is
just a list of three 3-tuples — testable without a renderer.
"""

from __future__ import annotations

import math
from typing import Final, TYPE_CHECKING

CANONICAL_DISTANCE_M: Final[float] = 14.0

# R1: isometric three-quarter angles per round-2 plan §2 step 2.
DEFAULT_ISO_ELEV_DEG: Final[float] = 25.0
DEFAULT_ISO_AZ_DEG: Final[float] = 45.0

if TYPE_CHECKING:  # pragma: no cover
    import pyvista as pv


def _iso_position(distance: float) -> tuple[float, float, float]:
    elev = math.radians(DEFAULT_ISO_ELEV_DEG)
    az = math.radians(DEFAULT_ISO_AZ_DEG)
    return (
        distance * math.cos(elev) * math.cos(az),
        distance * math.cos(elev) * math.sin(az),
        distance * math.sin(elev),
    )


def camera_pose_for(
    view: str,
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    """Return ``(position, focal_point, view_up)`` for the named view.

    ``view`` must be one of: front, back, left, right, top, bottom, iso.
    Raises ValueError for any other string — callers should pass an
    enum value (``CanonicalView.value``) so this is unreachable in the
    UI; the explicit raise is for unit-test clarity.
    """
    d = CANONICAL_DISTANCE_M
    focal = (0.0, 0.0, 0.0)

    if view == "front":
        return (d, 0.0, 0.0), focal, (0.0, 0.0, 1.0)
    if view == "back":
        return (-d, 0.0, 0.0), focal, (0.0, 0.0, 1.0)
    if view == "left":
        return (0.0, d, 0.0), focal, (0.0, 0.0, 1.0)
    if view == "right":
        return (0.0, -d, 0.0), focal, (0.0, 0.0, 1.0)
    if view == "top":
        return (0.0, 0.0, d), focal, (0.0, 1.0, 0.0)
    if view == "bottom":
        return (0.0, 0.0, -d), focal, (0.0, 1.0, 0.0)
    if view == "iso":
        return _iso_position(d), focal, (0.0, 0.0, 1.0)
    raise ValueError(
        f"camera_pose_for: unknown view {view!r}. "
        f"Expected one of: front, back, left, right, top, bottom, iso."
    )


def set_default_camera(
    plotter: "pv.Plotter",
    target_centroid: tuple[float, float, float] = (0.0, 0.0, 0.0),
    distance: float = CANONICAL_DISTANCE_M,
    force: bool = False,
) -> None:
    """Set the plotter to the round-2 default isometric three-quarter view.

    R1 of visual remediation: the default the user sees on app launch
    and the pose the view-cube's iso face restores. R2 makes the
    distance argument extent-driven — call sites pass
    ``framing.default_camera_distance_m(state)`` so the scene fills the
    majority of the canvas (see ``scene/framing.py``). The
    ``CANONICAL_DISTANCE_M`` default is preserved for callers that
    don't have a ``SceneState`` handy (tests, snap-to-iso from the
    view-cube).

    Idempotency: if the caller has already set ``plotter.camera_position``
    explicitly (PyVista's ``camera_set`` flag is True), this function is
    a no-op unless ``force=True``. That keeps the phase-1 golden test's
    locally-pinned legacy pose working: that test sets its camera
    *before* ``build_scene`` and expects the build pipeline to leave it
    alone.

    The caller MUST NOT call ``plotter.reset_camera()`` after this — it
    discards the explicit pose. Use ``camera_pose_for("iso")`` from
    other call sites (snap-to-view) for the same view.
    """
    if not force and getattr(plotter, "camera_set", False):
        return
    offset = _iso_position(distance)
    cx, cy, cz = target_centroid
    plotter.camera_position = [
        (cx + offset[0], cy + offset[1], cz + offset[2]),
        target_centroid,
        (0.0, 0.0, 1.0),
    ]
