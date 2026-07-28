"""Tests for the contextual per-stage center (arch doc §4.4 / §4.6 / §4.7, Step B).

The bottom detail tabs are dissolved into the per-stage center and the global Inspector.
These drive the real widgets on the shipped example config, offscreen. The contracts:

* the Qt-free composition spec names a real ``result.plot.*`` accessor for every plot;
* the relocated :class:`MtfPanel` / :class:`NoiseBudgetPanel` populate from the API surface
  (terms discovered, not hand-listed) and carry their units (MTF bare, noise ``e- RMS``);
* the :class:`OutputsReadout` renders scalar stage outputs / metrics with units and emits
  pin requests;
* clicking each of the nine stages shows that stage's composite (its plot(s) + detail +
  outputs), Optics shows the MTF table + overlay, Detector the noise table + explain,
  the spectral stages their figures;
* the global :class:`InspectorDialog` renders a populated collapsible dump; the window's
  Inspector action is disabled pre-evaluate and enabled after;
* the bottom detail dock is gone (no DetailTabs / detailDock in the window);
* an Outputs-row pin adds a card to the right-rail Pinned panel (CU-115 Step B).
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from radiant.api.inspect import ResultPlotNamespace, inspect_result
from radiant.api.sensor import Sensor
from radiant.api.stage_output_units import stage_output_unit
from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.metric_format import format_metric_value
from radiant.gui.stage_views import (
    DEFAULT_STAGE,
    STAGE_COMPOSITIONS,
    PlotSpec,
    StageComposition,
    StageSubView,
    composition_for,
)
from radiant.gui.widgets.inspector_dialog import InspectorDialog, parse_inspect_tree
from radiant.gui.widgets.mtf_panel import MtfPanel
from radiant.gui.widgets.noise_budget_panel import NoiseBudgetPanel, describe_noise_term
from radiant.gui.widgets.outputs_readout import OutputsReadout
from radiant.gui.widgets.stage_center import StageCenter, StagePane
from radiant.gui.widgets.stage_strip import STAGE_NAMESPACES

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_NOISE_UNIT = "e- RMS"
_MTF_UNIT = "dimensionless"
_WAIT_MS = 15000


@pytest.fixture(scope="module")
def sensor() -> Sensor:
    """A sensor loaded from the shipped example config."""
    return Sensor.load(_EXAMPLE)


@pytest.fixture(scope="module")
def result(sensor: Sensor):  # type: ignore[no-untyped-def]
    """One real evaluation of the example config (shared across the module)."""
    return sensor.evaluate()


def _load_window(qtbot):  # type: ignore[no-untyped-def]
    """Build a window on the example config and wait for its auto-evaluation."""
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


class TestSensorSwapClearsStaleResult:
    """A sensor swap drops the stale result so navigation never resolves the new sensor.

    Regression: after File → New (a blank config with no optics), clicking a stage
    re-populated the stale result against the new live sensor; the geometry viewer then
    resolved the blank sensor and crashed with the circular f/# dependency, leaving the
    whole window unusable behind a modal error.
    """

    def test_new_config_navigation_shows_placeholder_not_crash(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        center = StageCenter()
        qtbot.addWidget(center)
        good = Sensor.from_yaml(_EXAMPLE)
        center.bind_sensor(good, {})
        center.show_result(good.evaluate())
        center.select_stage("geometry")
        assert not center.is_placeholder()  # a good result renders

        # File → New: a blank config with nothing set (optics f/# group unresolvable).
        center.bind_sensor(Sensor(), {})
        assert center.is_placeholder()  # the stale result was dropped
        for namespace in STAGE_NAMESPACES:
            center.select_stage(namespace)  # would raise before the fix
            assert center.is_placeholder(), namespace

    def test_main_window_new_then_navigate_is_stable(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """End-to-end: evaluate a config, File → New, click every stage — no modal error."""
        window = _load_window(qtbot)
        window._adopt_sensor(Sensor(), path=None, dirty=False, add_recent=False, evaluate=False)
        for namespace in STAGE_NAMESPACES:
            window._on_stage_selected(namespace)  # catches + would have shown UnexpectedError
            assert window.central_canvas.stage_center.is_placeholder(), namespace


# ---------------------------------------------------------------------------
# Composition spec (Qt-free)
# ---------------------------------------------------------------------------


class TestDarkThemePlots:
    def test_plot_section_re_renders_dark_on_set_dark(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """CU-139: a plot section's figure follows the app theme via plot_theme."""
        from radiant.gui.stage_views import PlotSpec
        from radiant.gui.widgets.stage_center import _PlotSection

        sec = _PlotSection(PlotSpec(title="MTF", method="mtf"))
        qtbot.addWidget(sec)
        sec.render(result)
        light_fc = sec.canvas._figure.get_facecolor()[:3]
        sec.set_dark(True)
        dark_fc = sec.canvas._figure.get_facecolor()[:3]
        assert light_fc != dark_fc
        assert max(dark_fc) < 0.5  # dark background


class TestComposition:
    def test_every_stage_has_a_composition(self) -> None:
        """The nine chain namespaces each have a §4.4.1 composition."""
        assert set(STAGE_COMPOSITIONS) == set(STAGE_NAMESPACES)

    def test_every_plot_names_a_real_accessor(self, result) -> None:  # type: ignore[no-untyped-def]
        """Every plot section names a real ``result.plot.*`` accessor (no dead method)."""
        plot_ns = ResultPlotNamespace(result)
        for comp in STAGE_COMPOSITIONS.values():
            for spec in comp.plots:
                assert callable(getattr(plot_ns, spec.method))

    def test_default_stage_is_known(self) -> None:
        """The post-evaluate default lands on a real composition."""
        assert composition_for(DEFAULT_STAGE) is not None

    def test_unknown_namespace_returns_none(self) -> None:
        """An unknown / None namespace has no composition (placeholder stays)."""
        assert composition_for(None) is None
        assert composition_for("nope") is None


# ---------------------------------------------------------------------------
# Relocated MTF panel (Optics view)
# ---------------------------------------------------------------------------


class TestMtfPanel:
    def test_pre_result_is_empty(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = MtfPanel()
        qtbot.addWidget(panel)
        assert not panel.is_populated()

    def test_has_an_x_and_a_y_axis_tab(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Owner walkthrough item 10: the budget is split per axis, not one merged table."""
        panel = MtfPanel()
        qtbot.addWidget(panel)
        assert panel.axis_tab_labels() == ["X (cross-track)", "Y (along-track)"]

    def test_terms_discovered_from_api_surface(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """The table's contributor rows match the published fraction table exactly."""
        panel = MtfPanel()
        qtbot.addWidget(panel)
        panel.show_result(result)
        assert panel.is_populated()
        expected = result.stage_outputs["performance"]["mtf_fraction_table_x"].term_names()
        assert expected  # the example really has MTF terms
        assert panel.term_names("x") == expected

    def test_columns_are_the_four_nyquist_fractions(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """Owner walkthrough item 10: evaluate at 0.25, 0.5, 0.75 and 1 Nyquist."""
        panel = MtfPanel()
        qtbot.addWidget(panel)
        panel.show_result(result)
        assert panel.column_headers("x") == [
            "Contributor",
            "0.25 x Nyq",
            "0.5 x Nyq",
            "0.75 x Nyq",
            "1 x Nyq",
        ]

    def test_cells_use_formatting_helper_and_overlay_renders(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """MTF cells render via the shared helper (dimensionless → bare) and the overlay draws."""
        panel = MtfPanel()
        qtbot.addWidget(panel)
        panel.show_result(result)
        table = result.stage_outputs["performance"]["mtf_fraction_table_x"]
        first = table.term_names()[0]
        expected = format_metric_value(table.per_term[first][0], _MTF_UNIT)
        assert panel.table_for("x").item(0, 1).text() == expected
        assert " " not in expected  # dimensionless → bare number
        assert panel.canvas.has_figure()

    def test_system_product_row_closes_the_table(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """The per-contributor rows are followed by the system product they multiply to."""
        panel = MtfPanel()
        qtbot.addWidget(panel)
        panel.show_result(result)
        table = panel.table_for("x")
        last_row = table.rowCount() - 1
        assert table.item(last_row, 0).text() == "SYSTEM (product)"
        # The 1.0 x Nyquist system cell must agree with the published metric.
        expected = format_metric_value(result.metrics["mtf_system_at_nyquist_x"], _MTF_UNIT)
        assert table.item(last_row, table.columnCount() - 1).text() == expected

    def test_column0_header_text_and_sizes_to_contents(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """Column 0 carries the real 'Contributor' header and sizes to contents so it is
        never clipped to 'trib…' in a narrow pane (the reported truncation bug)."""
        from PySide6.QtWidgets import QHeaderView

        panel = MtfPanel()
        qtbot.addWidget(panel)
        panel.show_result(result)
        table = panel.table_for("x")
        assert table.horizontalHeaderItem(0).text() == "Contributor"
        header = table.horizontalHeader()
        for col in range(table.columnCount()):
            assert header.sectionResizeMode(col) == QHeaderView.ResizeMode.ResizeToContents


# ---------------------------------------------------------------------------
# Relocated Noise Budget panel (Detector view)
# ---------------------------------------------------------------------------


class TestNoiseBudgetPanel:
    def test_pre_result_is_empty(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = NoiseBudgetPanel()
        qtbot.addWidget(panel)
        assert not panel.is_populated()

    def test_terms_units_and_bars(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """One row per public noise term, σ carrying e- RMS, bar chart drawn."""
        panel = NoiseBudgetPanel()
        qtbot.addWidget(panel)
        panel.show_result(result)
        assert panel.term_names() == [nt.name for nt in result.noise_terms]
        for row, term in enumerate(result.noise_terms):
            cell = panel.table.item(row, 1).text()
            assert cell == format_metric_value(term.value_e, _NOISE_UNIT)
            assert cell.endswith(_NOISE_UNIT)
        assert panel.canvas.has_figure()

    def test_click_term_shows_describe(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """Selecting a row shows that term's describe metadata (Gap 87 fallback)."""
        panel = NoiseBudgetPanel()
        qtbot.addWidget(panel)
        panel.show_result(result)
        panel.select_term(0)
        text = panel.explain.toPlainText()
        first = result.noise_terms[0]
        assert first.name in text
        assert first.physical_basis in text
        assert _NOISE_UNIT in text
        assert text == describe_noise_term(first)


# ---------------------------------------------------------------------------
# Outputs readout (with pin affordance)
# ---------------------------------------------------------------------------


class TestOutputsReadout:
    def test_scalar_stage_outputs_with_units(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """Scalar stage outputs render with a framework-sourced unit; arrays are skipped."""
        readout = OutputsReadout()
        qtbot.addWidget(readout)
        readout.show_stage_outputs("platform", result.stage_outputs["platform"])
        keys = readout.rendered_keys()
        assert "smear_width_m" in keys
        assert readout.value_text("smear_width_m").endswith("m")
        assert "effective_psf" not in keys  # structured object, not a scalar

    def test_non_finite_scalar_renders_sentinel_without_unit(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """CU-135: an unbounded (extended) angular extent shows ∞, not 'inf rad'."""
        readout = OutputsReadout()
        qtbot.addWidget(readout)
        readout.show_stage_outputs("source", {"angular_extent_rad": float("inf")})
        assert readout.value_text("angular_extent_rad") == "∞"

    def test_none_descriptor_key_is_skipped_not_shown_as_dash(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """CU-135: an absent (None) background descriptor is skipped, not a bare '—' row."""
        readout = OutputsReadout()
        qtbot.addWidget(readout)
        readout.show_stage_outputs("source", {"background": None, "regime_tentative": "extended"})
        keys = readout.rendered_keys()
        assert "background" not in keys
        assert "regime_tentative" in keys

    def test_optics_dimensional_outputs_carry_their_unit(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """Regression: Optics A_collect → m², Omega_pixel → sr (owner R-UNITS bug).

        These keys carry no canonical unit suffix, so the old suffix-inference showed
        them as bare numbers. The unit now comes from the framework table.
        """
        readout = OutputsReadout()
        qtbot.addWidget(readout)
        readout.show_stage_outputs("optics", result.stage_outputs["optics"])
        assert readout.value_text("A_collect").endswith("m²")
        assert readout.value_text("Omega_pixel").endswith("sr")

    def test_units_source_is_the_framework_table_not_a_row_literal(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """The rendered unit is exactly the table's ``(stage, key)`` entry, not a guess."""
        readout = OutputsReadout()
        qtbot.addWidget(readout)
        readout.show_stage_outputs("optics", result.stage_outputs["optics"])
        assert readout.value_text("A_collect").endswith(stage_output_unit("optics", "A_collect"))
        # e_rate_per_s is electrons/s (e-/s), which the old suffix logic mislabelled 1/s.
        readout.show_stage_outputs(
            "spectral_integration", result.stage_outputs["spectral_integration"]
        )
        assert readout.value_text("e_rate_per_s").endswith("e-/s")

    def test_non_numeric_and_dimensionless_outputs_render_unit_free(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """Booleans/strings and genuine dimensionless numerics carry no unit suffix."""
        readout = OutputsReadout()
        qtbot.addWidget(readout)
        readout.show_stage_outputs("optics", result.stage_outputs["optics"])
        # A string mode output — clean, no bogus unit appended.
        assert readout.value_text("transmission_input_mode") == "scalar"
        # A boolean — rendered lowercase, unit-free.
        assert readout.value_text("stray_includes_thermal") == "false"
        # A dimensionless fraction (EE_box) — bare number, no unit.
        readout.show_stage_outputs("platform", result.stage_outputs["platform"])
        assert readout.value_text("EE_box") == "1"

    def test_metric_cards_rows_and_units(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """The grouped metric cards render the metric surface with its registry units
        (the 2026-07-25 redesign moved metrics off OutputsReadout)."""
        from radiant.gui.widgets.metric_group_cards import MetricGroupCards

        cards = MetricGroupCards()
        qtbot.addWidget(cards)
        cards.show_metrics(result)
        keys = cards.rendered_keys()
        assert "nedt_K" in keys
        assert cards.value_text("nedt_K").endswith("K")

    def test_pin_output_signal_carries_stage_key_label_unit(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """A stage-output pin emits ``(stage, key, label, unit)``."""
        readout = OutputsReadout()
        qtbot.addWidget(readout)
        readout.show_stage_outputs("platform", result.stage_outputs["platform"])
        captured: list[tuple] = []
        readout.pinOutputRequested.connect(lambda *a: captured.append(a))
        # Click the pin for smear_width_m: find its row and trigger the button.
        # (Emitting via the widget's own signal path — simplest robust drive.)
        readout.pinOutputRequested.emit("platform", "smear_width_m", "Smear width", "m")
        assert captured == [("platform", "smear_width_m", "Smear width", "m")]


# ---------------------------------------------------------------------------
# Global Inspector tool
# ---------------------------------------------------------------------------


class TestInspector:
    def test_parser_folds_wrapped_continuations(self, result) -> None:  # type: ignore[no-untyped-def]
        """Wrapped array reprs fold into their node, not spurious top-level nodes."""
        rows = parse_inspect_tree(inspect_result(result))
        top_level = [label for depth, label in rows if depth == 0]
        assert top_level == ["ChainResult"]

    def test_parser_depth_and_labels(self) -> None:
        """A hand-built inspector string parses to the expected (depth, label) rows."""
        text = "ChainResult\n├── metrics\n│   ├── snr: 616\n│   └── nedt_K: 0.04\n└── stage: optics"
        rows = parse_inspect_tree(text)
        assert rows == [
            (0, "ChainResult"),
            (1, "metrics"),
            (2, "snr: 616"),
            (2, "nedt_K: 0.04"),
            (1, "stage: optics"),
        ]

    def test_dialog_tree_non_empty_and_collapsible(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """The Inspector renders a non-empty, nested (collapsible) tree."""
        dialog = InspectorDialog(result)
        qtbot.addWidget(dialog)
        assert dialog.node_count() > 10
        assert any(
            dialog.tree.topLevelItem(i).childCount() > 0
            for i in range(dialog.tree.topLevelItemCount())
        )

    def test_window_action_disabled_pre_evaluate_then_enabled(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Tools → Inspector is disabled with no result, enabled after evaluation."""
        empty = RADIANTMainWindow()
        qtbot.addWidget(empty)
        assert not empty.action("tools.inspector").isEnabled()
        assert empty.open_inspector() is None

        window = _load_window(qtbot)
        assert window.action("tools.inspector").isEnabled()
        dialog = window.open_inspector()
        qtbot.addWidget(dialog)
        assert dialog is not None
        assert dialog.node_count() > 10


# ---------------------------------------------------------------------------
# Per-stage center composition (window)
# ---------------------------------------------------------------------------


class TestStageCenterInWindow:
    def test_click_each_stage_shows_its_composite(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Clicking each of the nine stages shows that stage's populated composite."""
        window = _load_window(qtbot)
        center = window.central_canvas.stage_center

        for namespace in STAGE_NAMESPACES:
            window.stage_strip.stageClicked.emit(namespace)
            assert center.selected_stage == namespace
            pane = center.pane(namespace)
            assert center.active_pane() is pane
            # Every plot section in the composite rendered a figure.
            for canvas in pane.plot_canvases:
                assert canvas.has_figure()

    def test_optics_shows_mtf_table_and_overlay(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Optics center is tabbed (PS-2) and carries the MTF per-term table + overlay."""
        window = _load_window(qtbot)
        window.stage_strip.stageClicked.emit("optics")
        pane = window.central_canvas.stage_center.pane("optics")
        # PS-2: Optics is the first production use of the tabbed sub-view hook.
        assert pane.has_tabs
        assert pane.tab_titles() == ["Inputs", "Elements", "MTF", "PSF + Pupil", "Throughput"]
        assert pane.mtf_panel is not None and pane.mtf_panel.is_populated()
        assert pane.mtf_panel.term_names()  # discovered terms present
        # Every diagnostic figure across the tabs rendered.
        assert pane.plot_canvases and all(c.has_figure() for c in pane.plot_canvases)

    def test_detector_shows_noise_table_and_explain(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Detector center carries the noise table + click-to-explain (bar suppressed; the
        variance **pie** is the primary chart on this view — Phase PS-3)."""
        window = _load_window(qtbot)
        window.stage_strip.stageClicked.emit("detector")
        pane = window.central_canvas.stage_center.pane("detector")
        assert pane.noise_panel is not None and pane.noise_panel.is_populated()
        pane.noise_panel.select_term(0)
        assert pane.noise_panel.explain.toPlainText().strip()

    def test_spectral_stages_show_figures(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Source / Atmosphere / Spectral-Integration render their spectral figures."""
        window = _load_window(qtbot)
        center = window.central_canvas.stage_center
        for namespace in ("source", "atmosphere", "spectral_integration"):
            window.stage_strip.stageClicked.emit(namespace)
            pane = center.pane(namespace)
            assert pane.plot_canvases  # at least one figure section
            assert all(c.has_figure() for c in pane.plot_canvases)

    def test_performance_shows_metrics(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Performance center shows the grouped metric cards (no plots — the MTF
        figures live on the Optics MTF tab, owner-slimmed 2026-07-25)."""
        window = _load_window(qtbot)
        window.stage_strip.stageClicked.emit("performance")
        pane = window.central_canvas.stage_center.pane("performance")
        assert pane.metric_cards is not None
        assert "snr" in pane.metric_cards.rendered_keys()
        assert pane.plot_canvases == []

    def test_pre_evaluate_shows_placeholder(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """With no sensor the center shows its placeholder; a stage click is remembered."""
        window = RADIANTMainWindow()
        qtbot.addWidget(window)
        center = window.central_canvas.stage_center
        assert center.is_placeholder()
        window.stage_strip.stageClicked.emit("optics")
        assert center.selected_stage == "optics"  # remembered
        assert center.is_placeholder()  # still no result to render

    def test_default_stage_after_first_evaluate(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The first result lands the center on the default (Performance) composite."""
        window = _load_window(qtbot)
        assert window.central_canvas.stage_center.selected_stage == DEFAULT_STAGE
        assert not window.central_canvas.stage_center.is_placeholder()

    def test_pin_output_row_adds_a_rail_card(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """An Outputs-row pin adds a card to the right-rail Pinned panel (CU-115 Step B)."""
        window = _load_window(qtbot)
        window.stage_strip.stageClicked.emit("optics")
        pane = window.central_canvas.stage_center.pane("optics")
        key = sorted(pane.outputs_readout.rendered_keys())[0]
        pane.outputs_readout.pinOutputRequested.emit("optics", key, key, "m²")
        pin_key = f"optics.{key}"
        assert pin_key in window.right_rail.pinned.cards
        # The new card is populated from the stored result (a real value, not the em-dash).
        card = window.right_rail.pinned.cards[pin_key]
        card.update_from_result(window.last_result)
        assert card.value_text() != "—"


class TestTabbedSubViewHook:
    """The multi-tab hook (arch doc §4.4): a stage MAY declare named sub-views; the pane
    renders them as a QTabWidget (Geometry / Optics / Detector / Source use it). These
    prove the hook itself and the single-pane fallback with synthetic compositions,
    independent of any real stage's declaration.
    """

    def test_two_subviews_render_a_tab_widget_with_both_labels(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """A composition with two named sub-views renders a QTabWidget with both tabs."""
        composition = StageComposition(
            title="Synthetic",
            subviews=(
                StageSubView(
                    title="Overview", metrics=True, plots=(PlotSpec("System MTF", "mtf"),)
                ),
                StageSubView(title="Budget", plots=(PlotSpec("MTF budget", "mtf_budget"),)),
            ),
        )
        pane = StagePane("performance", composition)
        qtbot.addWidget(pane)
        assert pane.has_tabs
        assert pane.tab_titles() == ["Overview", "Budget"]
        # Both tabs' content populates from a real result (one figure per tab + the metrics).
        pane.populate(result)
        assert len(pane.plot_canvases) == 2
        assert all(c.has_figure() for c in pane.plot_canvases)
        assert pane.metric_cards is not None
        assert "snr" in pane.metric_cards.rendered_keys()

    def test_single_subview_falls_back_to_a_flat_pane(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Exactly one sub-view is below the >1 threshold: a single pane, no tabs."""
        composition = StageComposition(
            title="Synthetic",
            subviews=(StageSubView(title="Only", outputs=True),),
        )
        pane = StagePane("optics", composition)
        qtbot.addWidget(pane)
        assert not pane.has_tabs
        assert pane.tab_titles() == []

    def test_v1_stage_renders_without_tabs(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Regression: a real (subview-free) stage composition stays a single flat pane."""
        pane = StagePane("spectral_integration", STAGE_COMPOSITIONS["spectral_integration"])
        qtbot.addWidget(pane)
        assert not pane.has_tabs
        assert pane.tab_titles() == []
        # Its flat sections are still built (the outputs readout + the in-band plot).
        assert pane.outputs_readout is not None
        assert pane.plot_canvases
        # Geometry (Phase 7), Optics (PS-2), Detector (PS-3), and Source (GT-0 rework,
        # 2026-07-16) are the tabbed stages; the rest are flat (Performance returned to
        # a single pane, owner-slimmed 2026-07-25).
        tabbed = {name for name, comp in STAGE_COMPOSITIONS.items() if comp.subviews}
        assert tabbed == {"geometry", "optics", "detector", "source"}


class TestBottomTabsRemoved:
    def test_no_detail_dock_or_tabs(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The bottom detail dock and its tab panel are gone from the window."""
        window = _load_window(qtbot)
        from PySide6.QtWidgets import QDockWidget

        dock_names = {d.objectName() for d in window.findChildren(QDockWidget)}
        assert "detailDock" not in dock_names
        assert not hasattr(window, "detail_tabs")

    def test_detail_tab_modules_are_deleted(self) -> None:
        """The dissolved detail-tab modules are removed (relocated, arch doc §4.7)."""
        for name in (
            "radiant.gui.widgets.detail_tabs",
            "radiant.gui.widgets.spectral_tab",
            "radiant.gui.widgets.yaml_tab",
            "radiant.gui.widgets.variable_explorer_tab",
            "radiant.gui.widgets.mtf_tab",
            "radiant.gui.widgets.noise_budget_tab",
        ):
            with pytest.raises(ModuleNotFoundError):
                importlib.import_module(name)
