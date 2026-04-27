"""Phase 5 silhouette-disk tests.

Pin geometry of `silhouette_disk_traces` and integration into `build_scene`:
  * Disk is omitted when A_t == 0.
  * Disk normal aligns with the view direction (face-on to observer).
  * Disk is added in SUB_PIXEL / default regimes only — never in EXTENDED
    or POINT_SOURCE (those override the shape representation entirely).
  * Hover text and trace name carry A_t in m² (units rule).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.regime import RadiometricRegime

from dev_tools.geometry_gui.app.scene_builder.build_scene import build_scene
from dev_tools.geometry_gui.app.scene_builder.silhouette_disk import (
    silhouette_disk_traces,
)
from dev_tools.geometry_gui.app.state import SceneState


# ---------------------------------------------------------------------------
# silhouette_disk_traces — direct unit tests
# ---------------------------------------------------------------------------


def test_silhouette_omitted_for_zero_area() -> None:
    traces = silhouette_disk_traces(
        np.array([0.0, 0.0, 1.0]),
        np.array([0.0, 0.0, -1.0]),
        projected_area_m2=0.0,
    )
    assert traces == []


def test_silhouette_normal_aligns_with_view_dir() -> None:
    """Sample three rim points; the resulting plane normal must be parallel
    to the supplied view direction (cross product gives the disk normal)."""
    target_pos = np.array([0.0, 0.0, 1.04])
    view_dir = np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)
    traces = silhouette_disk_traces(target_pos, view_dir, projected_area_m2=math.pi)
    assert len(traces) == 1
    trace = traces[0]
    pts = np.column_stack([np.asarray(trace.x), np.asarray(trace.y), np.asarray(trace.z)])
    rim_a, rim_b = pts[1] - pts[0], pts[2] - pts[0]
    disk_normal = np.cross(rim_a, rim_b)
    disk_normal /= np.linalg.norm(disk_normal)
    cos_angle = abs(float(np.dot(disk_normal, view_dir)))
    assert cos_angle == pytest.approx(1.0, abs=1e-12), (
        f"disk normal not aligned with view_dir: cos_angle={cos_angle}"
    )


def test_silhouette_hover_carries_units() -> None:
    """Trace name and hover both report A_t with explicit m^2 units."""
    traces = silhouette_disk_traces(
        np.array([0.0, 0.0, 1.04]),
        np.array([0.0, 0.0, -1.0]),
        projected_area_m2=12.5,
    )
    assert len(traces) == 1
    name = traces[0].name or ""
    hover = traces[0].hovertext or ""
    assert "m^2" in name and "12.5" in name
    assert "m^2" in hover and "12.5" in hover


def test_silhouette_display_size_scales_with_real_area() -> None:
    """Bigger A_t → bigger display radius (sphere(R=1m) anchors the scale)."""
    target = np.array([0.0, 0.0, 1.04])
    view = np.array([0.0, 0.0, -1.0])
    small = silhouette_disk_traces(target, view, projected_area_m2=math.pi)[0]
    big = silhouette_disk_traces(target, view, projected_area_m2=4.0 * math.pi)[0]
    small_radius = max(np.ptp(np.asarray(small.x)), np.ptp(np.asarray(small.y))) / 2.0
    big_radius = max(np.ptp(np.asarray(big.x)), np.ptp(np.asarray(big.y))) / 2.0
    assert big_radius > small_radius


# ---------------------------------------------------------------------------
# build_scene integration — silhouette per regime
# ---------------------------------------------------------------------------


def _names(traces: list) -> list[str]:
    return [getattr(t, "name", "") or "" for t in traces]


def test_silhouette_drawn_in_sub_pixel_when_inputs_supplied() -> None:
    state = SceneState.default()
    traces = build_scene(
        state,
        regime=RadiometricRegime.SUB_PIXEL,
        view_dir_scene=np.array([0.0, 0.0, -1.0]),
        projected_area_m2=math.pi,
    )
    assert any("Silhouette" in n for n in _names(traces))


def test_silhouette_drawn_in_default_regime_when_inputs_supplied() -> None:
    """Default (regime=None, Phase-2 contract) still draws silhouette
    when the live silhouette inputs are supplied — Phase 5 default path."""
    state = SceneState.default()
    traces = build_scene(
        state,
        view_dir_scene=np.array([0.0, 0.0, -1.0]),
        projected_area_m2=math.pi,
    )
    assert any("Silhouette" in n for n in _names(traces))


def test_silhouette_omitted_in_extended() -> None:
    state = SceneState.default()
    traces = build_scene(
        state,
        regime=RadiometricRegime.EXTENDED,
        gsd_m=12.34,
        view_dir_scene=np.array([0.0, 0.0, -1.0]),
        projected_area_m2=math.pi,
    )
    assert all("Silhouette" not in n for n in _names(traces))


def test_silhouette_omitted_in_point_source() -> None:
    state = SceneState.default()
    traces = build_scene(
        state,
        regime=RadiometricRegime.POINT_SOURCE,
        view_dir_scene=np.array([0.0, 0.0, -1.0]),
        projected_area_m2=math.pi,
    )
    assert all("Silhouette" not in n for n in _names(traces))


def test_silhouette_omitted_when_inputs_not_supplied() -> None:
    """Phase-2 callers (no silhouette inputs) get the original scene back."""
    traces = build_scene(SceneState.default())
    assert all("Silhouette" not in n for n in _names(traces))
