"""Phase 6 background-marker tests."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from dev_tools.geometry_gui.app.scene_builder.background_marker import (
    background_marker_traces,
)
from dev_tools.geometry_gui.app.state import BackgroundKind, SceneState

# Expected (color, descriptor-class-name) per kind. Mirrors the table in
# background_marker._BACKGROUND_DISPLAY but stays in the test so a code
# change to that table forces the test to be revisited.
EXPECTED: dict[BackgroundKind, tuple[str, str]] = {
    "cold_space": ("darkblue", "ColdSpaceBackground"),
    "ground": ("saddlebrown", "GroundBackground"),
    "at_aperture": ("dimgray", "AtApertureBackground"),
}

TARGET_POS = np.array([0.0, 0.0, 1.04])


def _state(kind: BackgroundKind) -> SceneState:
    return dataclasses.replace(SceneState.default(), background_kind=kind)


def test_none_produces_no_marker() -> None:
    assert background_marker_traces(_state("none"), TARGET_POS) == []


@pytest.mark.parametrize("kind, expected", list(EXPECTED.items()))
def test_color_per_background_kind(
    kind: BackgroundKind, expected: tuple[str, str]
) -> None:
    [trace] = background_marker_traces(_state(kind), TARGET_POS)
    color, descriptor = expected
    assert trace.line.color == color
    assert descriptor in (trace.name or "")


@pytest.mark.parametrize("kind", list(EXPECTED.keys()))
def test_marker_centered_on_target(kind: BackgroundKind) -> None:
    """Ring is centered on the target: every vertex is the same radial
    distance from `TARGET_POS` in the x/y plane, and z is constant."""
    [trace] = background_marker_traces(_state(kind), TARGET_POS)
    xs, ys, zs = np.asarray(trace.x), np.asarray(trace.y), np.asarray(trace.z)
    radii = np.hypot(xs - TARGET_POS[0], ys - TARGET_POS[1])
    assert np.allclose(radii, radii[0], atol=1e-12)
    assert np.allclose(zs, TARGET_POS[2], atol=1e-12)


@pytest.mark.parametrize("kind", list(EXPECTED.keys()))
def test_marker_label_names_kind_and_descriptor(kind: BackgroundKind) -> None:
    [trace] = background_marker_traces(_state(kind), TARGET_POS)
    name = trace.name or ""
    assert kind in name
    assert EXPECTED[kind][1] in name
