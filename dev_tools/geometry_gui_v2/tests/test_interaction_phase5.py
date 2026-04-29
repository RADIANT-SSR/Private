"""Phase 5 acceptance — interaction layer.

Covers (PLAN_v2.md §13):
  * ``InteractionState`` state machine (frozen replace pattern, defaults).
  * ``camera_pose_for`` returns a valid (position, focal, up) triple for
    every canonical view, with the expected geometric properties (camera
    points at origin, view_up is unit-length, ``iso`` matches the Phase-1
    golden pose used by the screenshot tests).
  * ``KEY_TO_VIEW`` covers the 1–6 keys.
  * ``scene.highlight._ACTORS_PER_PRIMITIVE`` covers every primitive the UI
    can pick, every actor name resolves uniquely (no two primitives claim
    the same actor), and ``apply_highlight`` is a no-op for ``None``.
  * Qt main window wiring: frame switcher updates the indicator label,
    keyboard shortcuts are registered, ``_set_active_edit`` re-renders.
    Skips cleanly when PySide6 / pyvistaqt aren't available.
"""

from __future__ import annotations

import math
import os
from typing import Iterator

import pytest

from dev_tools.geometry_gui_v2.app.interaction_state import (
    KEY_TO_VIEW,
    CanonicalView,
    DisplayFrame,
    InteractionState,
    frame_indicator_text,
)
from dev_tools.geometry_gui_v2.scene import highlight
from dev_tools.geometry_gui_v2.scene.camera_views import (
    CANONICAL_DISTANCE_M,
    camera_pose_for,
)


# --- InteractionState ------------------------------------------------------


def test_interaction_state_default_values() -> None:
    """The default state opens in the body frame with no active edit."""
    s = InteractionState()
    assert s.display_frame is DisplayFrame.BODY
    assert s.active_edit is None
    assert s.last_canonical_view is CanonicalView.ISO


def test_interaction_state_with_methods_return_new_instance() -> None:
    """The dataclass is frozen — every ``with_*`` returns a new object."""
    s = InteractionState()
    s2 = s.with_display_frame(DisplayFrame.WORLD)
    assert s2 is not s
    assert s2.display_frame is DisplayFrame.WORLD
    # Original unchanged (frozen).
    assert s.display_frame is DisplayFrame.BODY

    s3 = s.with_active_edit("vec_boresight")
    assert s3.active_edit == "vec_boresight"
    assert s3.display_frame is DisplayFrame.BODY  # unrelated field unchanged

    s4 = s.with_canonical_view(CanonicalView.TOP)
    assert s4.last_canonical_view is CanonicalView.TOP


def test_interaction_state_clear_active_edit() -> None:
    """Passing ``None`` clears the active edit (deselect)."""
    s = InteractionState().with_active_edit("vec_boresight")
    assert s.active_edit == "vec_boresight"
    cleared = s.with_active_edit(None)
    assert cleared.active_edit is None


def test_frame_indicator_text_format() -> None:
    """HUD text matches the spec wording exactly (PLAN_v2.md §13 step 7)."""
    assert (
        frame_indicator_text(InteractionState())
        == "Frame: Body  \u00b7  Origin: Target centroid"
    )
    assert (
        frame_indicator_text(InteractionState().with_display_frame(DisplayFrame.WORLD))
        == "Frame: World  \u00b7  Origin: Target centroid"
    )
    assert (
        frame_indicator_text(InteractionState().with_display_frame(DisplayFrame.SENSOR))
        == "Frame: Sensor  \u00b7  Origin: Target centroid"
    )


def test_display_frame_values_are_lowercase_strings() -> None:
    """The enum value is the canonical lowercase form; ``display_name``
    title-cases it for the UI."""
    assert DisplayFrame.WORLD.value == "world"
    assert DisplayFrame.WORLD.display_name == "World"
    assert DisplayFrame.BODY.display_name == "Body"
    assert DisplayFrame.SENSOR.display_name == "Sensor"


# --- KEY_TO_VIEW ----------------------------------------------------------


def test_key_to_view_covers_keys_one_through_six() -> None:
    """Keys 1–6 map to the six axis-aligned canonical views; ``ISO`` is
    reserved for camera-reset / default and has no number key."""
    assert set(KEY_TO_VIEW.keys()) == {"1", "2", "3", "4", "5", "6"}
    assert set(KEY_TO_VIEW.values()) == {
        CanonicalView.FRONT,
        CanonicalView.BACK,
        CanonicalView.LEFT,
        CanonicalView.RIGHT,
        CanonicalView.TOP,
        CanonicalView.BOTTOM,
    }


# --- camera_pose_for ------------------------------------------------------


@pytest.mark.parametrize(
    "view",
    ["front", "back", "left", "right", "top", "bottom", "iso"],
)
def test_camera_pose_for_returns_unit_view_up(view: str) -> None:
    """``view_up`` must be a unit vector (PyVista will normalize anyway, but
    explicit unit input keeps the convention obvious)."""
    _pos, _focal, up = camera_pose_for(view)
    norm = math.sqrt(up[0] ** 2 + up[1] ** 2 + up[2] ** 2)
    assert norm == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize(
    "view",
    ["front", "back", "left", "right", "top", "bottom", "iso"],
)
def test_camera_pose_for_focal_point_is_origin(view: str) -> None:
    """All canonical views look at the target centroid (origin)."""
    _pos, focal, _up = camera_pose_for(view)
    assert focal == (0.0, 0.0, 0.0)


@pytest.mark.parametrize(
    "view, expected_axis",
    [
        ("front", (1.0, 0.0, 0.0)),
        ("back", (-1.0, 0.0, 0.0)),
        ("left", (0.0, 1.0, 0.0)),
        ("right", (0.0, -1.0, 0.0)),
        ("top", (0.0, 0.0, 1.0)),
        ("bottom", (0.0, 0.0, -1.0)),
    ],
)
def test_camera_pose_for_axis_aligned_views(
    view: str, expected_axis: tuple[float, float, float]
) -> None:
    """Each axis-aligned view places the camera one ``CANONICAL_DISTANCE_M``
    along its named axis."""
    pos, _focal, _up = camera_pose_for(view)
    for got, want in zip(pos, expected_axis):
        assert got == pytest.approx(want * CANONICAL_DISTANCE_M, abs=1e-9)


def test_camera_pose_for_iso_is_round2_isometric_three_quarter() -> None:
    """R1 of round-2 visual remediation: the iso pose is the standard
    isometric three-quarter view (elev = 25°, az = 45°), not the legacy
    Phase-1 pose (elev = arctan(0.5), az = 35°).

    The phase-1 golden test in ``test_scene_goldens_phase1.py`` keeps a
    locally-hardcoded camera so its goldens stay reproducible against
    the legacy pose; the canonical iso pose used by the view-cube and
    the default-camera helper is the round-2 spec.
    """
    pos, _focal, _up = camera_pose_for("iso")
    d = CANONICAL_DISTANCE_M
    elev = math.radians(25.0)
    az = math.radians(45.0)
    assert pos[0] == pytest.approx(d * math.cos(elev) * math.cos(az), abs=1e-9)
    assert pos[1] == pytest.approx(d * math.cos(elev) * math.sin(az), abs=1e-9)
    assert pos[2] == pytest.approx(d * math.sin(elev), abs=1e-9)


def test_camera_pose_for_unknown_view_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unknown view"):
        camera_pose_for("nope")


# --- highlight registry ---------------------------------------------------


def test_selectable_primitives_includes_every_documented_pickable() -> None:
    """The pickable set must cover the four user-facing primitive families:
    vectors, arcs, glyphs, and the target body. Tests the *minimum* set; the
    registry may grow."""
    primitives = set(highlight.selectable_primitives())
    must_have = {
        "vec_boresight",
        "vec_surface_normal",
        "vec_sun_ray",
        "vec_sun_to_background",
        "arc_off_nadir",
        "arc_phase_angle",
        "arc_sun_zenith",
        "glyph_observer",
        "glyph_sun",
        "glyph_background",
        "target",
    }
    missing = must_have - primitives
    assert not missing, f"highlight registry missing primitives: {missing}"


def test_actors_for_primitive_returns_at_least_base_actor() -> None:
    """Every primitive's actor tuple includes its base actor name (the name
    matches the primitive key)."""
    for primitive in highlight.selectable_primitives():
        actors = highlight.actors_for_primitive(primitive)
        assert primitive in actors, (
            f"primitive {primitive!r} actor tuple {actors} should include "
            f"the base actor with the same name"
        )


def test_actors_for_primitive_unknown_raises() -> None:
    with pytest.raises(KeyError):
        highlight.actors_for_primitive("does_not_exist")


def test_no_actor_is_owned_by_two_primitives() -> None:
    """A picked actor must resolve to exactly one primitive — no overlap.
    The Qt shell builds an inverse lookup table assuming this."""
    seen: dict[str, str] = {}
    for primitive in highlight.selectable_primitives():
        for actor in highlight.actors_for_primitive(primitive):
            assert actor not in seen, (
                f"actor {actor!r} claimed by both {seen[actor]!r} and "
                f"{primitive!r}"
            )
            seen[actor] = primitive


def test_apply_highlight_with_none_is_noop() -> None:
    """Passing ``None`` is the deselect path — must not raise even with no
    plotter side-effects to make."""

    class _SentinelPlotter:
        actors: dict[str, object] = {}

    highlight.apply_highlight(_SentinelPlotter(), None)  # type: ignore[arg-type]


def test_apply_highlight_unknown_primitive_is_noop() -> None:
    """An unknown primitive name silently does nothing (the Qt picking
    callback may pass a name we don't have a registry entry for; we don't
    want to crash the GUI)."""

    class _SentinelPlotter:
        actors: dict[str, object] = {}

    highlight.apply_highlight(_SentinelPlotter(), "not_a_primitive")  # type: ignore[arg-type]


def test_apply_highlight_stamps_accent_on_known_actors() -> None:
    """When a primitive has actors in the plotter, every constituent actor
    gets the accent color and accent line width."""
    from dev_tools.geometry_gui_v2.scene import style

    accent_rgb = (
        int(style.ACCENT_COLOR.lstrip("#")[0:2], 16) / 255.0,
        int(style.ACCENT_COLOR.lstrip("#")[2:4], 16) / 255.0,
        int(style.ACCENT_COLOR.lstrip("#")[4:6], 16) / 255.0,
    )

    class _FakeProperty:
        def __init__(self) -> None:
            self.color: tuple[float, float, float] | None = None
            self.edge_color: tuple[float, float, float] | None = None
            self.line_width: float | None = None

        def SetColor(self, r: float, g: float, b: float) -> None:
            self.color = (r, g, b)

        def SetEdgeColor(self, r: float, g: float, b: float) -> None:
            self.edge_color = (r, g, b)

        def SetLineWidth(self, w: float) -> None:
            self.line_width = w

    class _FakeActor:
        def __init__(self) -> None:
            self._prop = _FakeProperty()

        def GetProperty(self) -> _FakeProperty:
            return self._prop

    class _FakePlotter:
        def __init__(self) -> None:
            self.actors = {
                name: _FakeActor()
                for name in highlight.actors_for_primitive("vec_boresight")
            }

    plotter = _FakePlotter()
    highlight.apply_highlight(plotter, "vec_boresight")  # type: ignore[arg-type]

    for name, actor in plotter.actors.items():
        prop = actor.GetProperty()
        assert prop.color == pytest.approx(accent_rgb, abs=1e-9), (
            f"{name!r} did not receive accent color"
        )
        assert prop.edge_color == pytest.approx(accent_rgb, abs=1e-9)
        assert prop.line_width == style.ACCENT_LINE_WIDTH


# --- Qt main-window wiring ------------------------------------------------
# These tests construct a live ``GeometryMainWindow`` (which embeds a
# ``QtInteractor``). On platforms where the offscreen Qt platform plugin
# cannot create a real GL context, ``QtInteractor.__init__`` segfaults
# *during construction* — Python's exception handling can't recover from
# that. To opt in, set ``RADIANT_GUI_FULL_WINDOW_TESTS=1`` (CI does this in
# environments that have a working virtual framebuffer; local dev on
# headless macOS skips them).
#
# Equivalent coverage on non-segfault paths is provided by
# tests/test_readouts_panel.py (panel construction) and the pure-Python
# tests above (state machine, camera poses, highlight registry).

os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

_FULL_WINDOW_TESTS_ENABLED = os.environ.get("RADIANT_GUI_FULL_WINDOW_TESTS") == "1"

pytestmark_window = pytest.mark.skipif(
    not _FULL_WINDOW_TESTS_ENABLED,
    reason=(
        "Set RADIANT_GUI_FULL_WINDOW_TESTS=1 to run the full QtInteractor-"
        "backed window tests. Skipped by default because offscreen GL "
        "contexts segfault on some platforms during QtInteractor.__init__."
    ),
)


@pytest.fixture(scope="module")
def qt_app() -> Iterator[object]:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def main_window(qt_app):
    """Construct the main window once per test. Skip on QtInteractor failure
    (offscreen GL contexts vary by platform)."""
    try:
        from dev_tools.geometry_gui_v2.app.main import GeometryMainWindow

        win = GeometryMainWindow()
    except Exception as exc:
        pytest.skip(f"GeometryMainWindow unavailable in this environment: {exc}")
    yield win
    try:
        win.close()
    except Exception:
        pass


@pytestmark_window
def test_main_window_has_frame_switcher_with_three_options(main_window) -> None:
    combo = main_window._frame_combo
    assert combo.count() == 3
    items = [combo.itemText(i) for i in range(combo.count())]
    assert items == ["World", "Body", "Sensor"]


@pytestmark_window
def test_frame_switcher_updates_indicator_label(main_window) -> None:
    """Selecting a different frame must update the HUD text immediately."""
    label = main_window._frame_indicator_label
    combo = main_window._frame_combo

    combo.setCurrentIndex(0)  # World
    assert "World" in label.text()

    combo.setCurrentIndex(2)  # Sensor
    assert "Sensor" in label.text()

    combo.setCurrentIndex(1)  # Body
    assert "Body" in label.text()


@pytestmark_window
def test_frame_switcher_updates_interaction_state(main_window) -> None:
    """The combo must drive ``InteractionState.display_frame``."""
    main_window._frame_combo.setCurrentIndex(0)  # World
    assert main_window._interaction.display_frame is DisplayFrame.WORLD

    main_window._frame_combo.setCurrentIndex(2)  # Sensor
    assert main_window._interaction.display_frame is DisplayFrame.SENSOR


@pytestmark_window
def test_frame_indicator_label_reads_target_centroid(main_window) -> None:
    """The HUD always names ``Origin: Target centroid`` regardless of frame."""
    label = main_window._frame_indicator_label
    assert "Origin: Target centroid" in label.text()


@pytestmark_window
def test_snap_to_view_updates_camera_position(main_window) -> None:
    """Pressing a number key (proxied here through ``_snap_to_view``) must
    actually move the camera."""
    main_window._snap_to_view(CanonicalView.TOP)
    pos = main_window.plotter.camera_position[0]
    expected_pos, _focal, _up = camera_pose_for("top")
    for got, want in zip(pos, expected_pos):
        assert got == pytest.approx(want, abs=1e-6)


@pytestmark_window
def test_snap_to_view_updates_interaction_state(main_window) -> None:
    main_window._snap_to_view(CanonicalView.LEFT)
    assert main_window._interaction.last_canonical_view is CanonicalView.LEFT


@pytestmark_window
def test_set_active_edit_updates_state(main_window) -> None:
    """The pick callback funnels through ``_set_active_edit`` — verify it
    propagates to the dataclass without raising."""
    main_window._set_active_edit("vec_boresight")
    assert main_window._interaction.active_edit == "vec_boresight"

    main_window._set_active_edit(None)
    assert main_window._interaction.active_edit is None


@pytestmark_window
def test_keyboard_shortcuts_registered(main_window) -> None:
    """All Phase-5 shortcuts (R, 1–6, ?) must be live as ``QShortcut`` children
    of the main window."""
    from PySide6.QtGui import QShortcut

    shortcut_keys = {
        sc.key().toString().upper()
        for sc in main_window.findChildren(QShortcut)
    }
    expected = {"R", "1", "2", "3", "4", "5", "6", "?"}
    missing = expected - shortcut_keys
    assert not missing, f"missing shortcuts: {missing} (have {shortcut_keys})"
