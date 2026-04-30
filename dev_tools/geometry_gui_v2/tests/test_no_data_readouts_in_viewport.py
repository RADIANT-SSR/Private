"""Regression test for round-3 S1 — no data readouts in the 3D viewport.

Round-3 §0 defect 3: ``Sensor alt = 600 km slant = 639 km`` and
``Target alt = 0 km A_t = 3.14 m^2 (sub_pixel)`` text was being emitted
as in-viewport label content. Those values belong in the right-dock
ReadoutsPanel and the left-dock ParametersPanel; the viewport never
duplicates panel content.

The test scans every ``LabelAnchor.text`` produced by ``collect_anchors``
on each canonical view (plus the round-3 altitude sweep so high-altitude
slant readouts are also covered) for a forbidden-pattern set.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Final

import pytest

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene.labels._anchors import collect_anchors
from dev_tools.geometry_gui_v2.tests.audit_round2.render_canonical_views import (
    CANONICAL_VIEWS,
    _state_for,
)


_FORBIDDEN_PATTERNS: Final[tuple[str, ...]] = (
    r"alt\s*=\s*\d",
    r"slant\s*=\s*\d",
    r"A_t\s*=",
    r"\(sub_pixel\)",
    r"\(extended\)",
    r"\(point_source\)",
)


def _altitude_sweep_states() -> list[tuple[str, SceneState]]:
    base = SceneState.default()
    return [
        (f"altitude_{km:04d}km", dataclasses.replace(base, target_altitude_m=km * 1_000.0))
        for km in (0, 1, 10, 100, 600, 2000)
    ]


@pytest.mark.parametrize("view_name", CANONICAL_VIEWS)
def test_canonical_view_has_no_data_readouts(view_name: str) -> None:
    state = _state_for(view_name)
    for anchor in collect_anchors(state):
        for pattern in _FORBIDDEN_PATTERNS:
            assert not re.search(pattern, anchor.text), (
                f"{view_name}: viewport label '{anchor.text}' "
                f"(anchor '{anchor.name}') contains forbidden pattern '{pattern}'"
            )


@pytest.mark.parametrize("name,state", _altitude_sweep_states())
def test_altitude_sweep_has_no_data_readouts(name: str, state: SceneState) -> None:
    for anchor in collect_anchors(state):
        for pattern in _FORBIDDEN_PATTERNS:
            assert not re.search(pattern, anchor.text), (
                f"{name}: viewport label '{anchor.text}' "
                f"(anchor '{anchor.name}') contains forbidden pattern '{pattern}'"
            )


def test_minimal_object_names_present() -> None:
    """Sanity: the default scene exposes the four minimal object nouns."""
    state = SceneState.default()
    texts = {a.text for a in collect_anchors(state)}
    assert "Target" in texts
    assert "Satellite" in texts
    assert "Sun" in texts
