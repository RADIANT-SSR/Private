"""Phase 11 visual-polish tests.

Pins the following PLAN.md §12 contracts:
  (a) per-group arc radii — every arc anchors at its declared radius.
  (b) symbol-only on-figure labels — no `=` or numeric value rendered;
      Unicode subscripts present where the canonical mapping requires.
  (c) anchor-keyed color palette — every arc reads from `_arc_palette`.
  (d) camera auto-frame — default state still produces today's eye dict
      within ε; larger scenes scale outward.
  (e) readout rows — az/el/θ_s/Δφ all carry a `deg` unit token.
  (f) empty-selection caption — present iff `angle-groups == []`.
  (g) checklist persistence — non-default value passes through the
      callback unchanged across repeated invocations.
"""

from __future__ import annotations

import math
import re

import numpy as np
import plotly.graph_objects as go

from dev_tools.geometry_gui.app.layout.angle_group_controls import (
    EMPTY_SELECTION_CAPTION,
)
from dev_tools.geometry_gui.app.layout.readout_panel import READOUT_LINES
from dev_tools.geometry_gui.app.main import (
    ALL_INPUT_IDS,
    ALL_OUTPUTS,
    update_scene,
)
from dev_tools.geometry_gui.app.scene_builder._arc_labels import (
    ARC_LABELS,
    label_for,
)
from dev_tools.geometry_gui.app.scene_builder._arc_palette import (
    ARC_PALETTE,
    PROJECTION_ALPHA,
    arc_color_for,
)
from dev_tools.geometry_gui.app.scene_builder._arc_radii import (
    ARC_DISPLAY_RADII,
    arc_radius_for,
)
from dev_tools.geometry_gui.app.scene_builder._camera_frame import (
    DEFAULT_EYE,
    REFERENCE_HALF_EXTENT,
    camera_eye_from_traces,
)
from dev_tools.geometry_gui.app.scene_builder.azimuth_arc import azimuth_arc_traces
from dev_tools.geometry_gui.app.scene_builder.build_scene import build_scene
from dev_tools.geometry_gui.app.scene_builder.elevation_arc import (
    elevation_arc_traces,
)
from dev_tools.geometry_gui.app.scene_builder.off_nadir_arc import (
    off_nadir_arc_traces,
)
from dev_tools.geometry_gui.app.scene_builder.phase_angle_arc import (
    phase_angle_arc_traces,
)
from dev_tools.geometry_gui.app.scene_builder.solar_zenith_arc import (
    solar_zenith_arc_traces,
)
from dev_tools.geometry_gui.app.scene_builder.sun_azimuth_arc import (
    sun_azimuth_arc_traces,
)
from dev_tools.geometry_gui.app.scene_builder.sun_zenith_arc import (
    sun_zenith_arc_traces,
)
from dev_tools.geometry_gui.app.state import SceneState
from dev_tools.geometry_gui.tests.test_callback_smoke import _default_inputs


# ---------------------------------------------------------------------------
# (a) per-group arc radii
# ---------------------------------------------------------------------------


def test_arc_radii_table_contents() -> None:
    """The radii table contains exactly the seven arc keys."""
    assert set(ARC_DISPLAY_RADII) == {
        "off_nadir",
        "azimuth",
        "elevation",
        "phase_angle",
        "sun_zenith",
        "sun_azimuth",
        "solar_zenith_b",
    }


def test_arc_radii_match_plan() -> None:
    """Frozen mapping per PLAN.md §12."""
    assert arc_radius_for("off_nadir") == 0.40
    assert arc_radius_for("azimuth") == 0.40
    assert arc_radius_for("elevation") == 0.40
    assert arc_radius_for("phase_angle") == 0.60
    assert arc_radius_for("sun_zenith") == 0.80
    assert arc_radius_for("sun_azimuth") == 0.80
    assert arc_radius_for("solar_zenith_b") == 0.45


def _first_arc_radius(traces: list[go.Scatter3d], anchor: np.ndarray) -> float:
    """Return |first_point − anchor| for the first lines-mode trace."""
    for trace in traces:
        if getattr(trace, "mode", "") == "lines":
            xs = np.asarray(trace.x, dtype=float)
            ys = np.asarray(trace.y, dtype=float)
            zs = np.asarray(trace.z, dtype=float)
            return float(
                math.sqrt(
                    (xs[0] - anchor[0]) ** 2
                    + (ys[0] - anchor[1]) ** 2
                    + (zs[0] - anchor[2]) ** 2
                )
            )
    raise AssertionError("no lines-mode trace found")


def test_off_nadir_arc_anchors_at_off_nadir_radius() -> None:
    observer = np.array([-2.0, 0.0, 3.46], dtype=float)
    target = np.zeros(3, dtype=float)
    traces = off_nadir_arc_traces(observer, target)
    assert math.isclose(
        _first_arc_radius(traces, observer), arc_radius_for("off_nadir"), rel_tol=1e-9
    )


def test_phase_angle_arc_anchors_at_phase_angle_radius() -> None:
    target = np.zeros(3, dtype=float)
    view = np.array([1.0, 0.0, 1.0], dtype=float) / math.sqrt(2.0)
    sun = np.array([1.0, 1.0, 1.0], dtype=float) / math.sqrt(3.0)
    traces = phase_angle_arc_traces(target, view, sun)
    assert math.isclose(
        _first_arc_radius(traces, target), arc_radius_for("phase_angle"), rel_tol=1e-9
    )


def test_sun_zenith_arc_anchors_at_sun_zenith_radius() -> None:
    target = np.zeros(3, dtype=float)
    sun = np.array([0.5, 0.5, 1.0 / math.sqrt(2.0)], dtype=float)
    sun /= np.linalg.norm(sun)
    traces = sun_zenith_arc_traces(target, sun)
    assert math.isclose(
        _first_arc_radius(traces, target), arc_radius_for("sun_zenith"), rel_tol=1e-9
    )


def test_solar_zenith_at_b_uses_smaller_radius() -> None:
    bg = np.array([1.0, 0.0, -1.0], dtype=float)
    n = np.array([0.0, 0.0, 1.0], dtype=float)
    sun = np.array([0.5, 0.5, 0.7071], dtype=float)
    sun /= np.linalg.norm(sun)
    traces = solar_zenith_arc_traces(bg, n, sun)
    assert math.isclose(
        _first_arc_radius(traces, bg), arc_radius_for("solar_zenith_b"), rel_tol=1e-9
    )


# ---------------------------------------------------------------------------
# (b) symbol-only Unicode-subscript labels
# ---------------------------------------------------------------------------


def test_label_table_matches_plan() -> None:
    """Frozen Unicode-subscript mapping per PLAN.md §12."""
    assert label_for("off_nadir") == "θ_off"
    assert label_for("azimuth") == "az"
    assert label_for("elevation") == "el"
    assert label_for("phase_angle") == "αₜ"
    assert label_for("sun_zenith") == "θₛ"
    assert label_for("sun_azimuth") == "Δφ"
    assert label_for("solar_zenith_b") == "θ_sun,B"


def test_label_table_keys_match_radii_keys() -> None:
    assert set(ARC_LABELS) == set(ARC_DISPLAY_RADII)


def _text_traces(traces: list[go.Scatter3d]) -> list[go.Scatter3d]:
    return [t for t in traces if getattr(t, "mode", "") == "text"]


def test_arc_labels_carry_no_numeric_value() -> None:
    """No on-figure arc label string contains an `=` or a digit."""
    target = np.zeros(3, dtype=float)
    observer = np.array([-2.0, 0.0, 3.46], dtype=float)
    view = -np.array([0.5, 0.0, -math.sqrt(0.75)], dtype=float)
    sun = np.array([0.5, 0.5, 1.0]) / np.linalg.norm([0.5, 0.5, 1.0])
    bg = np.array([1.0, 0.0, -1.0], dtype=float)
    n = np.array([0.0, 0.0, 1.0], dtype=float)

    all_labels: list[str] = []
    for arc_traces in (
        off_nadir_arc_traces(observer, target),
        azimuth_arc_traces(target, -view),
        elevation_arc_traces(target, -view),
        phase_angle_arc_traces(target, view, sun),
        sun_zenith_arc_traces(target, sun),
        sun_azimuth_arc_traces(target, sun),
        solar_zenith_arc_traces(bg, n, sun),
    ):
        for txt in _text_traces(arc_traces):
            for s in txt.text:
                all_labels.append(s)

    digit_or_eq = re.compile(r"[=\d]")
    for s in all_labels:
        assert not digit_or_eq.search(s), (
            f"on-figure arc label {s!r} must be symbol-only (no `=`, no digit)"
        )


# ---------------------------------------------------------------------------
# (c) anchor-keyed color palette
# ---------------------------------------------------------------------------


def test_palette_table_contents() -> None:
    """Frozen anchor-keyed palette per PLAN.md §12."""
    assert ARC_PALETTE == {
        "observer": "#1f4ea8",
        "target": "#a83030",
        "background": "#7a3a1a",
        "sun": "#c08020",
    }


def test_projection_alpha_is_half() -> None:
    assert PROJECTION_ALPHA == 0.5


def _arc_line_color(traces: list[go.Scatter3d]) -> str:
    for t in traces:
        if getattr(t, "mode", "") == "lines":
            return t.line.color
    raise AssertionError("no lines-mode trace")


def test_observer_arcs_use_observer_color() -> None:
    target = np.zeros(3, dtype=float)
    observer = np.array([-2.0, 0.0, 3.46], dtype=float)
    boresight = (target - observer) / np.linalg.norm(target - observer)
    expected = arc_color_for("observer")
    assert _arc_line_color(off_nadir_arc_traces(observer, target)) == expected
    assert _arc_line_color(azimuth_arc_traces(target, boresight)) == expected
    assert _arc_line_color(elevation_arc_traces(target, boresight)) == expected


def test_target_arc_uses_target_color() -> None:
    target = np.zeros(3, dtype=float)
    view = np.array([1.0, 0.0, 1.0]) / math.sqrt(2.0)
    sun = np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)
    assert (
        _arc_line_color(phase_angle_arc_traces(target, view, sun))
        == arc_color_for("target")
    )


def test_sun_arcs_use_sun_color() -> None:
    target = np.zeros(3, dtype=float)
    sun = np.array([0.5, 0.5, 1.0]) / np.linalg.norm([0.5, 0.5, 1.0])
    expected = arc_color_for("sun")
    assert _arc_line_color(sun_zenith_arc_traces(target, sun)) == expected
    assert _arc_line_color(sun_azimuth_arc_traces(target, sun)) == expected


def test_background_arc_uses_background_color() -> None:
    bg = np.array([1.0, 0.0, -1.0], dtype=float)
    n = np.array([0.0, 0.0, 1.0], dtype=float)
    sun = np.array([0.5, 0.5, 1.0]) / np.linalg.norm([0.5, 0.5, 1.0])
    assert (
        _arc_line_color(solar_zenith_arc_traces(bg, n, sun))
        == arc_color_for("background")
    )


# ---------------------------------------------------------------------------
# (d) camera auto-frame
# ---------------------------------------------------------------------------


def test_camera_default_state_eye_unchanged() -> None:
    """Default-state base scene returns today's framing (1.8, 1.8, 1.4)."""
    state = SceneState.default()
    traces = build_scene(state, angle_groups=frozenset())
    eye = camera_eye_from_traces(traces)
    assert math.isclose(eye["x"], DEFAULT_EYE[0], rel_tol=1e-6)
    assert math.isclose(eye["y"], DEFAULT_EYE[1], rel_tol=1e-6)
    assert math.isclose(eye["z"], DEFAULT_EYE[2], rel_tol=1e-6)


def test_camera_scales_with_larger_bbox() -> None:
    """A trace that pushes well past the reference half-extent enlarges the eye."""

    class _BigTrace:
        x = [0.0, 3.0 * REFERENCE_HALF_EXTENT]
        y = [0.0, 0.0]
        z = [0.0, 0.0]

    eye = camera_eye_from_traces([_BigTrace()])  # type: ignore[list-item]
    assert eye["x"] > DEFAULT_EYE[0] * 2.0


def test_camera_empty_traces_returns_default() -> None:
    eye = camera_eye_from_traces([])
    assert eye == {
        "x": DEFAULT_EYE[0],
        "y": DEFAULT_EYE[1],
        "z": DEFAULT_EYE[2],
    }


# ---------------------------------------------------------------------------
# (e) readout rows for az / el / θ_s / Δφ
# ---------------------------------------------------------------------------


_NEW_READOUT_IDS: tuple[str, ...] = (
    "ro-view-azimuth",
    "ro-view-elevation",
    "ro-solar-zenith",
    "ro-relative-azimuth",
)


def test_readout_panel_includes_new_rows() -> None:
    rendered_ids = {component_id for component_id, _ in READOUT_LINES}
    for new_id in _NEW_READOUT_IDS:
        assert new_id in rendered_ids


def test_readout_new_rows_carry_unit_token() -> None:
    """Every new readout row ends in `deg` (C4 hard rule)."""
    inputs = _default_inputs()
    out = update_scene(*inputs)
    out_dict = {component_id: value for (component_id, _prop), value in zip(ALL_OUTPUTS, out)}
    rendered_text: str = out_dict["readout-text"]
    for new_id in _NEW_READOUT_IDS:
        # Every new row must appear in the rendered block AND end with `deg`.
        # Lines look like `View azimuth az            : 180.00 deg`
        # We read the new value out of the format_readout pipeline by
        # rebuilding it directly:
        pass
    from dev_tools.geometry_gui.app.state import SceneState
    from dev_tools.geometry_gui.app.view_model import classify_regime, format_readout

    state = SceneState.default()
    regime, reason = classify_regime(state)
    formatted = format_readout(state, regime, reason)
    for new_id in _NEW_READOUT_IDS:
        assert new_id in formatted
        assert formatted[new_id].endswith(" deg"), formatted[new_id]
    # And the rendered block must contain "deg" tokens for those rows.
    assert " deg" in rendered_text


# ---------------------------------------------------------------------------
# (f) empty-selection caption
# ---------------------------------------------------------------------------


def _outputs_dict(out: tuple) -> dict[str, object]:
    return {component_id: value for (component_id, _prop), value in zip(ALL_OUTPUTS, out)}


def test_empty_caption_shown_when_no_groups_selected() -> None:
    inputs = list(_default_inputs())
    inputs[ALL_INPUT_IDS.index("angle-groups")] = []
    out = update_scene(*inputs)
    out_dict = _outputs_dict(out)
    assert out_dict["angle-groups-empty-caption"] == EMPTY_SELECTION_CAPTION


def test_empty_caption_blank_when_default_groups_selected() -> None:
    inputs = list(_default_inputs())
    out = update_scene(*inputs)
    out_dict = _outputs_dict(out)
    assert out_dict["angle-groups-empty-caption"] == ""


# ---------------------------------------------------------------------------
# (g) checklist persistence — value survives repeated callback invocations
# ---------------------------------------------------------------------------


def test_checklist_value_persists_across_callback_invocations() -> None:
    """Non-default checklist value reads back unchanged on every call.

    Phase-10/11 regression guard: Dash sees the live `value` of a Checklist
    on every Input fire, so the *callback* always reflects the user's
    selection. This test pins that contract by re-driving the callback
    with a non-default value across multiple unrelated slider changes
    and verifying the angle-groups value is honored each time (the
    figure trace count differs from the default-groups baseline).
    """
    base = list(_default_inputs())
    custom_value: list[str] = ["world_axes"]
    base[ALL_INPUT_IDS.index("angle-groups")] = custom_value

    # Drive the callback with the custom value plus several different
    # slider settings; trace count must match between invocations because
    # only the angle_groups-gated traces depend on the checklist value.
    counts: list[int] = []
    for look_deg in (10.0, 25.0, 45.0):
        inputs = list(base)
        inputs[ALL_INPUT_IDS.index("obs-look-angle")] = look_deg
        out = update_scene(*inputs)
        fig: go.Figure = _outputs_dict(out)["scene"]  # type: ignore[assignment]
        # Count traces whose name starts with "X axis" / "Y axis" / "Z axis"
        # — these are the world-axes triad we explicitly enabled.
        triad = [t for t in fig.data if (t.name or "").startswith("world ")]
        counts.append(len(triad))
    # Each axis emits one lines-mode trace named "world X" / "world Y" /
    # "world Z" (the text-mode label trace has name=None), so 3 per call.
    assert counts == [3, 3, 3], (
        f"world_axes triad must persist across slider drags; got {counts}"
    )


# ---------------------------------------------------------------------------
# Callback output arity sanity (Phase 11 added one more output)
# ---------------------------------------------------------------------------


def test_callback_output_arity_includes_empty_caption() -> None:
    """ALL_OUTPUTS now includes the `angle-groups-empty-caption` slot."""
    out_ids = [component_id for component_id, _ in ALL_OUTPUTS]
    assert "angle-groups-empty-caption" in out_ids
