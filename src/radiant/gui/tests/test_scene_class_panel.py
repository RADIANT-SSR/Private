"""Tests for the Geometry screen's scene-class steering card (Geometry-Flexibility Phase 4).

These drive the real widget on the shipped example config, offscreen. The contracts:

* **pre-evaluate** the chip is a neutral placeholder and the relevance block shows
  nothing — the panel never guesses a class it has not been told;
* the **derived** chip renders ``stage_outputs["geometry"]`` verbatim (the stage is the
  single source of angle/label truth, arch doc §6.3), naming both bands and the key;
* the **assertion** edit goes through the shared Parameter Editor: exactly one
  ``sensor.set`` on the live sensor and one ``parameterEdited`` emission, so results go
  stale and the host re-evaluates — the same discipline as every other Inputs field;
* the **relevance** list equals the ``radiant.api.scene_relevance`` bridge's
  ``default_off_metrics`` for the displayed class, rendered with human labels (never a
  raw registry key), and differs the documented way between a ground target
  (target-plane family off) and an air target (ground-projection family off);
* an asserted-vs-derived **mismatch** tints the card in place, shows the error's
  what-line, and clears on a clean run — routed by the window's geometry-conflict path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import radiant.gui.widgets.actionable_error_dialog as aed
from radiant.api.scene_relevance import default_off_metrics
from radiant.api.sensor import Sensor
from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.metric_format import METRIC_DISPLAY_LABELS, metric_display_label
from radiant.gui.stage_views import STAGE_COMPOSITIONS
from radiant.gui.widgets import scene_class_panel as scp
from radiant.gui.widgets.scene_class_panel import (
    SCENE_CLASS_PARAM,
    SceneClassPanel,
    names_scene_class_assertion,
    off_metric_labels,
)
from radiant.gui.widgets.stage_center import StagePane

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 15000

# A LEO down-looking example: space observer, ground target.
_GROUND_OUTPUTS = {
    "scene_class": "space_to_ground",
    "observer_class": "space",
    "target_class": "ground",
}
_AIR_OUTPUTS = {
    "scene_class": "ground_to_air",
    "observer_class": "ground",
    "target_class": "air",
}


@pytest.fixture(scope="module")
def sensor() -> Sensor:
    """A sensor loaded from the shipped example config."""
    return Sensor.load(_EXAMPLE)


def _panel(qtbot, sensor: Sensor | None = None) -> SceneClassPanel:  # type: ignore[no-untyped-def]
    """A panel bound to *sensor* (or unbound) with a fresh display-unit store."""
    panel = SceneClassPanel()
    qtbot.addWidget(panel)
    panel.bind_sensor(sensor, {})
    return panel


def _load_window(qtbot):  # type: ignore[no-untyped-def]
    """Build a window on the example config and wait for its auto-evaluation."""
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


# ---------------------------------------------------------------------------
# Relevance model (Qt-free — the bridge + the display wording)
# ---------------------------------------------------------------------------


class TestOffMetricLabels:
    def test_no_class_lists_nothing(self) -> None:
        """No class known → nothing shown, rather than the metric layer's ground fallback."""
        assert off_metric_labels(None) == ()

    def test_ground_target_matches_the_bridge(self) -> None:
        """A ground target's off-set is the bridge's, rendered with human labels."""
        expected = {metric_display_label(k) for k in default_off_metrics("space_to_ground")}
        assert set(off_metric_labels("space_to_ground")) == expected

    def test_air_target_matches_the_bridge(self) -> None:
        """An air target's off-set is the bridge's, rendered with human labels."""
        expected = {metric_display_label(k) for k in default_off_metrics("ground_to_air")}
        assert set(off_metric_labels("ground_to_air")) == expected

    def test_ground_and_air_differ_the_documented_way(self) -> None:
        """Ground drops the target-plane family; air drops the ground-projection family."""
        ground = off_metric_labels("space_to_ground")
        air = off_metric_labels("ground_to_air")
        assert "Target-plane sample distance (x)" in ground
        assert "GSD (geometric mean)" not in ground
        assert "GSD (geometric mean)" in air
        assert "NIIRS" in air
        assert "Target-plane sample distance (x)" not in air

    def test_no_raw_registry_keys_reach_the_screen(self) -> None:
        """Every listed label is a human label, never the raw metric key."""
        for scene_class in ("space_to_ground", "ground_to_air", "air_to_space"):
            for label in off_metric_labels(scene_class):
                assert label in METRIC_DISPLAY_LABELS.values()

    def test_order_follows_the_display_table(self) -> None:
        """Rows read in the registry's physics order, not alphabetically."""
        labels = off_metric_labels("ground_to_air")
        rank = list(METRIC_DISPLAY_LABELS.values())
        positions = [rank.index(label) for label in labels]
        assert positions == sorted(positions)


class TestErrorPredicate:
    def test_mismatch_context_is_recognised(self) -> None:
        """The stage's asserted/derived context routes to this card."""
        ctx = {"asserted": "ground_to_ground", "derived": "space_to_ground"}
        assert names_scene_class_assertion("…asserts…", ctx)

    def test_bounds_error_what_is_recognised(self) -> None:
        """The defence-in-depth 'not a scene class' error names the parameter."""
        what = "geometry.scene_class = 'sea_to_ground' is not a scene class"
        assert names_scene_class_assertion(what, {"asserted": "sea_to_ground", "valid": ()})

    def test_unrelated_geometry_error_is_not_this_cards(self) -> None:
        """A viewing over-spec is the mode form's conflict, not the scene-class card's."""
        ctx = {"geometry.path_zenith_rad": 0.5, "geometry.sensor_off_nadir_rad": 0.1}
        assert not names_scene_class_assertion("Over-specified viewing geometry", ctx)


# ---------------------------------------------------------------------------
# The widget
# ---------------------------------------------------------------------------


class TestSceneClassPanel:
    def test_placeholder_before_any_evaluation(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """Pre-evaluate: a neutral chip and no relevance list — no guessed class."""
        panel = _panel(qtbot, sensor)
        assert panel.chip_text() == "Scene: evaluate to derive"
        assert panel.derived_class is None
        assert panel.displayed_class() is None
        assert panel.relevance_labels() == ()
        assert not panel.relevance_visible()

    def test_assertion_row_shows_the_schema_default_unset(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """The example asserts nothing: the field shows the sentinel, not a class."""
        panel = _panel(qtbot, sensor)
        assert panel.assertion_row.dotpath == SCENE_CLASS_PARAM
        assert panel.asserted_class() is None
        assert "auto" in panel.assertion_row.value_text()

    def test_derived_chip_after_populate(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """The chip names both bands and the class key, marked as derived."""
        panel = _panel(qtbot, sensor)
        panel.populate(_GROUND_OUTPUTS)
        assert panel.chip_text() == "Scene: space → ground (space_to_ground) — derived"
        assert panel.derived_class == "space_to_ground"

    def test_partial_outputs_leave_the_placeholder(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """Outputs without a scene_class key are not guessed at."""
        panel = _panel(qtbot, sensor)
        panel.populate({"theta_o_rad": 0.1})
        assert panel.chip_text() == "Scene: evaluate to derive"
        assert not panel.relevance_visible()

    def test_relevance_follows_the_derived_class(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """Populating a ground-target class lists exactly that class's off-set."""
        panel = _panel(qtbot, sensor)
        panel.populate(_GROUND_OUTPUTS)
        assert panel.relevance_visible()
        assert panel.relevance_labels() == off_metric_labels("space_to_ground")

    def test_relevance_swaps_with_the_class(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """A second evaluation with an air target replaces the list (no stale rows)."""
        panel = _panel(qtbot, sensor)
        panel.populate(_GROUND_OUTPUTS)
        panel.populate(_AIR_OUTPUTS)
        assert panel.relevance_labels() == off_metric_labels("ground_to_air")
        assert "Target-plane sample distance (x)" not in panel.relevance_labels()

    def test_chip_reports_an_agreeing_assertion(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """An assertion that matches the derivation is reported beside it, not instead."""
        live = Sensor.load(_EXAMPLE)
        live.set(SCENE_CLASS_PARAM, "space_to_ground")
        panel = _panel(qtbot, live)
        panel.populate(_GROUND_OUTPUTS)
        assert panel.chip_text().endswith("— derived; assertion agrees")
        assert panel.asserted_class() == "space_to_ground"

    def test_asserted_class_drives_the_preview_before_evaluation(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Asserting steers the defaults up front — the preview follows the assertion.

        The derived label still leads the chip (it is what the chain actually ran),
        so an asserted class can never masquerade as a derivation.
        """
        live = Sensor.load(_EXAMPLE)
        live.set(SCENE_CLASS_PARAM, "ground_to_air")
        panel = _panel(qtbot, live)
        panel.populate(_GROUND_OUTPUTS)  # the last clean run's derivation
        assert "asserted ground_to_air" in panel.chip_text()
        assert panel.chip_text().startswith("Scene: space → ground (space_to_ground) — derived")
        assert panel.displayed_class() == "ground_to_air"
        assert panel.relevance_labels() == off_metric_labels("ground_to_air")

    def test_unbound_panel_shows_nothing(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """With no sensor the field blanks and the chip stays neutral (pre-config)."""
        panel = _panel(qtbot, None)
        assert panel.chip_text() == "Scene: evaluate to derive"
        assert panel.assertion_row.value_text() == "—"

    def test_rebinding_drops_the_previous_scenes_class(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """A config swap must not leave the old scene's derived class on screen."""
        panel = _panel(qtbot, sensor)
        panel.populate(_GROUND_OUTPUTS)
        panel.bind_sensor(Sensor.load(_EXAMPLE), {})
        assert panel.derived_class is None
        assert panel.chip_text() == "Scene: evaluate to derive"
        assert not panel.relevance_visible()

    def test_conflict_tint_set_and_cleared(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """A mismatch tints the card and shows the what-line; clearing drops both."""
        panel = _panel(qtbot, sensor)
        what = "geometry.scene_class asserts 'ground_to_ground', but the altitudes derive …"
        ctx = {"asserted": "ground_to_ground", "derived": "space_to_ground"}
        assert panel.highlight_error(what, ctx)
        assert panel.is_conflicting()
        assert panel.conflict_text() == what
        panel.clear_highlight()
        assert not panel.is_conflicting()
        assert panel.conflict_text() == ""

    def test_unrelated_error_leaves_the_card_alone(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """A viewing over-spec is not this card's conflict."""
        panel = _panel(qtbot, sensor)
        ctx = {"geometry.path_zenith_rad": 0.5, "geometry.sensor_off_nadir_rad": 0.1}
        assert not panel.highlight_error("Over-specified viewing geometry", ctx)
        assert not panel.is_conflicting()


class TestAssertionEdit:
    def test_edit_is_one_set_and_one_signal(self, qtbot, monkeypatch, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """An accepted assertion edit: exactly one sensor.set + one parameterEdited.

        The commit goes through the shared Parameter Editor (validated on a throwaway
        clone first), so this exercises the same edit+reject discipline as every other
        schema field — no bespoke setter on this card.
        """
        live = Sensor.load(_EXAMPLE)
        panel = _panel(qtbot, live)

        set_calls: list[str] = []
        orig_set = type(live).set

        def counting_set(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if self is live and args:
                set_calls.append(args[0])
            return orig_set(self, *args, **kwargs)

        monkeypatch.setattr(type(live), "set", counting_set)

        def fake_exec(self):  # type: ignore[no-untyped-def]
            self.value_editor.setCurrentText("space_to_ground")  # the enum combo
            self.apply(close=True)
            return 0

        monkeypatch.setattr(scp.ParameterEditorDialog, "exec", fake_exec)
        with qtbot.waitSignal(panel.parameterEdited, timeout=_WAIT_MS) as blocker:
            panel._open_editor(SCENE_CLASS_PARAM)  # noqa: SLF001 — the commit path

        assert set_calls == [SCENE_CLASS_PARAM]
        assert blocker.args == [SCENE_CLASS_PARAM]
        assert live.get(SCENE_CLASS_PARAM) == "space_to_ground"
        # The card adopted the assertion: the field re-read, and the relevance preview
        # now describes the asserted class even though nothing has been evaluated yet.
        assert panel.asserted_class() == "space_to_ground"
        assert panel.displayed_class() == "space_to_ground"
        assert panel.relevance_labels() == off_metric_labels("space_to_ground")
        assert "asserted" in panel.chip_text()
        # The unbound-sensor reference above stays untouched (module fixture hygiene).
        assert sensor.get(SCENE_CLASS_PARAM) == "auto"


# ---------------------------------------------------------------------------
# Wiring — the pane mounts it, the window routes the mismatch to it
# ---------------------------------------------------------------------------


class TestGeometryPaneWiring:
    def test_inputs_tab_declares_the_card(self) -> None:
        """The Qt-free composition puts the card on the Geometry Inputs sub-view."""
        inputs = STAGE_COMPOSITIONS["geometry"].subviews[0]
        assert inputs.title == "Inputs"
        assert inputs.scene_class_panel

    def test_pane_builds_the_card_above_the_mode_form(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Geometry pane mounts the card, and it sits before the mode form."""
        pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
        qtbot.addWidget(pane)
        panel = pane.scene_class_panel
        form = pane.geometry_form
        assert panel is not None
        assert form is not None
        parent = panel.parentWidget()
        assert parent is not None
        children = parent.findChildren(type(panel)) + parent.findChildren(type(form))
        assert children  # both live under the same Inputs tab
        layout = parent.layout()
        assert layout is not None
        order = [layout.itemAt(i).widget() for i in range(layout.count())]
        assert order.index(panel) < order.index(form)

    def test_populate_fills_the_chip_from_the_live_result(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """After a real evaluation the chip shows the stage's published class verbatim."""
        window = _load_window(qtbot)
        window.central_canvas.select_stage("geometry")
        result = window._last_result  # noqa: SLF001
        assert result is not None
        published = result.stage_outputs["geometry"]["scene_class"]
        panel = window.central_canvas.stage_center.pane("geometry").scene_class_panel
        assert panel is not None
        assert panel.derived_class == published
        assert published in panel.chip_text()
        assert panel.relevance_labels() == off_metric_labels(published)

    def test_asserted_mismatch_tints_the_card_and_navigates(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """A wrong assertion fails the evaluate; the card tints in place and clears.

        The LEO example derives a space observer; asserting ``ground_to_ground`` makes
        the stage raise its ``GeometrySpecificationError`` (the CU-093 redundant-entry
        pattern). The window routes it to this card and shows the Geometry screen; the
        actionable dialog is captured so it does not block the event loop.
        """
        window = _load_window(qtbot)
        shown: list[aed.ActionableErrorDialog] = []
        monkeypatch.setattr(aed.ActionableErrorDialog, "exec", lambda self: shown.append(self) or 0)

        window.sensor.set(SCENE_CLASS_PARAM, "ground_to_ground")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(SCENE_CLASS_PARAM)

        assert len(shown) == 1  # the stage's actionable error surfaced
        panel = window.central_canvas.stage_center.pane("geometry").scene_class_panel
        assert panel is not None
        assert panel.is_conflicting()
        assert "ground_to_ground" in panel.conflict_text()
        assert window.central_canvas.selected_stage == "geometry"

        # Withdraw the assertion: a clean run clears the tint (one lifecycle with the
        # mode-selector highlight).
        window.sensor.reset(SCENE_CLASS_PARAM)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(SCENE_CLASS_PARAM)
        assert not panel.is_conflicting()
        assert panel.conflict_text() == ""
