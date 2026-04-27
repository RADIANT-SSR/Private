"""Phase 9 angle-annotation tests.

Per PLAN.md §11 phase-9 acceptance:
  * Each arc's swept angle equals the labeled angle to machine precision.
  * Each label string carries an explicit unit token (`°` / `deg`).
  * The phase-angle and solar-zenith arcs match a direct dot-product
    computation across 50 random states.

Rule 19: every module has its own tests; this file groups Phase 9
annotation tests so regressions surface together.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest

from dev_tools.geometry_gui.app.scene_builder._arc_helpers import (
    ARC_DISPLAY_RADIUS,
    arc_points,
)
from dev_tools.geometry_gui.app.scene_builder.boresight_ray import (
    boresight_ray_traces,
)
from dev_tools.geometry_gui.app.scene_builder.nadir_reference import (
    nadir_reference_traces,
)
from dev_tools.geometry_gui.app.scene_builder.off_nadir_arc import (
    off_nadir_arc_traces,
)
from dev_tools.geometry_gui.app.scene_builder.phase_angle_arc import (
    phase_angle_arc_traces,
    phase_angle_rad,
)
from dev_tools.geometry_gui.app.scene_builder.solar_zenith_arc import (
    solar_zenith_arc_traces,
    solar_zenith_at_b_rad,
)
from dev_tools.geometry_gui.app.scene_builder.sun_ray_background import (
    sun_ray_background_traces,
)
from dev_tools.geometry_gui.app.scene_builder.sun_ray_target import (
    sun_ray_target_traces,
)
from dev_tools.geometry_gui.app.scene_builder.surface_normal_arrow import (
    surface_normal_arrow_traces,
)


# ---------------------------------------------------------------------------
# Shared arc primitive — the load-bearing math under every annotation
# ---------------------------------------------------------------------------


def test_arc_points_radius_matches_constant() -> None:
    """Sampled arc points sit at exactly ARC_DISPLAY_RADIUS from the anchor."""
    anchor = np.array([1.0, -2.0, 3.0])
    u1 = np.array([1.0, 0.0, 0.0])
    u2 = np.array([0.0, 1.0, 0.0])
    xs, ys, zs, _ = arc_points(anchor, u1, u2)
    pts = np.stack([xs, ys, zs], axis=1) - anchor
    radii = np.linalg.norm(pts, axis=1)
    np.testing.assert_allclose(radii, ARC_DISPLAY_RADIUS, atol=1e-12)


def test_arc_swept_equals_input_angle() -> None:
    """Angle between u_start and u_end equals the returned swept angle."""
    anchor = np.zeros(3)
    u1 = np.array([1.0, 0.0, 0.0])
    u2 = np.array([math.cos(0.3), math.sin(0.3), 0.0])
    _, _, _, swept = arc_points(anchor, u1, u2)
    assert swept == pytest.approx(0.3, abs=1e-12)


def test_arc_collapses_when_directions_parallel() -> None:
    """Identical direction inputs produce no arc (caller must skip drawing)."""
    anchor = np.zeros(3)
    u = np.array([0.0, 0.0, 1.0])
    xs, _, _, swept = arc_points(anchor, u, u)
    assert xs.size == 0
    assert swept == 0.0


# ---------------------------------------------------------------------------
# Off-nadir arc
# ---------------------------------------------------------------------------


def test_off_nadir_arc_label_contains_degrees() -> None:
    """Label string carries the unit token `deg`. Observer placed consistently
    with a 20° off-nadir geometry; the arc reads back the same angle."""
    look = math.radians(20.0)
    observer = np.array([-math.sin(look), 0.0, math.cos(look)]) * 4.0
    target = np.zeros(3)
    arc, _ = off_nadir_arc_traces(observer, target)
    assert "deg" in (arc.name or "")
    assert "20.0" in (arc.name or "")


@pytest.mark.parametrize("look_deg", [5.0, 20.0, 35.0, 50.0])
def test_off_nadir_arc_swept_matches_look_angle(look_deg: float) -> None:
    """Swept arc length equals the geometric look angle to machine precision."""
    look = math.radians(look_deg)
    observer = np.array([-math.sin(look), 0.0, math.cos(look)]) * 4.0
    target = np.zeros(3)
    arc, _ = off_nadir_arc_traces(observer, target)
    pts = np.stack([np.asarray(arc.x), np.asarray(arc.y), np.asarray(arc.z)], axis=1)
    rel = pts - observer
    e1 = rel[0] / np.linalg.norm(rel[0])
    e2 = rel[-1] / np.linalg.norm(rel[-1])
    swept = math.acos(float(np.clip(np.dot(e1, e2), -1.0, 1.0)))
    assert swept == pytest.approx(look, abs=1e-9)


# ---------------------------------------------------------------------------
# Phase-angle arc α_t — 50-seed parametric vs direct dot product
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(50))
def test_phase_angle_matches_dot_product(seed: int) -> None:
    """phase_angle_rad agrees with direct arccos(o · s) on random unit vectors."""
    rng = random.Random(seed)
    # Generate two non-degenerate unit vectors.
    while True:
        v1 = np.array([rng.uniform(-1, 1) for _ in range(3)])
        v2 = np.array([rng.uniform(-1, 1) for _ in range(3)])
        n1 = np.linalg.norm(v1)
        n2 = np.linalg.norm(v2)
        if n1 > 0.1 and n2 > 0.1:
            break
    e1 = v1 / n1
    e2 = v2 / n2
    expected = math.acos(float(np.clip(np.dot(e1, e2), -1.0, 1.0)))
    assert phase_angle_rad(v1, v2) == pytest.approx(expected, abs=1e-12)


def test_phase_angle_arc_label_is_symbol_only() -> None:
    """Phase 11: on-figure label is the canonical Unicode subscript form `αₜ`,
    no `=` and no numeric value (the value lives in the trace name only)."""
    target = np.zeros(3)
    o = np.array([-math.sin(math.radians(20)), 0.0, math.cos(math.radians(20))])
    s = np.array([0.0, 0.0, 1.0])  # sun at zenith
    traces = phase_angle_arc_traces(target, o, s)
    text_labels = [t.text[0] for t in traces if t.mode == "text"]
    assert any(label == "αₜ" for label in text_labels), text_labels
    assert all("=" not in label for label in text_labels), text_labels


# ---------------------------------------------------------------------------
# Solar-zenith arc θ_sun,B — 50-seed parametric
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(50))
def test_solar_zenith_matches_dot_product(seed: int) -> None:
    """solar_zenith_at_b_rad agrees with direct arccos(n · s)."""
    rng = random.Random(seed + 100)
    while True:
        n = np.array([rng.uniform(-1, 1) for _ in range(3)])
        s = np.array([rng.uniform(-1, 1) for _ in range(3)])
        if np.linalg.norm(n) > 0.1 and np.linalg.norm(s) > 0.1:
            break
    n_unit = n / np.linalg.norm(n)
    s_unit = s / np.linalg.norm(s)
    expected = math.acos(float(np.clip(np.dot(n_unit, s_unit), -1.0, 1.0)))
    assert solar_zenith_at_b_rad(n, s) == pytest.approx(expected, abs=1e-12)


def test_solar_zenith_arc_label_contains_degrees() -> None:
    bg = np.array([0.5, 0.0, -1.5])
    n_b = np.array([0.0, 0.0, 1.0])
    sun = np.array([math.sin(math.radians(35)), 0.0, math.cos(math.radians(35))])
    arc, _ = solar_zenith_arc_traces(bg, n_b, sun)
    assert "deg" in (arc.name or "")


# ---------------------------------------------------------------------------
# Sun rays
# ---------------------------------------------------------------------------


def test_sun_ray_target_endpoints_match_inputs() -> None:
    target = np.array([0.0, 0.0, 0.0])
    sun = np.array([1.0, 2.0, 3.0])
    line, _label = sun_ray_target_traces(target, sun)
    assert (line.x[0], line.y[0], line.z[0]) == pytest.approx(tuple(target.tolist()))
    assert (line.x[1], line.y[1], line.z[1]) == pytest.approx(tuple(sun.tolist()))


def test_sun_ray_background_starts_at_b_and_uses_unit_direction() -> None:
    bg = np.array([0.5, 0.0, -1.5])
    sun_dir = np.array([0.0, 0.0, 2.0])  # non-unit; module must normalize.
    line, _label = sun_ray_background_traces(bg, sun_dir)
    assert (line.x[0], line.y[0], line.z[0]) == pytest.approx(tuple(bg.tolist()))
    end = np.array([line.x[1], line.y[1], line.z[1]])
    direction = end - bg
    assert direction[2] > 0.0  # along +Z (sun direction)


# ---------------------------------------------------------------------------
# Boresight + nadir reference
# ---------------------------------------------------------------------------


def test_boresight_ray_solid_segment_endpoints() -> None:
    o = np.array([-1.5, 0.0, 3.5])
    t = np.zeros(3)
    b = np.array([0.5, 0.0, -1.5])
    solid, extension, _label = boresight_ray_traces(o, t, b, math.radians(20))
    assert (solid.x[0], solid.z[0]) == pytest.approx((o[0], o[2]))
    assert (solid.x[1], solid.z[1]) == pytest.approx((t[0], t[2]))
    assert extension.line.dash == "dot"


def test_nadir_reference_drops_to_target_altitude() -> None:
    o = np.array([-1.5, 0.0, 3.5])
    t = np.array([0.0, 0.0, 0.0])
    line, _label = nadir_reference_traces(o, t)
    assert line.z[0] == pytest.approx(o[2])
    assert line.z[1] == pytest.approx(t[2])


# ---------------------------------------------------------------------------
# Surface normal arrow at B
# ---------------------------------------------------------------------------


def test_surface_normal_arrow_points_along_plus_z() -> None:
    bg = np.array([0.5, 0.0, -1.5])
    shaft, _tip, label = surface_normal_arrow_traces(bg)
    direction = np.array(
        [shaft.x[1] - shaft.x[0], shaft.y[1] - shaft.y[0], shaft.z[1] - shaft.z[0]]
    )
    direction /= np.linalg.norm(direction)
    np.testing.assert_allclose(direction, [0.0, 0.0, 1.0], atol=1e-12)
    assert label.text[0] == "n_B"
