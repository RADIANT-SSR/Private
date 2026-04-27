"""Phase 2 scene-builder tests, updated for the Phase 8 target-centric redesign.

Required by the Phase-2 contract:
  1. test_build_scene_returns_traces — non-empty list of plotly traces per shape.
  2. test_no_nan_in_meshes           — no NaN/inf in any trace's x/y/z arrays.

Plus a JSON golden-comparison test per shape so a regression in the mesh
geometry would surface immediately. JSON is used in place of PNG so the
test runs without `kaleido` installed; a separate `dev_render_goldens.py`
helper produces PNGs when `kaleido` is available.

Phase 8 redesign anchors:
  * target sits at the scene origin (0, 0, 0)
  * observer sits at OBSERVER_DISPLAY_DISTANCE along −boresight
  * ground patch replaces the unit-Earth sphere
  * distances are illustrative, angles physical (PLAN.md C7)
"""

from __future__ import annotations

import dataclasses
import json
import math
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import pytest
from plotly.basedatatypes import BaseTraceType

from dev_tools.geometry_gui.app.scene_builder import build_scene
from dev_tools.geometry_gui.app.scene_builder.build_scene import (
    TARGET_DISPLAY_RADIUS,
    boresight_unit_display,
    observer_position_display,
    target_position_display,
)
from dev_tools.geometry_gui.app.scene_builder.ground_patch import (
    ground_patch_traces,
)
from dev_tools.geometry_gui.app.scene_builder.observer_glyph import (
    OBSERVER_DISPLAY_DISTANCE,
)
from dev_tools.geometry_gui.app.state import SceneState

GOLDEN_DIR = Path(__file__).parent / "golden"
SHAPES = ("sphere", "cylinder", "flat_plate", "box", "cone")


def _fixed_state(shape: str) -> SceneState:
    """Same SceneState used to generate the goldens — keep deterministic."""
    return dataclasses.replace(
        SceneState.default(),
        observer_yaw_rad=math.radians(5.0),
        observer_pitch_rad=math.radians(-2.0),
        observer_roll_rad=math.radians(1.0),
        target_yaw_rad=math.radians(20.0),
        target_pitch_rad=math.radians(-10.0),
        target_roll_rad=math.radians(7.0),
        target_shape=shape,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Required tests
# ---------------------------------------------------------------------------


def test_build_scene_returns_traces() -> None:
    """For every shape, build_scene returns a non-empty list of plotly traces."""
    for shape in SHAPES:
        traces = build_scene(_fixed_state(shape))
        assert isinstance(traces, list)
        assert len(traces) > 0, f"{shape}: no traces produced"
        for t in traces:
            assert isinstance(t, BaseTraceType), (
                f"{shape}: trace {t!r} is not a plotly BaseTraceType"
            )


def test_no_nan_in_meshes() -> None:
    """Every trace's x/y/z arrays contain only finite numbers."""
    for shape in SHAPES:
        for t in build_scene(_fixed_state(shape)):
            for axis in ("x", "y", "z"):
                vals = getattr(t, axis, None)
                if vals is None:
                    continue
                arr = np.asarray(vals, dtype=np.float64)
                assert np.isfinite(arr).all(), (
                    f"{shape} / {t.name} / {axis}: contains NaN or inf"
                )


def test_ground_patch_default_unshaded() -> None:
    """ground_patch_traces() with no sun direction draws a single solid mesh.

    Phase 8 contract: ground patch replaces the legacy Earth sphere. Without
    a sun-direction argument it must paint a single uniform color (so callers
    that haven't wired the sun yet still get a valid scene).
    """
    [patch] = ground_patch_traces()
    assert getattr(patch, "vertexcolor", None) is None
    assert isinstance(patch, go.Mesh3d)


# ---------------------------------------------------------------------------
# Golden-snapshot test (JSON, deterministic)
# ---------------------------------------------------------------------------


def _trace_signature(traces: list[go.Mesh3d | go.Scatter3d | go.Cone]) -> dict:
    """Reduce the trace list to a JSON-serializable shape signature.

    Stores per-trace name + x/y/z (rounded to 9 decimals to absorb
    last-bit float noise across numpy/BLAS revisions). Index/color/opacity
    are excluded — Phase 2 owns geometry, not styling.
    """
    sig = {"traces": []}
    for t in traces:
        entry: dict = {"name": getattr(t, "name", None), "type": type(t).__name__}
        for axis in ("x", "y", "z"):
            vals = getattr(t, axis, None)
            if vals is None:
                entry[axis] = None
            else:
                entry[axis] = np.round(
                    np.asarray(vals, dtype=np.float64), 9
                ).tolist()
        for face_attr in ("i", "j", "k"):
            vals = getattr(t, face_attr, None)
            if vals is not None:
                entry[face_attr] = [int(v) for v in np.asarray(vals)]
        sig["traces"].append(entry)
    return sig


@pytest.mark.parametrize("shape", SHAPES)
def test_golden_scene_signature(shape: str) -> None:
    """For each shape, the trace-signature JSON matches the committed golden."""
    sig = _trace_signature(build_scene(_fixed_state(shape)))
    golden_path = GOLDEN_DIR / f"scene_{shape}.json"
    if not golden_path.exists():
        pytest.fail(
            f"Golden missing: {golden_path}. Regenerate with "
            f"`python -m dev_tools.geometry_gui.tests.dev_render_goldens`."
        )
    with golden_path.open("r") as fh:
        golden = json.load(fh)
    assert sig == golden, f"Scene signature for {shape!r} differs from golden"


# ---------------------------------------------------------------------------
# Position-helper sanity checks (free; pin the Phase-8 display convention)
# ---------------------------------------------------------------------------


def test_target_position_at_origin() -> None:
    """Phase 8 redesign: target sits at scene origin regardless of altitude."""
    pos = target_position_display()
    np.testing.assert_allclose(pos, [0.0, 0.0, 0.0], atol=1e-15)


def test_observer_position_at_nadir() -> None:
    """At look_angle=0 the observer sits straight up at OBSERVER_DISPLAY_DISTANCE."""
    s = dataclasses.replace(SceneState.default(), observer_look_angle_rad=0.0)
    pos = observer_position_display(s)
    np.testing.assert_allclose(
        pos, [0.0, 0.0, OBSERVER_DISPLAY_DISTANCE], atol=1e-12
    )


def test_observer_position_off_nadir() -> None:
    """At look_angle θ the observer sits at (−sin θ, 0, cos θ) × OBSERVER_DISPLAY_DISTANCE."""
    theta = math.radians(20.0)
    s = dataclasses.replace(SceneState.default(), observer_look_angle_rad=theta)
    pos = observer_position_display(s)
    expected = OBSERVER_DISPLAY_DISTANCE * np.array(
        [-math.sin(theta), 0.0, math.cos(theta)]
    )
    np.testing.assert_allclose(pos, expected, atol=1e-12)


def test_boresight_is_unit_and_points_toward_origin() -> None:
    """Boresight = (sin θ, 0, −cos θ): unit norm, points down-and-forward."""
    theta = math.radians(35.0)
    s = dataclasses.replace(SceneState.default(), observer_look_angle_rad=theta)
    b = boresight_unit_display(s)
    assert float(np.linalg.norm(b)) == pytest.approx(1.0, abs=1e-15)
    assert b[2] < 0.0  # points downward (toward target / past it to ground)


def test_target_display_radius_constant() -> None:
    """Phase 8 redesign anchors TARGET_DISPLAY_RADIUS at 1.0 (the scene unit)."""
    assert TARGET_DISPLAY_RADIUS == 1.0
