"""Phase 10 angle-projection tests.

Per PLAN.md §11 phase-10 acceptance:
  * Each projected arc lies in its declared plane to machine precision.
  * Projections render as dashed lines (`dash == "dot"`), low opacity.
  * Degenerate cases (parent arc empty) produce no projection traces.

Rule 19: every module has its own tests; this file groups Phase 10
projection tests so regressions surface together.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from dev_tools.geometry_gui.app.scene_builder.off_nadir_projection import (
    off_nadir_projection_traces,
)
from dev_tools.geometry_gui.app.scene_builder.phase_angle_projection import (
    phase_angle_projection_traces,
)
from dev_tools.geometry_gui.app.scene_builder.solar_zenith_projection import (
    solar_zenith_projection_traces,
)


def _arc_xyz(trace) -> np.ndarray:
    return np.stack(
        [np.asarray(trace.x), np.asarray(trace.y), np.asarray(trace.z)], axis=1
    )


# ---------------------------------------------------------------------------
# Off-nadir projection — XZ plane at observer
# ---------------------------------------------------------------------------


def test_off_nadir_projection_lies_in_observer_xz_plane() -> None:
    """All projected points have y == observer.y to machine precision."""
    look = math.radians(20.0)
    observer = np.array([-math.sin(look), 0.5, math.cos(look)]) * 4.0  # off-XZ
    target = np.zeros(3)
    traces = off_nadir_projection_traces(observer, target)
    arc = traces[0]
    pts = _arc_xyz(arc)
    np.testing.assert_allclose(pts[:, 1], observer[1], atol=1e-12)


def test_off_nadir_projection_is_dashed_low_opacity() -> None:
    look = math.radians(20.0)
    observer = np.array([-math.sin(look), 0.0, math.cos(look)]) * 4.0
    target = np.zeros(3)
    traces = off_nadir_projection_traces(observer, target)
    assert traces[0].line.dash == "dot"
    assert (traces[0].opacity or 1.0) <= 0.7


# ---------------------------------------------------------------------------
# Phase-angle projection — target's tangent plane (XY at target)
# ---------------------------------------------------------------------------


def test_phase_angle_projection_lies_in_target_tangent_plane() -> None:
    """All projected points have z == target.z to machine precision."""
    target = np.zeros(3)
    o = np.array([-math.sin(math.radians(20)), 0.0, math.cos(math.radians(20))])
    s = np.array(
        [math.sin(math.radians(35)), 0.2, math.cos(math.radians(35))]
    )
    traces = phase_angle_projection_traces(target, o, s)
    arc = traces[0]
    pts = _arc_xyz(arc)
    np.testing.assert_allclose(pts[:, 2], target[2], atol=1e-12)


# ---------------------------------------------------------------------------
# Solar-zenith projection — ground plane at B
# ---------------------------------------------------------------------------


def test_solar_zenith_projection_lies_in_ground_plane_at_b() -> None:
    """All projected points have z == B.z to machine precision."""
    bg = np.array([0.5, 0.0, -1.5])
    n_b = np.array([0.0, 0.0, 1.0])
    sun = np.array([math.sin(math.radians(35)), 0.0, math.cos(math.radians(35))])
    traces = solar_zenith_projection_traces(bg, n_b, sun)
    arc = traces[0]
    pts = _arc_xyz(arc)
    np.testing.assert_allclose(pts[:, 2], bg[2], atol=1e-12)


# ---------------------------------------------------------------------------
# Degenerate cases
# ---------------------------------------------------------------------------


def test_phase_angle_projection_empty_when_directions_parallel() -> None:
    target = np.zeros(3)
    u = np.array([0.0, 0.0, 1.0])
    assert phase_angle_projection_traces(target, u, u) == []


def test_solar_zenith_projection_empty_when_sun_along_normal() -> None:
    bg = np.array([0.5, 0.0, -1.5])
    n_b = np.array([0.0, 0.0, 1.0])
    sun = np.array([0.0, 0.0, 1.0])
    assert solar_zenith_projection_traces(bg, n_b, sun) == []
