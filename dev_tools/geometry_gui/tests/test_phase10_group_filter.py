"""Phase 10 angle-group filter tests for `build_scene`.

Per PLAN.md §11 phase-10 acceptance:
  * Each toggle independently adds/removes exactly its declared traces.
  * Empty selection yields zero arc/ray/triad/projection traces (only
    base scene + target representation remain).
  * Default groups (when ``angle_groups=None``) match
    ``DEFAULT_ANGLE_GROUPS``.

Rule 19: every module has its own tests; this file pins the dispatch
behavior of `build_scene` against the angle-groups frozenset.
"""

from __future__ import annotations

from dev_tools.geometry_gui.app.scene_builder import build_scene
from dev_tools.geometry_gui.app.scene_builder.build_scene import (
    DEFAULT_ANGLE_GROUPS,
    build_scene as build_scene_fn,
)
from dev_tools.geometry_gui.app.state import SceneState

# Substrings that uniquely identify each group's signature traces by trace name.
GROUP_SIGNATURES: dict[str, tuple[str, ...]] = {
    "observer": ("nadir reference", "off-nadir =", "az = ", "el = "),
    "target": ("s_t (target", "alpha_t ="),
    "background": ("n_B (surface", "s_B (B", "theta_sun_B ="),
    "sun": ("theta_s =", "delta_phi ="),
    "world_axes": ("world X", "world Y", "world Z"),
    "projections": (
        "off-nadir projection",
        "α_t projection",
        "θ_sun,B projection",
    ),
}


def _names(traces: list) -> list[str]:
    return [getattr(t, "name", None) or "" for t in traces]


def _has_substring(names: list[str], needle: str) -> bool:
    """True if any trace name starts with `needle` (anchored prefix match,
    so sun-glyph hover text containing 'theta_s = …' does not collide with
    the sun-zenith arc whose name *starts* with 'theta_s = …')."""
    return any(n.startswith(needle) for n in names)


def test_default_angle_groups_constant() -> None:
    """The committed default is observer + target + background."""
    assert DEFAULT_ANGLE_GROUPS == frozenset({"observer", "target", "background"})


def test_empty_groups_omits_all_annotations() -> None:
    """An empty frozenset removes every group-gated trace."""
    state = SceneState.default()
    traces = build_scene_fn(state, angle_groups=frozenset())
    names = _names(traces)
    for needles in GROUP_SIGNATURES.values():
        for needle in needles:
            assert not _has_substring(names, needle), (
                f"empty selection still contains {needle!r}"
            )


def test_each_group_independently_adds_its_traces() -> None:
    """Selecting exactly one group surfaces exactly that group's signatures."""
    state = SceneState.default()
    for group, needles in GROUP_SIGNATURES.items():
        traces = build_scene_fn(state, angle_groups=frozenset({group}))
        names = _names(traces)
        for needle in needles:
            assert _has_substring(names, needle), (
                f"selecting {group!r} did not include trace matching {needle!r}"
            )
        for other_group, other_needles in GROUP_SIGNATURES.items():
            if other_group == group:
                continue
            for needle in other_needles:
                assert not _has_substring(names, needle), (
                    f"selecting {group!r} leaked {other_group!r} trace {needle!r}"
                )


def test_default_argument_matches_default_groups() -> None:
    """`angle_groups=None` falls back to DEFAULT_ANGLE_GROUPS."""
    state = SceneState.default()
    traces_default = _names(build_scene(state))
    traces_explicit = _names(build_scene(state, angle_groups=DEFAULT_ANGLE_GROUPS))
    assert traces_default == traces_explicit


def test_world_axes_group_off_by_default() -> None:
    """The world-axes triad is opt-in; it must not appear in the default scene."""
    state = SceneState.default()
    names = _names(build_scene(state))
    for needle in GROUP_SIGNATURES["world_axes"]:
        assert not _has_substring(names, needle), (
            f"world_axes leaked into default scene via {needle!r}"
        )


def test_projections_group_off_by_default() -> None:
    """Projections are opt-in; they must not appear in the default scene."""
    state = SceneState.default()
    names = _names(build_scene(state))
    for needle in GROUP_SIGNATURES["projections"]:
        assert not _has_substring(names, needle), (
            f"projections leaked into default scene via {needle!r}"
        )
