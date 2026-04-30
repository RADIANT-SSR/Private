"""Round-3 S4 regression — break-mark actors are added to the scene.

Round-3 §0 defect 4: break-marks (the small zigzags signaling
"this connecting line is not to scale") were missing from the
target → satellite and target → sun lines in the round-three reel,
despite shipping in round 1 (T7) and being re-targeted in round 2 (R5).

Root cause (per S4 diagnosis): the helper in ``scene/vectors/_tube.py``
*was* drawing break-mark actors named ``vec_boresight_break`` and
``vec_sun_ray_break``, but the line started at the world origin
``(0, 0, 0)`` rather than at the (lifted) target centroid. With the
schematic altitude lift, the target rose to z≈4–5 m at high target
altitude, leaving the break-mark midpoint (anchored at z≈3 m) below
the target and outside the visible portion of the line. From the
canonical isometric view the break-marks appeared "missing" —
they were rendering, just at the wrong z and partly obscured by the
arc-midpoint cluster.

The S4 fix anchors each line's start at ``target_centroid_scene``,
so the break-mark sits at the midpoint of the *visible* line at every
altitude. This test asserts the actors exist; visual verification of
the canonical view is the gating gate (see
``tests/golden/round3/s4_after/`` for the post-fix renders).
"""

from __future__ import annotations

import dataclasses
from typing import Final

import pytest
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene.builder import build_scene
from dev_tools.geometry_gui_v2.tests.audit_round2.render_canonical_views import (
    CANONICAL_VIEWS,
    _state_for,
)


_WINDOW_SIZE: Final[tuple[int, int]] = (1920, 1080)


def _altitude_sweep_states() -> list[tuple[str, SceneState]]:
    base = SceneState.default()
    return [
        (f"alt_{km:04d}km", dataclasses.replace(base, target_altitude_m=km * 1_000.0))
        for km in (0, 1, 10, 100, 600, 2000)
    ]


def _build_and_collect_actor_names(state: SceneState) -> set[str]:
    p = pv.Plotter(off_screen=True, window_size=_WINDOW_SIZE)
    try:
        build_scene(state, plotter=p)
        return set(p.actors.keys())
    finally:
        p.close()


@pytest.mark.parametrize("view_name", CANONICAL_VIEWS)
def test_break_marks_present_in_canonical_view(view_name: str) -> None:
    actors = _build_and_collect_actor_names(_state_for(view_name))
    assert "vec_boresight_break" in actors, (
        f"{view_name}: target → satellite line is missing its break-mark "
        f"(actor 'vec_boresight_break'); existing actors: {sorted(actors)!r}"
    )
    assert "vec_sun_ray_break" in actors, (
        f"{view_name}: target → sun line is missing its break-mark "
        f"(actor 'vec_sun_ray_break'); existing actors: {sorted(actors)!r}"
    )


@pytest.mark.parametrize("name,state", _altitude_sweep_states())
def test_break_marks_present_in_altitude_sweep(name: str, state: SceneState) -> None:
    actors = _build_and_collect_actor_names(state)
    assert "vec_boresight_break" in actors, (
        f"{name}: target → satellite line is missing its break-mark"
    )
    assert "vec_sun_ray_break" in actors, (
        f"{name}: target → sun line is missing its break-mark"
    )
