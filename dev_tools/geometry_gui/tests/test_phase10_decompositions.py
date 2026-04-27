"""Phase 10 angle-decomposition + world-axes tests.

Per PLAN.md §11 phase-10 acceptance:
  * Az/el reconstruct the boresight to machine precision.
  * Sun zenith arc and azimuth arc agree with direct atan2/arccos
    computations on the sun direction across 50 random states.
  * World-axes triad is three orthogonal unit-length lines along +X/+Y/+Z.
  * Empty / degenerate cases produce no traces (caller renders nothing).

Rule 19: every module has its own tests; this file groups Phase 10
decomposition tests so regressions surface together.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest

from dev_tools.geometry_gui.app.scene_builder.azimuth_arc import (
    azimuth_arc_traces,
    view_azimuth_rad,
)
from dev_tools.geometry_gui.app.scene_builder.elevation_arc import (
    elevation_arc_traces,
    view_elevation_rad,
)
from dev_tools.geometry_gui.app.scene_builder.sun_azimuth_arc import (
    sun_azimuth_arc_traces,
    sun_azimuth_rad,
)
from dev_tools.geometry_gui.app.scene_builder.sun_zenith_arc import (
    sun_zenith_arc_traces,
    sun_zenith_at_target_rad,
)
from dev_tools.geometry_gui.app.scene_builder.world_axes_triad import (
    WORLD_AXIS_DISPLAY_LENGTH,
    world_axes_triad_traces,
)


# ---------------------------------------------------------------------------
# Az/el decomposition — reconstruct boresight from (az, el) and original
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(50))
def test_az_el_reconstruct_boresight(seed: int) -> None:
    """az/el are measured on the *view* (target → observer = −boresight).
    Given az = atan2(view_y, view_x), el = arcsin(view_z), reconstructing
    view = (cos el cos az, cos el sin az, sin el) and negating must
    return the original unit boresight."""
    rng = random.Random(seed)
    while True:
        v = np.array([rng.uniform(-1.0, 1.0) for _ in range(3)])
        # Force boresight into −Z half (observer→target hits the ground).
        if v[2] >= 0.0:
            v[2] = -abs(v[2]) - 0.05
        n = float(np.linalg.norm(v))
        if n > 0.1:
            break
    b = v / n

    az = view_azimuth_rad(b)
    el = view_elevation_rad(b)
    view = np.array(
        [math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)]
    )
    reconstructed = -view
    np.testing.assert_allclose(reconstructed, b, atol=1e-12)


def test_azimuth_arc_canonical_observer_along_minus_x() -> None:
    """Canonical observer in the −X/+Z quadrant: view = (−sin θ, 0, +cos θ)
    has its XY-projection along −X, so az = 180° (anti-parallel to +X).
    The arc spans π — non-empty and labeled ~180°."""
    boresight = np.array([math.sin(math.radians(20)), 0.0, -math.cos(math.radians(20))])
    target = np.zeros(3)
    traces = azimuth_arc_traces(target, boresight)
    arc = next(t for t in traces if t.mode == "lines")
    assert "180.0 deg" in (arc.name or "") or "180.0" in (arc.name or "")


def test_azimuth_arc_label_contains_degrees() -> None:
    """An off-meridian boresight produces an arc with `deg` in its name."""
    boresight = np.array([0.5, 0.5, -math.sqrt(0.5)])
    target = np.zeros(3)
    traces = azimuth_arc_traces(target, boresight / np.linalg.norm(boresight))
    assert any("deg" in (t.name or "") for t in traces if t.mode == "lines")


def test_elevation_arc_label_and_swept_match() -> None:
    """Elevation arc swept angle matches the boresight-elevation helper."""
    look = math.radians(20.0)
    boresight = np.array([math.sin(look), 0.0, -math.cos(look)])
    target = np.zeros(3)
    traces = elevation_arc_traces(target, boresight)
    assert any("deg" in (t.name or "") for t in traces if t.mode == "lines")
    # Reconstruct swept angle from the arc geometry.
    arc = next(t for t in traces if t.mode == "lines")
    pts = np.stack([np.asarray(arc.x), np.asarray(arc.y), np.asarray(arc.z)], axis=1)
    rel = pts - target
    e1 = rel[0] / np.linalg.norm(rel[0])
    e2 = rel[-1] / np.linalg.norm(rel[-1])
    swept = math.acos(float(np.clip(np.dot(e1, e2), -1.0, 1.0)))
    assert swept == pytest.approx(view_elevation_rad(boresight), abs=1e-9)


# ---------------------------------------------------------------------------
# Sun decomposition — 50-seed parametric vs direct trig
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(50))
def test_sun_zenith_matches_arccos_z(seed: int) -> None:
    rng = random.Random(seed + 200)
    while True:
        s = np.array([rng.uniform(-1, 1) for _ in range(3)])
        if np.linalg.norm(s) > 0.1:
            break
    expected = math.acos(float(np.clip(s[2] / np.linalg.norm(s), -1.0, 1.0)))
    assert sun_zenith_at_target_rad(s) == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("seed", range(50))
def test_sun_azimuth_matches_atan2(seed: int) -> None:
    rng = random.Random(seed + 300)
    while True:
        s = np.array([rng.uniform(-1, 1) for _ in range(3)])
        if math.hypot(s[0], s[1]) > 0.05:
            break
    expected = math.atan2(s[1], s[0])
    assert sun_azimuth_rad(s) == pytest.approx(expected, abs=1e-12)


def test_sun_zenith_arc_label_is_symbol_only() -> None:
    """Phase 11: on-figure label is `θₛ` (Unicode subscript). Numeric value
    lives in the trace name only — no `=` or digit on the figure."""
    target = np.zeros(3)
    sun = np.array([math.sin(math.radians(35)), 0.0, math.cos(math.radians(35))])
    traces = sun_zenith_arc_traces(target, sun)
    text_labels = [t.text[0] for t in traces if t.mode == "text"]
    assert any(label == "θₛ" for label in text_labels), text_labels
    assert all("=" not in label for label in text_labels), text_labels


def test_sun_azimuth_arc_collapses_when_sun_overhead() -> None:
    target = np.zeros(3)
    sun = np.array([0.0, 0.0, 1.0])
    assert sun_azimuth_arc_traces(target, sun) == []


# ---------------------------------------------------------------------------
# World axes triad — three orthogonal unit lines from origin
# ---------------------------------------------------------------------------


def test_world_axes_triad_three_orthogonal_lines() -> None:
    traces = world_axes_triad_traces()
    line_traces = [t for t in traces if t.mode == "lines"]
    assert len(line_traces) == 3

    directions = []
    for line in line_traces:
        start = np.array([line.x[0], line.y[0], line.z[0]])
        end = np.array([line.x[1], line.y[1], line.z[1]])
        np.testing.assert_allclose(start, [0.0, 0.0, 0.0], atol=1e-12)
        d = end - start
        np.testing.assert_allclose(np.linalg.norm(d), WORLD_AXIS_DISPLAY_LENGTH, atol=1e-12)
        directions.append(d / np.linalg.norm(d))

    dirs = np.stack(directions, axis=0)
    # Pairwise orthogonality.
    for i in range(3):
        for j in range(i + 1, 3):
            assert abs(float(np.dot(dirs[i], dirs[j]))) < 1e-12
    # Span the global axes (each line is along ±X, ±Y, ±Z).
    expected = {(1, 0, 0), (0, 1, 0), (0, 0, 1)}
    seen = {tuple(np.round(d).astype(int).tolist()) for d in directions}
    assert seen == expected


def test_world_axes_triad_label_text_is_axis_name() -> None:
    traces = world_axes_triad_traces()
    text_traces = [t for t in traces if t.mode == "text"]
    labels = {t.text[0] for t in text_traces}
    assert labels == {"X", "Y", "Z"}
