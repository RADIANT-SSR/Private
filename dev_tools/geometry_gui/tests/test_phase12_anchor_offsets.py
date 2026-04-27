"""Phase 12 anchor-offset acceptance tests.

Per PLAN.md §13:
  * Per-anchor outward-offset table is the single source of truth.
  * Target-anchored arcs sit at `vertex + offset * bisector(u1, u2)`.
  * Each target-anchored arc emits one leader-line trace from the
    physical vertex to the arc's geometric center.
  * Observer / background / sun arcs (offset = 0) emit no leader line.
  * Swept-angle output of every arc helper is unchanged from Phase 11
    (the offset shifts the anchor, not the math).
  * Default-state target-arc traces sit outside the cone target's
    bounding box (the largest mesh).

Rule 19: each test exists for one acceptance bullet.
"""

from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go
import pytest

from dev_tools.geometry_gui.app.scene_builder._arc_offsets import (
    ARC_OUTWARD_OFFSETS,
    bisector,
    offset_for,
    shifted_anchor,
)
from dev_tools.geometry_gui.app.scene_builder.arc_leader_line import (
    arc_leader_line_traces,
)
from dev_tools.geometry_gui.app.scene_builder.azimuth_arc import azimuth_arc_traces
from dev_tools.geometry_gui.app.scene_builder.build_scene import build_scene
from dev_tools.geometry_gui.app.scene_builder.elevation_arc import (
    elevation_arc_traces,
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
)
from dev_tools.geometry_gui.app.scene_builder.sun_azimuth_arc import (
    sun_azimuth_arc_traces,
)
from dev_tools.geometry_gui.app.scene_builder.sun_zenith_arc import (
    sun_zenith_arc_traces,
)
from dev_tools.geometry_gui.app.state import SceneState


# ---------------------------------------------------------------------------
# (a) Offset table is the single source of truth.
# ---------------------------------------------------------------------------


def test_offset_table_keys_match_anchor_palette() -> None:
    """Every anchor used by the palette has an entry in the offset table."""
    expected = {"observer", "target", "background", "sun"}
    assert set(ARC_OUTWARD_OFFSETS.keys()) == expected


def test_only_target_anchor_has_nonzero_offset() -> None:
    """Today only the target needs an outward offset; the others sit in clear space."""
    assert offset_for("target") > 0.0
    assert offset_for("observer") == 0.0
    assert offset_for("background") == 0.0
    assert offset_for("sun") == 0.0


def test_offset_for_unknown_key_raises() -> None:
    with pytest.raises(KeyError):
        offset_for("not_an_anchor")


# ---------------------------------------------------------------------------
# Bisector primitive.
# ---------------------------------------------------------------------------


def test_bisector_of_orthogonal_unit_vectors() -> None:
    u1 = np.array([1.0, 0.0, 0.0])
    u2 = np.array([0.0, 1.0, 0.0])
    b = bisector(u1, u2)
    np.testing.assert_allclose(b, np.array([1.0, 1.0, 0.0]) / math.sqrt(2.0), atol=1e-12)


def test_bisector_falls_back_when_anti_parallel() -> None:
    """Anti-parallel sum has zero norm; helper returns a finite perpendicular."""
    u1 = np.array([1.0, 0.0, 0.0])
    u2 = np.array([-1.0, 0.0, 0.0])
    b = bisector(u1, u2)
    assert math.isclose(float(np.linalg.norm(b)), 1.0, abs_tol=1e-12)
    # Must be perpendicular to u1 (no component along x).
    assert abs(float(np.dot(b, u1))) < 1e-12


def test_shifted_anchor_zero_offset_returns_anchor_unchanged() -> None:
    a = np.array([1.0, 2.0, 3.0])
    u1 = np.array([1.0, 0.0, 0.0])
    u2 = np.array([0.0, 1.0, 0.0])
    out = shifted_anchor(a, u1, u2, "observer")
    np.testing.assert_allclose(out, a, atol=1e-12)


def test_shifted_anchor_target_offsets_along_bisector() -> None:
    a = np.zeros(3)
    u1 = np.array([1.0, 0.0, 0.0])
    u2 = np.array([0.0, 0.0, 1.0])
    out = shifted_anchor(a, u1, u2, "target")
    expected_dir = np.array([1.0, 0.0, 1.0]) / math.sqrt(2.0)
    np.testing.assert_allclose(out, offset_for("target") * expected_dir, atol=1e-12)


# ---------------------------------------------------------------------------
# (b) Target-anchored arcs apply the shift before arc_points().
# ---------------------------------------------------------------------------


def _arc_center(arc: go.Scatter3d) -> np.ndarray:
    pts = np.stack([np.asarray(arc.x), np.asarray(arc.y), np.asarray(arc.z)], axis=1)
    return pts.mean(axis=0)


def test_phase_angle_arc_anchor_is_shifted_off_target() -> None:
    """α_t arc samples lie at distance ≥ offset_for('target') − radius from target."""
    t = np.zeros(3)
    o = np.array([-math.sin(math.radians(20)), 0.0, math.cos(math.radians(20))])
    s = np.array([0.0, 0.0, 1.0])
    traces = phase_angle_arc_traces(t, o, s)
    arc = next(tr for tr in traces if tr.mode == "lines")
    pts = np.stack([np.asarray(arc.x), np.asarray(arc.y), np.asarray(arc.z)], axis=1)
    distances = np.linalg.norm(pts - t, axis=1)
    # Every sample sits strictly outside the unit-radius target.
    assert distances.min() > 1.0


def test_sun_zenith_arc_anchor_is_shifted_off_target() -> None:
    t = np.zeros(3)
    sun = np.array([math.sin(math.radians(35)), 0.0, math.cos(math.radians(35))])
    traces = sun_zenith_arc_traces(t, sun)
    arc = next(tr for tr in traces if tr.mode == "lines")
    pts = np.stack([np.asarray(arc.x), np.asarray(arc.y), np.asarray(arc.z)], axis=1)
    distances = np.linalg.norm(pts - t, axis=1)
    assert distances.min() > 1.0


def test_sun_azimuth_arc_anchor_is_shifted_off_target() -> None:
    t = np.zeros(3)
    sun = np.array([0.5, 0.5, 0.7071])
    traces = sun_azimuth_arc_traces(t, sun)
    arc = next(tr for tr in traces if tr.mode == "lines")
    pts = np.stack([np.asarray(arc.x), np.asarray(arc.y), np.asarray(arc.z)], axis=1)
    distances = np.linalg.norm(pts - t, axis=1)
    assert distances.min() > 1.0


# ---------------------------------------------------------------------------
# Swept-angle invariant — translation does not change the angle.
# ---------------------------------------------------------------------------


def test_phase_angle_swept_unchanged_after_shift() -> None:
    """Phase-12 only translates; the arc's swept angle equals the pre-shift α_t.

    Reconstructed from the arc's *shifted* anchor (the geometric center of
    the arc samples is the chord midpoint, not the anchor — so this test
    must use the analytic anchor to recover the radial directions).
    """
    t = np.zeros(3)
    o = np.array([-math.sin(math.radians(20)), 0.0, math.cos(math.radians(20))])
    s = np.array([0.0, 0.0, 1.0])
    expected = phase_angle_rad(o, s)
    traces = phase_angle_arc_traces(t, o, s)
    arc = next(tr for tr in traces if tr.mode == "lines" and "alpha_t" in (tr.name or "") and "leader" not in (tr.name or ""))
    pts = np.stack([np.asarray(arc.x), np.asarray(arc.y), np.asarray(arc.z)], axis=1)
    anchor = shifted_anchor(t, o, s, "target")
    e_first = pts[0] - anchor
    e_last = pts[-1] - anchor
    e_first /= np.linalg.norm(e_first)
    e_last /= np.linalg.norm(e_last)
    swept_geom = math.acos(float(np.clip(np.dot(e_first, e_last), -1.0, 1.0)))
    assert swept_geom == pytest.approx(expected, abs=1e-9)


# ---------------------------------------------------------------------------
# (e) Leader line traces.
# ---------------------------------------------------------------------------


def test_phase_angle_arc_emits_one_leader_line() -> None:
    t = np.zeros(3)
    o = np.array([-math.sin(math.radians(20)), 0.0, math.cos(math.radians(20))])
    s = np.array([0.0, 0.0, 1.0])
    traces = phase_angle_arc_traces(t, o, s)
    leaders = [
        tr for tr in traces if tr.mode == "lines" and "leader" in (tr.name or "")
    ]
    assert len(leaders) == 1


def test_sun_zenith_arc_emits_one_leader_line() -> None:
    t = np.zeros(3)
    sun = np.array([math.sin(math.radians(35)), 0.0, math.cos(math.radians(35))])
    traces = sun_zenith_arc_traces(t, sun)
    leaders = [
        tr for tr in traces if tr.mode == "lines" and "leader" in (tr.name or "")
    ]
    assert len(leaders) == 1


def test_sun_azimuth_arc_emits_one_leader_line() -> None:
    t = np.zeros(3)
    sun = np.array([0.5, 0.5, 0.7071])
    traces = sun_azimuth_arc_traces(t, sun)
    leaders = [
        tr for tr in traces if tr.mode == "lines" and "leader" in (tr.name or "")
    ]
    assert len(leaders) == 1


def test_leader_line_endpoints_are_vertex_and_arc_center() -> None:
    """For a default-ish phase-angle case, the leader runs vertex → shifted center."""
    t = np.zeros(3)
    o = np.array([-math.sin(math.radians(20)), 0.0, math.cos(math.radians(20))])
    s = np.array([0.0, 0.0, 1.0])
    traces = phase_angle_arc_traces(t, o, s)
    leader = next(tr for tr in traces if "leader" in (tr.name or ""))
    start = np.array([leader.x[0], leader.y[0], leader.z[0]])
    end = np.array([leader.x[1], leader.y[1], leader.z[1]])
    np.testing.assert_allclose(start, t, atol=1e-12)
    expected_anchor = shifted_anchor(t, o, s, "target")
    np.testing.assert_allclose(end, expected_anchor, atol=1e-12)


# ---------------------------------------------------------------------------
# Observer / background / sun arcs do NOT emit leaders (offset = 0).
# ---------------------------------------------------------------------------


def test_off_nadir_arc_emits_no_leader_line() -> None:
    observer = np.array([-math.sin(math.radians(20)), 0.0, math.cos(math.radians(20))]) * 4.0
    target = np.zeros(3)
    traces = off_nadir_arc_traces(observer, target)
    leaders = [
        tr for tr in traces if tr.mode == "lines" and "leader" in (tr.name or "")
    ]
    assert leaders == []


def test_azimuth_arc_emits_no_leader_line() -> None:
    target = np.zeros(3)
    boresight = np.array([math.sin(math.radians(20)), 0.0, -math.cos(math.radians(20))])
    traces = azimuth_arc_traces(target, boresight)
    leaders = [
        tr for tr in traces if tr.mode == "lines" and "leader" in (tr.name or "")
    ]
    assert leaders == []


def test_elevation_arc_emits_no_leader_line() -> None:
    target = np.zeros(3)
    boresight = np.array([math.sin(math.radians(20)), 0.0, -math.cos(math.radians(20))])
    traces = elevation_arc_traces(target, boresight)
    leaders = [
        tr for tr in traces if tr.mode == "lines" and "leader" in (tr.name or "")
    ]
    assert leaders == []


def test_solar_zenith_arc_emits_no_leader_line() -> None:
    bg = np.array([0.5, 0.0, -1.5])
    n_b = np.array([0.0, 0.0, 1.0])
    sun = np.array([math.sin(math.radians(35)), 0.0, math.cos(math.radians(35))])
    traces = solar_zenith_arc_traces(bg, n_b, sun)
    leaders = [
        tr for tr in traces if tr.mode == "lines" and "leader" in (tr.name or "")
    ]
    assert leaders == []


# ---------------------------------------------------------------------------
# Leader-line helper unit behavior.
# ---------------------------------------------------------------------------


def test_leader_helper_skips_when_endpoints_coincide() -> None:
    a = np.array([1.0, 2.0, 3.0])
    out = arc_leader_line_traces(a, a, "#000000", leader_name="x")
    assert out == []


def test_leader_helper_emits_one_dotted_scatter3d_when_offset() -> None:
    a = np.zeros(3)
    b = np.array([1.0, 0.0, 0.0])
    out = arc_leader_line_traces(a, b, "#abcdef", leader_name="x")
    assert len(out) == 1
    line = out[0]
    assert line.mode == "lines"
    assert line.line.dash == "dot"
    assert line.line.color == "#abcdef"


# ---------------------------------------------------------------------------
# (g) Default-state full-scene check — target arcs sit clear of the cone mesh.
# ---------------------------------------------------------------------------


def test_target_arcs_clear_cone_mesh_in_default_scene() -> None:
    """For the largest mesh (cone), every target-anchored arc sample lies
    strictly outside the mesh's bounding box. This is the user-visible
    Phase-12 acceptance criterion."""
    state = SceneState.default()
    state = SceneState(**{**state.__dict__, "target_shape": "cone"})
    traces = build_scene(
        state,
        regime=None,
        view_dir_scene=None,
        projected_area_m2=1.0,
        angle_groups=frozenset({"target", "sun"}),
    )

    cone_mesh = next(tr for tr in traces if "Target (cone)" in (tr.name or ""))
    cone_pts = np.stack(
        [np.asarray(cone_mesh.x), np.asarray(cone_mesh.y), np.asarray(cone_mesh.z)],
        axis=1,
    )
    cone_min = cone_pts.min(axis=0)
    cone_max = cone_pts.max(axis=0)

    target_arc_keys = ("alpha_t", "theta_s", "delta_phi")
    arc_traces = [
        tr
        for tr in traces
        if isinstance(tr, go.Scatter3d)
        and tr.mode == "lines"
        and any(key in (tr.name or "") for key in target_arc_keys)
        and "leader" not in (tr.name or "")
    ]
    assert arc_traces, "expected at least one target-anchored arc trace"

    for arc in arc_traces:
        pts = np.stack(
            [np.asarray(arc.x), np.asarray(arc.y), np.asarray(arc.z)], axis=1
        )
        # An arc clears the mesh when at least one axis has every point
        # outside the mesh's range on that axis.
        outside_per_axis = [
            np.all(pts[:, i] < cone_min[i]) or np.all(pts[:, i] > cone_max[i])
            for i in range(3)
        ]
        assert any(outside_per_axis), (
            f"arc '{arc.name}' overlaps cone bbox: "
            f"arc range x={pts[:,0].min():.3f}..{pts[:,0].max():.3f}, "
            f"y={pts[:,1].min():.3f}..{pts[:,1].max():.3f}, "
            f"z={pts[:,2].min():.3f}..{pts[:,2].max():.3f}; "
            f"cone bbox={cone_min}..{cone_max}"
        )
