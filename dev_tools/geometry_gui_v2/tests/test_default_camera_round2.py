"""R1 of round-2 visual remediation — default camera is isometric.

Acceptance:
  * ``build_scene`` leaves the plotter at an isometric three-quarter
    view (no degenerate side view, no axis-aligned pose).
  * ``camera_pose_for("iso")`` returns the same pose so the view-cube
    iso-face click restores the default.
  * Setting ``camera_position`` *before* ``build_scene`` is honored
    (the phase-1 goldens depend on this).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

pytest.importorskip("pyvista")

import pyvista as pv  # noqa: E402

from dev_tools.geometry_gui_v2.app.state import SceneState  # noqa: E402
from dev_tools.geometry_gui_v2.scene.builder import build_scene  # noqa: E402
from dev_tools.geometry_gui_v2.scene.camera_views import (  # noqa: E402
    CANONICAL_DISTANCE_M,
    DEFAULT_ISO_AZ_DEG,
    DEFAULT_ISO_ELEV_DEG,
    camera_pose_for,
    set_default_camera,
)


def _build_off_screen() -> pv.Plotter:
    p = pv.Plotter(off_screen=True, window_size=(640, 480))
    build_scene(SceneState.default(), plotter=p)
    return p


def test_default_camera_view_dir_is_isometric() -> None:
    """Round-2 plan §2 R1 acceptance: in an isometric three-quarter
    view, all three components of the (focal − camera) view direction
    have non-trivial magnitude — none is near zero. This rules out a
    degenerate side / top / front view.
    """
    p = _build_off_screen()
    try:
        cam_pos = np.array(p.camera_position[0])
        focal = np.array(p.camera_position[1])
        view_dir = focal - cam_pos
        view_dir = view_dir / np.linalg.norm(view_dir)
    finally:
        p.close()
    assert all(abs(c) > 0.2 for c in view_dir), (
        f"camera is not isometric: view_dir={view_dir}"
    )


def test_default_camera_matches_iso_pose() -> None:
    """The default-camera helper and ``camera_pose_for('iso')`` agree
    so clicking the view-cube's iso face restores the default view.
    """
    p = pv.Plotter(off_screen=True, window_size=(640, 480))
    try:
        set_default_camera(p)
        actual_pos = tuple(p.camera_position[0])
    finally:
        p.close()
    expected_pos, _focal, _up = camera_pose_for("iso")
    for got, want in zip(actual_pos, expected_pos):
        assert got == pytest.approx(want, abs=1e-9)


def test_default_camera_uses_round2_angles() -> None:
    """Pose places the camera at (d·cos(elev)·cos(az), d·cos(elev)·sin(az), d·sin(elev))
    with elev=25°, az=45° — the round-2 spec, not the legacy phase-1 pose.
    """
    p = pv.Plotter(off_screen=True, window_size=(640, 480))
    try:
        set_default_camera(p)
        pos = p.camera_position[0]
    finally:
        p.close()
    d = CANONICAL_DISTANCE_M
    elev = math.radians(DEFAULT_ISO_ELEV_DEG)
    az = math.radians(DEFAULT_ISO_AZ_DEG)
    assert pos[0] == pytest.approx(d * math.cos(elev) * math.cos(az), abs=1e-9)
    assert pos[1] == pytest.approx(d * math.cos(elev) * math.sin(az), abs=1e-9)
    assert pos[2] == pytest.approx(d * math.sin(elev), abs=1e-9)


def test_set_default_camera_respects_caller_pose() -> None:
    """If the caller has already set ``camera_position`` (e.g. the
    phase-1 golden test pins the legacy pose), ``set_default_camera``
    is a no-op. ``force=True`` overrides for callers that need to
    reset to the default explicitly.
    """
    p = pv.Plotter(off_screen=True, window_size=(640, 480))
    try:
        custom = [(7.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)]
        p.camera_position = custom
        set_default_camera(p)
        # Caller pose is preserved.
        assert tuple(p.camera_position[0]) == pytest.approx((7.0, 0.0, 0.0), abs=1e-9)
        # force=True overrides.
        set_default_camera(p, force=True)
        assert tuple(p.camera_position[0]) != pytest.approx((7.0, 0.0, 0.0), abs=1e-9)
    finally:
        p.close()
