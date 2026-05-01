"""Phase 1 view-model tests.

Covers the four required tests from prompts/phase_1_view_model.md:

  1. test_scene_geometry_matches_core_class — slant range / GSD parity.
  2. test_projected_area_parity            — C3 invariant for all 5 shapes.
  3. test_regime_truth_table               — five Rule-10 branches + override.
  4. test_view_direction_unit_norm         — ‖v‖ = 1 in scene & body frames.

Plus the failure-mode coverage required by the Category-B report.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterable

import numpy as np
import pytest

from radiant.core.geometry import (
    ObserverGeometry,
    SceneGeometry,
    TargetGeometry,
    euler_to_rotation_matrix,
)
from radiant.core.regime import RadiometricRegime
from radiant.source.shapes.box import Box
from radiant.source.shapes.cone import Cone
from radiant.source.shapes.cylinder import Cylinder
from radiant.source.shapes.flat_plate import FlatPlate
from radiant.source.shapes.sphere import Sphere

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.app.view_model import (
    build_scene_geometry,
    build_target_shape,
    classify_regime,
    compute_view_direction_scene,
    derived_readout,
    projected_area_m2,
    view_direction_body,
)


# ---------------------------------------------------------------------------
# 1. SceneGeometry parity
# ---------------------------------------------------------------------------


def test_scene_geometry_matches_core_class() -> None:
    """Slant range and GSD from the view-model must equal SceneGeometry's own values."""
    state = SceneState.default()

    geom_vm = build_scene_geometry(state)

    expected_geom = SceneGeometry(
        observer=ObserverGeometry(
            altitude_m=state.observer_altitude_m,
            look_angle_rad=state.observer_look_angle_rad,
            yaw_rad=state.observer_yaw_rad,
            pitch_rad=state.observer_pitch_rad,
            roll_rad=state.observer_roll_rad,
        ),
        target=TargetGeometry(altitude_m=state.target_altitude_m),
    )

    assert geom_vm.slant_range_m == expected_geom.slant_range_m
    assert geom_vm.ground_range_m == expected_geom.ground_range_m
    assert geom_vm.gsd_m(
        state.focal_length_m, state.pixel_pitch_m
    ) == expected_geom.gsd_m(state.focal_length_m, state.pixel_pitch_m)
    assert geom_vm.ifov_rad(
        state.focal_length_m, state.pixel_pitch_m
    ) == expected_geom.ifov_rad(state.focal_length_m, state.pixel_pitch_m)


# ---------------------------------------------------------------------------
# 2. Projected-area parity (C3 invariant)
# ---------------------------------------------------------------------------


def _states_for_each_shape() -> Iterable[SceneState]:
    """One non-trivial SceneState per shape kind, with a non-zero target attitude."""
    base = dataclasses.replace(
        SceneState.default(),
        observer_yaw_rad=math.radians(7.0),
        observer_pitch_rad=math.radians(-3.0),
        observer_roll_rad=math.radians(2.0),
        target_yaw_rad=math.radians(15.0),
        target_pitch_rad=math.radians(-22.0),
        target_roll_rad=math.radians(9.0),
    )
    yield dataclasses.replace(base, target_shape="sphere", target_radius_m=1.5)
    yield dataclasses.replace(
        base, target_shape="cylinder", target_radius_m=0.7, target_length_m=3.4
    )
    yield dataclasses.replace(
        base, target_shape="flat_plate", target_length_m=2.1, target_width_m=1.3
    )
    yield dataclasses.replace(
        base,
        target_shape="box",
        target_length_m=2.0,
        target_width_m=1.0,
        target_height_m=0.5,
    )
    yield dataclasses.replace(
        base, target_shape="cone", target_base_radius_m=0.9, target_height_m=2.5
    )


def test_projected_area_parity() -> None:
    """View-model A_t equals shape.projected_area(v_body) to machine precision (C3)."""
    for state in _states_for_each_shape():
        v_body = view_direction_body(state)

        # Build a sibling shape directly (orientation_rad = (0,0,0) per
        # build_target_shape's design), then call projected_area on it.
        kind = state.target_shape
        if kind == "sphere":
            direct = Sphere(radius_m=state.target_radius_m)
        elif kind == "cylinder":
            direct = Cylinder(
                radius_m=state.target_radius_m, length_m=state.target_length_m
            )
        elif kind == "flat_plate":
            direct = FlatPlate(
                length_m=state.target_length_m, width_m=state.target_width_m
            )
        elif kind == "box":
            direct = Box(
                length_m=state.target_length_m,
                width_m=state.target_width_m,
                height_m=state.target_height_m,
            )
        elif kind == "cone":
            direct = Cone(
                base_radius_m=state.target_base_radius_m,
                height_m=state.target_height_m,
            )
        else:  # pragma: no cover — caught by build_target_shape
            pytest.fail(f"unexpected shape kind {kind!r}")

        expected = direct.projected_area(v_body)
        actual = projected_area_m2(state)

        # Machine precision per the Phase-1 acceptance test spec.
        assert actual == pytest.approx(expected, rel=1e-15, abs=0.0), (
            f"{kind}: view-model {actual!r} vs direct {expected!r}"
        )


# ---------------------------------------------------------------------------
# 3. Rule-10 truth table
# ---------------------------------------------------------------------------


def _state_with_angular_extent(
    target_diameter_m: float,
    fill_fraction: float = 1.0,
    regime_override: str = "auto",
    pixel_pitch_m: float = 10e-6,
    focal_length_m: float = 1.0,
) -> SceneState:
    """Construct a state where projected_area = (target_diameter_m / 2)^2 · π
    via a sphere, so ang_ext = sqrt(A) / slant_range is controllable.
    """
    return dataclasses.replace(
        SceneState.default(),
        target_shape="sphere",
        target_radius_m=target_diameter_m / 2.0,
        target_fill_fraction=fill_fraction,
        regime_override=regime_override,  # type: ignore[arg-type]
        pixel_pitch_m=pixel_pitch_m,
        focal_length_m=focal_length_m,
    )


def test_regime_truth_table() -> None:
    """Cover all five Rule-10 branches plus the explicit override path."""
    # Branch 1 — explicit override beats everything.
    s_ovr = _state_with_angular_extent(
        target_diameter_m=0.001, regime_override="extended"
    )
    regime, reason = classify_regime(s_ovr)
    assert regime is RadiometricRegime.EXTENDED
    assert "override" in reason.lower()

    # Branch 2 — fill_fraction < 1.0 forces SUB_PIXEL even if huge.
    s_fill = _state_with_angular_extent(
        target_diameter_m=10_000.0, fill_fraction=0.4
    )
    regime, reason = classify_regime(s_fill)
    assert regime is RadiometricRegime.SUB_PIXEL
    assert "fill_fraction" in reason

    # Compute slant range so we can size targets to land in the wanted bin.
    geom = build_scene_geometry(SceneState.default())
    slant = geom.slant_range_m
    ifov = SceneState.default().pixel_pitch_m / SceneState.default().focal_length_m

    # Branch 3 — ang_ext ≥ 2·ifov ⇒ EXTENDED.
    # Make sqrt(A) = 4 · ifov · slant ⇒ A = (4·ifov·slant)^2.
    sqrtA_ext = 4.0 * ifov * slant
    diam_ext = 2.0 * sqrtA_ext / math.sqrt(math.pi)  # so π·r² = A
    s_ext = _state_with_angular_extent(target_diameter_m=diam_ext)
    regime, reason = classify_regime(s_ext)
    assert regime is RadiometricRegime.EXTENDED
    assert "2*ifov" in reason

    # Branch 4 — ang_ext ≤ 0.25·ifov ⇒ POINT_SOURCE.
    sqrtA_pt = 0.10 * ifov * slant
    diam_pt = 2.0 * sqrtA_pt / math.sqrt(math.pi)
    s_pt = _state_with_angular_extent(target_diameter_m=diam_pt)
    regime, reason = classify_regime(s_pt)
    assert regime is RadiometricRegime.POINT_SOURCE
    assert "0.25*ifov" in reason

    # Branch 5 — 0.25·ifov < ang_ext < 2·ifov ⇒ SUB_PIXEL.
    sqrtA_sp = 1.0 * ifov * slant  # right in the middle
    diam_sp = 2.0 * sqrtA_sp / math.sqrt(math.pi)
    s_sp = _state_with_angular_extent(target_diameter_m=diam_sp)
    regime, reason = classify_regime(s_sp)
    assert regime is RadiometricRegime.SUB_PIXEL
    assert "0.25*ifov < ang_ext < 2*ifov" in reason


# ---------------------------------------------------------------------------
# 4. View direction unit-norm property
# ---------------------------------------------------------------------------


def test_view_direction_unit_norm() -> None:
    """‖v‖ = 1 ± 1e-12 in both scene and body frames across 50 random states."""
    rng = np.random.default_rng(seed=20260426)
    base = SceneState.default()

    for _ in range(50):
        # Sample full-range attitudes for both observer and target.
        # Observer look angle stays in [0, π/2) — ObserverGeometry validates.
        state = dataclasses.replace(
            base,
            observer_look_angle_rad=float(rng.uniform(0.0, 0.4 * math.pi)),
            observer_yaw_rad=float(rng.uniform(-math.pi, math.pi)),
            observer_pitch_rad=float(rng.uniform(-math.pi, math.pi)),
            observer_roll_rad=float(rng.uniform(-math.pi, math.pi)),
            target_yaw_rad=float(rng.uniform(-math.pi, math.pi)),
            target_pitch_rad=float(rng.uniform(-math.pi, math.pi)),
            target_roll_rad=float(rng.uniform(-math.pi, math.pi)),
        )

        v_scene = compute_view_direction_scene(state)
        v_body = view_direction_body(state)

        assert abs(float(np.linalg.norm(v_scene)) - 1.0) < 1e-12
        assert abs(float(np.linalg.norm(v_body)) - 1.0) < 1e-12


# ---------------------------------------------------------------------------
# Failure-mode coverage (Category-B report requirement)
# ---------------------------------------------------------------------------


def test_zero_size_shape_rejected() -> None:
    """RADIANT shape constructors raise on non-positive sizes — view-model surfaces that."""
    bad = dataclasses.replace(
        SceneState.default(), target_shape="sphere", target_radius_m=0.0
    )
    with pytest.raises(ValueError, match="positive"):
        build_target_shape(bad)


def test_flat_plate_view_along_normal_full_area() -> None:
    """View parallel to plate normal ⇒ A_proj = L · W (full face)."""
    state = dataclasses.replace(
        SceneState.default(),
        target_shape="flat_plate",
        target_length_m=2.0,
        target_width_m=3.0,
        observer_yaw_rad=0.0,
        observer_pitch_rad=0.0,
        observer_roll_rad=0.0,
        target_yaw_rad=0.0,
        target_pitch_rad=0.0,
        target_roll_rad=0.0,
    )
    # At zero attitudes both v_scene and v_body are −Z, parallel to plate normal.
    A = projected_area_m2(state)
    assert A == pytest.approx(2.0 * 3.0, rel=1e-15)


def test_flat_plate_view_perpendicular_to_normal_zero() -> None:
    """View perpendicular to plate normal ⇒ A_proj = 0 (edge-on)."""
    # Pitch the target by 90° around its body Y so the body +Z (plate normal)
    # rotates into the body X — perpendicular to the unrotated scene-frame
    # view direction (still −Z in scene). v_body then has v[2] ≈ 0.
    state = dataclasses.replace(
        SceneState.default(),
        target_shape="flat_plate",
        target_length_m=2.0,
        target_width_m=3.0,
        target_pitch_rad=math.pi / 2.0,
    )
    A = projected_area_m2(state)
    assert A == pytest.approx(0.0, abs=1e-12)


def test_fill_fraction_zero_forces_sub_pixel() -> None:
    """fill_fraction = 0 (< 1) forces SUB_PIXEL by Rule-10 branch 2."""
    s = dataclasses.replace(SceneState.default(), target_fill_fraction=0.0)
    regime, reason = classify_regime(s)
    assert regime is RadiometricRegime.SUB_PIXEL
    assert "fill_fraction" in reason


def test_fill_fraction_above_one_still_ranges_via_geometry() -> None:
    """fill_fraction > 1 is not < 1, so Rule-10 branch 2 is skipped and the
    classifier falls through to the geometric branches.

    This documents *current* behavior — the view-model does not validate
    fill_fraction's upper bound (per Phase-1 scope; CLAUDE.md Rule 16
    assigns input validation to ParameterSet, which the GUI bypasses for
    sliders). Phase 3 will clamp the slider's max to 1.0 instead.
    """
    s = _state_with_angular_extent(
        target_diameter_m=1e-6, fill_fraction=1.5
    )  # tiny target → POINT_SOURCE
    regime, _ = classify_regime(s)
    assert regime is RadiometricRegime.POINT_SOURCE


# ---------------------------------------------------------------------------
# View-direction sign / observer-rotation sanity check
# ---------------------------------------------------------------------------


def test_view_direction_scene_at_zero_attitude() -> None:
    """At zero observer attitude the scene-frame view direction is exactly −Z."""
    state = dataclasses.replace(
        SceneState.default(),
        observer_yaw_rad=0.0,
        observer_pitch_rad=0.0,
        observer_roll_rad=0.0,
    )
    v = compute_view_direction_scene(state)
    np.testing.assert_allclose(v, np.array([0.0, 0.0, -1.0]), atol=1e-15)


def test_view_direction_body_consistency_with_helpers_math() -> None:
    """The local 4-line transpose matches `R.T @ v` from `radiant.core.geometry`.

    This pins the view-model to the same rotation algebra used inside
    `radiant.source.shapes._helpers.view_to_body` — without importing it.
    """
    state = dataclasses.replace(
        SceneState.default(),
        target_yaw_rad=math.radians(40.0),
        target_pitch_rad=math.radians(-15.0),
        target_roll_rad=math.radians(8.0),
    )
    v_scene = compute_view_direction_scene(state)
    R_target = euler_to_rotation_matrix(
        state.target_yaw_rad, state.target_pitch_rad, state.target_roll_rad
    )
    expected = R_target.T @ v_scene
    np.testing.assert_allclose(view_direction_body(state), expected, rtol=0.0, atol=0.0)


# ---------------------------------------------------------------------------
# Readout panel — units on every entry (CLAUDE.md hard rule)
# ---------------------------------------------------------------------------


def test_derived_readout_has_units_on_every_value() -> None:
    """Every readout entry is a (float, unit_string) pair with non-empty units."""
    out = derived_readout(SceneState.default())
    expected_keys = {
        "slant_range",
        "ground_range",
        "gsd",
        "ifov",
        "angular_extent",
        "pixel_area",
        "projected_area",
        "fill_fraction_effective",
        "apparent_size_pixels",
        "view_azimuth",
        "view_elevation",
        "solar_zenith",
        "relative_azimuth",
    }
    assert set(out.keys()) == expected_keys
    for key, (value, unit) in out.items():
        assert isinstance(value, float), f"{key}: value not a float"
        assert isinstance(unit, str) and unit, f"{key}: unit string missing"
