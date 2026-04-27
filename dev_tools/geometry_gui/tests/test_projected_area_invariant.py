"""Phase 5 C3-invariant tests — `projected_area_m2(state)` matches the
radiometric `shape.projected_area(view_dir)` exactly, for every reachable
SceneState. This is the gate test: a failure means the GUI displays a
number radiometry would not use.

Also covers the three numerical truth anchors required for Category-C
validation (sphere, plate normal, plate at 60°), and the failure modes
listed in `prompts/phase_5_projected_area.md`.
"""

from __future__ import annotations

import dataclasses
import math
import random
from typing import Final

import pytest

from dev_tools.geometry_gui.app.state import SceneState
from dev_tools.geometry_gui.app.view_model import (
    build_target_shape,
    multi_facet_explainer,
    projected_area_m2,
    view_direction_body,
)

SHAPES: Final[tuple[str, ...]] = ("sphere", "cylinder", "flat_plate", "box", "cone")


# ---------------------------------------------------------------------------
# C3 invariant — 50 random reachable states
# ---------------------------------------------------------------------------


def _random_state(seed: int) -> SceneState:
    """Seeded random SceneState that exercises every slider on the GUI."""
    rng = random.Random(seed)
    base = SceneState.default()
    return dataclasses.replace(
        base,
        observer_altitude_m=rng.uniform(200_000.0, 800_000.0),
        observer_look_angle_rad=math.radians(rng.uniform(0.0, 45.0)),
        observer_yaw_rad=math.radians(rng.uniform(-180.0, 180.0)),
        observer_pitch_rad=math.radians(rng.uniform(-30.0, 30.0)),
        observer_roll_rad=math.radians(rng.uniform(-30.0, 30.0)),
        target_shape=rng.choice(SHAPES),  # type: ignore[arg-type]
        target_radius_m=rng.uniform(0.5, 5.0),
        target_length_m=rng.uniform(0.5, 8.0),
        target_width_m=rng.uniform(0.5, 5.0),
        target_height_m=rng.uniform(0.5, 5.0),
        target_base_radius_m=rng.uniform(0.5, 4.0),
        target_yaw_rad=math.radians(rng.uniform(-180.0, 180.0)),
        target_pitch_rad=math.radians(rng.uniform(-90.0, 90.0)),
        target_roll_rad=math.radians(rng.uniform(-180.0, 180.0)),
    )


@pytest.mark.parametrize("seed", range(50))
def test_projected_area_matches_shape_call(seed: int) -> None:
    """C3 invariant: GUI's A_t == shape.projected_area(v_body), bit-exact."""
    state = _random_state(seed)
    shape = build_target_shape(state)
    v_body = view_direction_body(state)
    expected = shape.projected_area(v_body)
    actual = projected_area_m2(state)
    assert actual == expected, (
        f"seed={seed} shape={state.target_shape}: "
        f"GUI A_t={actual} != shape.projected_area={expected}"
    )


# ---------------------------------------------------------------------------
# Numerical truth anchors (Category C — three required)
# ---------------------------------------------------------------------------


def test_truth_anchor_sphere_unit_radius() -> None:
    """Sphere R=1 m → A_t = π m² for any view direction (orientation-invariant)."""
    state = dataclasses.replace(
        SceneState.default(), target_shape="sphere", target_radius_m=1.0
    )
    expected = math.pi
    actual = projected_area_m2(state)
    abs_err = abs(actual - expected)
    rel_err = abs_err / expected
    assert actual == pytest.approx(expected, rel=1e-12), (
        f"sphere R=1: expected π, got {actual}, abs_err={abs_err}, rel_err={rel_err}"
    )


def test_truth_anchor_flat_plate_normal_view() -> None:
    """2×3 flat plate viewed exactly normal → A_t = 6 m²."""
    state = dataclasses.replace(
        SceneState.default(),
        target_shape="flat_plate",
        target_length_m=2.0,
        target_width_m=3.0,
        # default observer_yaw=0, target_yaw=0 → boresight aligned with plate normal.
        observer_yaw_rad=0.0,
        observer_pitch_rad=0.0,
        observer_roll_rad=0.0,
        observer_look_angle_rad=0.0,
        target_yaw_rad=0.0,
        target_pitch_rad=0.0,
        target_roll_rad=0.0,
    )
    expected = 6.0
    actual = projected_area_m2(state)
    abs_err = abs(actual - expected)
    rel_err = abs_err / expected
    assert actual == pytest.approx(expected, rel=1e-12), (
        f"plate normal: expected 6.0, got {actual}, abs_err={abs_err}, rel_err={rel_err}"
    )


def test_truth_anchor_flat_plate_60_deg() -> None:
    """2×3 flat plate viewed at 60° from normal → A_t = 6·cos(60°) = 3 m²."""
    state = dataclasses.replace(
        SceneState.default(),
        target_shape="flat_plate",
        target_length_m=2.0,
        target_width_m=3.0,
        observer_yaw_rad=0.0,
        observer_pitch_rad=0.0,
        observer_roll_rad=0.0,
        observer_look_angle_rad=0.0,
        # Tilt the plate by 60° about its X-axis. The boresight is +Z (body),
        # so the plate normal makes a 60° angle with the boresight → cos(60°)=0.5.
        target_yaw_rad=0.0,
        target_pitch_rad=math.radians(60.0),
        target_roll_rad=0.0,
    )
    expected = 6.0 * math.cos(math.radians(60.0))  # = 3.0
    actual = projected_area_m2(state)
    abs_err = abs(actual - expected)
    rel_err = abs_err / expected
    assert actual == pytest.approx(expected, rel=1e-12), (
        f"plate 60°: expected 3.0, got {actual}, abs_err={abs_err}, rel_err={rel_err}"
    )


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


def test_zero_radius_sphere_raises_explicit_error() -> None:
    """Shape constructors enforce strictly positive sizes. Confirm this
    surfaces as an actionable ValueError (Rule 17 — no silent NaN)."""
    state = dataclasses.replace(
        SceneState.default(), target_shape="sphere", target_radius_m=0.0
    )
    with pytest.raises(ValueError, match="radius_m must be positive"):
        projected_area_m2(state)


def test_zero_size_flat_plate_raises_explicit_error() -> None:
    state = dataclasses.replace(
        SceneState.default(),
        target_shape="flat_plate",
        target_length_m=0.0,
        target_width_m=3.0,
    )
    with pytest.raises(ValueError, match="must be positive"):
        projected_area_m2(state)


def test_edge_on_flat_plate_returns_zero() -> None:
    """View parallel to plate (90° from normal) → projected area is 0."""
    state = dataclasses.replace(
        SceneState.default(),
        target_shape="flat_plate",
        target_length_m=2.0,
        target_width_m=3.0,
        observer_yaw_rad=0.0,
        observer_pitch_rad=0.0,
        observer_roll_rad=0.0,
        observer_look_angle_rad=0.0,
        target_pitch_rad=math.radians(90.0),
    )
    actual = projected_area_m2(state)
    assert actual == pytest.approx(0.0, abs=1e-12), (
        f"edge-on plate: expected ~0, got {actual}"
    )


def test_reversed_view_flat_plate_uses_abs_cos() -> None:
    """FlatPlate uses |cos θ|, so reversing the view (180° flip) gives the
    same area as front-on. Document and confirm this behavior."""
    front = dataclasses.replace(
        SceneState.default(),
        target_shape="flat_plate",
        target_length_m=2.0,
        target_width_m=3.0,
        observer_look_angle_rad=0.0,
        target_pitch_rad=0.0,
    )
    reversed_ = dataclasses.replace(front, target_pitch_rad=math.radians(180.0))
    assert projected_area_m2(front) == pytest.approx(
        projected_area_m2(reversed_), rel=1e-12
    )


def test_cone_tip_on_view_matches_shape_call() -> None:
    """Cone viewed tip-on (view aligned with cone axis) — non-trivial value;
    just confirm GUI matches `Cone.projected_area(v)`."""
    state = dataclasses.replace(
        SceneState.default(),
        target_shape="cone",
        target_base_radius_m=1.5,
        target_height_m=4.0,
        observer_yaw_rad=0.0,
        observer_pitch_rad=0.0,
        observer_roll_rad=0.0,
        observer_look_angle_rad=0.0,
        target_yaw_rad=0.0,
        target_pitch_rad=0.0,
        target_roll_rad=0.0,
    )
    shape = build_target_shape(state)
    v_body = view_direction_body(state)
    assert projected_area_m2(state) == shape.projected_area(v_body)


# ---------------------------------------------------------------------------
# Multi-facet explainer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("shape", SHAPES)
def test_multi_facet_explainer_published_for_every_shape(shape: str) -> None:
    text = multi_facet_explainer(shape)
    assert text and "not documented" not in text
