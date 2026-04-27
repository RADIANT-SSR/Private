"""Phase 6 sun-arrow tests."""

from __future__ import annotations

import dataclasses
import math
import random

import numpy as np
import pytest

from dev_tools.geometry_gui.app.scene_builder.sun_arrow import (
    SUN_ARROW_DISPLAY_LENGTH,
    sun_arrow_traces,
    sun_unit_vector_local,
    sun_unit_vector_scene,
)
from dev_tools.geometry_gui.app.state import SceneState


def _state(**overrides: object) -> SceneState:
    return dataclasses.replace(SceneState.default(), **overrides)


# ---------------------------------------------------------------------------
# Direction math
# ---------------------------------------------------------------------------


def test_sun_overhead_points_along_zenith() -> None:
    """theta_s = 0 → arrow along +Z (local zenith == global +Z at the +Z pole)."""
    n = sun_unit_vector_local(_state(solar_zenith_rad=0.0, relative_azimuth_rad=0.0))
    assert n == pytest.approx(np.array([0.0, 0.0, 1.0]), abs=1e-12)


def test_sun_on_horizon_along_x() -> None:
    """theta_s = π/2, Δφ = 0 → +X (cross-track, in the local horizontal plane)."""
    n = sun_unit_vector_local(
        _state(solar_zenith_rad=math.pi / 2.0, relative_azimuth_rad=0.0)
    )
    assert n == pytest.approx(np.array([1.0, 0.0, 0.0]), abs=1e-12)


def test_sun_on_horizon_along_y() -> None:
    """theta_s = π/2, Δφ = π/2 → +Y (along-track in local horizontal)."""
    n = sun_unit_vector_local(
        _state(solar_zenith_rad=math.pi / 2.0, relative_azimuth_rad=math.pi / 2.0)
    )
    assert n == pytest.approx(np.array([0.0, 1.0, 0.0]), abs=1e-12)


@pytest.mark.parametrize("seed", range(50))
def test_sun_unit_vector_norm(seed: int) -> None:
    """Across 50 random (θ_s, Δφ), the sun vector has unit norm."""
    rng = random.Random(seed)
    state = _state(
        solar_zenith_rad=rng.uniform(0.0, math.pi),
        relative_azimuth_rad=rng.uniform(-math.pi, math.pi),
    )
    n = sun_unit_vector_scene(state)
    assert float(np.linalg.norm(n)) == pytest.approx(1.0, rel=1e-12)


# ---------------------------------------------------------------------------
# Trace shape
# ---------------------------------------------------------------------------


def test_sun_arrow_returns_shaft_and_tip() -> None:
    state = _state()
    target_pos = np.array([0.0, 0.0, 1.04])
    traces = sun_arrow_traces(state, target_pos)
    assert len(traces) == 2
    shaft, tip = traces
    assert shaft.mode == "lines"
    assert tip.type == "cone"


def test_sun_arrow_shaft_length_matches_constant() -> None:
    """Shaft length in display units equals SUN_ARROW_DISPLAY_LENGTH."""
    state = _state(solar_zenith_rad=math.pi / 4.0, relative_azimuth_rad=0.3)
    target_pos = np.array([0.0, 0.0, 1.04])
    shaft, _tip = sun_arrow_traces(state, target_pos)
    p0 = np.array([shaft.x[0], shaft.y[0], shaft.z[0]])
    p1 = np.array([shaft.x[1], shaft.y[1], shaft.z[1]])
    assert float(np.linalg.norm(p1 - p0)) == pytest.approx(
        SUN_ARROW_DISPLAY_LENGTH, rel=1e-12
    )


def test_sun_arrow_label_contains_angles_in_degrees() -> None:
    """Hover/legend label must surface theta_s and delta_phi in degrees (units rule)."""
    state = _state(
        solar_zenith_rad=math.radians(35.0),
        relative_azimuth_rad=math.radians(12.0),
    )
    target_pos = np.array([0.0, 0.0, 1.04])
    shaft, _tip = sun_arrow_traces(state, target_pos)
    name = shaft.name or ""
    assert "35.0" in name and "12.0" in name and "deg" in name


# ---------------------------------------------------------------------------
# Ground-patch shading consumes the sun direction
# (Phase 8 redesign: earth_mesh replaced by ground_patch — PLAN.md §11)
# ---------------------------------------------------------------------------


def test_ground_patch_uses_sun_direction_when_supplied() -> None:
    """ground_patch_traces with sun_dir_scene returns a Mesh3d with vertexcolor set."""
    from dev_tools.geometry_gui.app.scene_builder.ground_patch import (
        ground_patch_traces,
    )

    sun_dir = np.array([0.0, 0.0, 1.0])
    [trace] = ground_patch_traces(sun_dir_scene=sun_dir)
    assert getattr(trace, "vertexcolor", None) is not None


def test_ground_patch_no_shading_when_sun_dir_none() -> None:
    """ground_patch_traces() with no sun direction paints a single uniform color."""
    from dev_tools.geometry_gui.app.scene_builder.ground_patch import (
        ground_patch_traces,
    )

    [trace] = ground_patch_traces()
    assert getattr(trace, "vertexcolor", None) is None
