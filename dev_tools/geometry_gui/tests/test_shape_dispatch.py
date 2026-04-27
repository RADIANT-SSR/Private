"""Phase 4 shape-dispatch tests.

Every choice in the shape dropdown must:
  1. Construct a valid `TargetShape` via `view_model.build_target_shape`.
  2. Produce a non-empty mesh from `scene_builder.build_scene` (default regime).

Also covers Phase-4 regime-driven dispatch in `build_scene`:
  * EXTENDED   → pixel-cell trace replaces the shape mesh
  * POINT_SOURCE → single-marker trace replaces the shape mesh
"""

from __future__ import annotations

import dataclasses

import pytest

from radiant.core.regime import RadiometricRegime
from radiant.source.shape import TargetShape

from dev_tools.geometry_gui.app.layout.target_controls import SHAPE_OPTIONS
from dev_tools.geometry_gui.app.scene_builder.build_scene import build_scene
from dev_tools.geometry_gui.app.state import SceneState
from dev_tools.geometry_gui.app.view_model import build_target_shape

ALL_DROPDOWN_VALUES = tuple(opt["value"] for opt in SHAPE_OPTIONS)


@pytest.mark.parametrize("shape", ALL_DROPDOWN_VALUES)
def test_dropdown_shape_yields_target_shape(shape: str) -> None:
    state = dataclasses.replace(SceneState.default(), target_shape=shape)  # type: ignore[arg-type]
    target = build_target_shape(state)
    assert isinstance(target, TargetShape), (
        f"shape={shape!r} did not produce a TargetShape (got {type(target).__name__})"
    )


@pytest.mark.parametrize("shape", ALL_DROPDOWN_VALUES)
def test_dropdown_shape_yields_non_empty_mesh(shape: str) -> None:
    state = dataclasses.replace(SceneState.default(), target_shape=shape)  # type: ignore[arg-type]
    traces = build_scene(state)  # default regime → renders shape mesh
    assert len(traces) > 0, f"shape={shape!r} produced no traces"

    def _has_vertices(trace: object) -> bool:
        xs = getattr(trace, "x", None)
        return xs is not None and len(xs) > 0

    assert any(_has_vertices(t) for t in traces), (
        f"shape={shape!r}: no trace has vertex data"
    )


def test_extended_regime_replaces_shape_with_pixel_cell() -> None:
    """In EXTENDED, build_scene emits a 'Pixel cell' trace instead of the shape mesh."""
    state = SceneState.default()
    traces = build_scene(state, regime=RadiometricRegime.EXTENDED, gsd_m=12.34)
    names = [getattr(t, "name", "") for t in traces]
    assert any("Pixel cell" in (n or "") for n in names), (
        f"expected a 'Pixel cell' trace, got names={names}"
    )
    assert all("Sphere" not in (n or "") for n in names), (
        "shape mesh should be omitted in EXTENDED regime"
    )


def test_point_source_regime_replaces_shape_with_dot() -> None:
    """In POINT_SOURCE, build_scene emits a single 'Point source' marker."""
    state = SceneState.default()
    traces = build_scene(state, regime=RadiometricRegime.POINT_SOURCE)
    names = [getattr(t, "name", "") for t in traces]
    assert any("Point source" in (n or "") for n in names), (
        f"expected a 'Point source' trace, got names={names}"
    )


def test_extended_without_gsd_raises() -> None:
    """build_scene refuses EXTENDED without a real-world GSD argument."""
    with pytest.raises(ValueError, match="gsd_m"):
        build_scene(SceneState.default(), regime=RadiometricRegime.EXTENDED)


def test_default_regime_preserves_phase2_contract() -> None:
    """Calling build_scene without a regime renders the shape mesh + body axes.

    Phase-2 goldens are pinned to this no-regime contract.
    """
    traces = build_scene(SceneState.default())
    names = [getattr(t, "name", "") for t in traces]
    assert any("body +X" in (n or "") for n in names), (
        "default regime should still draw body axes"
    )
