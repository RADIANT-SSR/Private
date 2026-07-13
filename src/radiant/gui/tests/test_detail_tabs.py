"""Tests for the five v1 detail tabs (GUI plan Phase 4 Task B, arch doc §4.5).

Each tab is driven from a real evaluation of the shipped example config, offscreen. The
contracts asserted:

* every tab starts in its themed evaluate-first state and populates on ``show_result``;
* the MTF and Noise tables discover their terms **from the API surface** (generated, not
  hand-listed) and render each numeric cell through the shared formatting helper, so every
  value carries its unit (MTF is dimensionless → bare number; noise → ``e- RMS``);
* the Spectral selector switches between the three ``result.plot`` spectral figures;
* the Variables tree is non-empty, collapsible, and folds the inspector's wrapped array
  reprs (CU-113) instead of dumping them as top-level nodes;
* the YAML text round-trips through the public loader and Export writes a loadable file;
* the DetailTabs container populates all five on a real window evaluation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from radiant.api.inspect import inspect_result
from radiant.api.sensor import Sensor
from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.metric_format import format_metric_value
from radiant.gui.themes import apply_theme
from radiant.gui.widgets.detail_tabs import TAB_LABELS, DetailTabs
from radiant.gui.widgets.mtf_tab import MtfTab, _bases
from radiant.gui.widgets.noise_budget_tab import NoiseBudgetTab, describe_noise_term
from radiant.gui.widgets.spectral_tab import SpectralTab
from radiant.gui.widgets.variable_explorer_tab import VariableExplorerTab, parse_inspect_tree
from radiant.gui.widgets.yaml_tab import YamlTab
from radiant.gui.yaml_format import dotpath_provenance, line_provenance, serialize_yaml

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


# ---------------------------------------------------------------------------
# Spectral tab
# ---------------------------------------------------------------------------


class TestSpectralTab:
    def test_pre_result_is_empty(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The tab shows its evaluate-first state before any result."""
        tab = SpectralTab()
        qtbot.addWidget(tab)
        assert not tab.is_populated()

    def test_selector_lists_three_frames(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The frame selector offers source / atmosphere / in-band (arch doc §4.5)."""
        tab = SpectralTab()
        qtbot.addWidget(tab)
        labels = [tab.selector.itemText(i) for i in range(tab.selector.count())]
        assert labels == ["Source", "Atmosphere", "In-band"]

    def test_selector_switches_figures(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """Populating renders a figure; switching the selector renders the next one."""
        tab = SpectralTab()
        qtbot.addWidget(tab)
        tab.show_result(result)
        assert tab.is_populated()
        assert tab.current_accessor() == "spectral_source"
        assert tab.canvas.has_figure()

        tab.selector.setCurrentIndex(1)
        assert tab.current_accessor() == "spectral_atmosphere"
        assert tab.canvas.has_figure()

        tab.selector.setCurrentIndex(2)
        assert tab.current_accessor() == "spectral_inband"
        assert tab.canvas.has_figure()


# ---------------------------------------------------------------------------
# MTF tab
# ---------------------------------------------------------------------------


class TestMtfTab:
    def test_pre_result_is_empty(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        tab = MtfTab()
        qtbot.addWidget(tab)
        assert not tab.is_populated()

    def test_terms_discovered_from_api_surface(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """The table's contributor rows match the budget surface exactly (generated)."""
        tab = MtfTab()
        qtbot.addWidget(tab)
        tab.show_result(result)
        assert tab.is_populated()

        budget = result.stage_outputs["performance"]["mtf_budget"]
        expected = _bases(budget.per_term_at_nyquist)
        assert expected  # the example really has MTF terms
        assert tab.term_names() == expected

    def test_mtf_cells_use_formatting_helper(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """Every MTF@Nyquist cell renders via the shared helper (dimensionless → bare)."""
        tab = MtfTab()
        qtbot.addWidget(tab)
        tab.show_result(result)

        budget = result.stage_outputs["performance"]["mtf_budget"]
        per_term = budget.per_term_at_nyquist
        for row, base in enumerate(_bases(per_term)):
            value_x = per_term.get(f"{base}_x")
            assert value_x is not None
            expected = format_metric_value(value_x, _MTF_UNIT)
            assert tab.table.item(row, 1).text() == expected
            # A dimensionless value renders as a bare number (no unit suffix).
            assert " " not in expected

    def test_overlay_figure_renders(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        tab = MtfTab()
        qtbot.addWidget(tab)
        tab.show_result(result)
        assert tab.canvas.has_figure()


# ---------------------------------------------------------------------------
# Noise Budget tab
# ---------------------------------------------------------------------------


class TestNoiseBudgetTab:
    def test_pre_result_is_empty(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        tab = NoiseBudgetTab()
        qtbot.addWidget(tab)
        assert not tab.is_populated()

    def test_term_count_matches_result(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """One row per public noise term (generated from ``result.noise_terms``)."""
        tab = NoiseBudgetTab()
        qtbot.addWidget(tab)
        tab.show_result(result)
        assert tab.is_populated()
        assert tab.term_names() == [nt.name for nt in result.noise_terms]

    def test_sigma_cells_carry_units(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """Every σ cell carries the e- RMS unit via the shared formatting helper."""
        tab = NoiseBudgetTab()
        qtbot.addWidget(tab)
        tab.show_result(result)
        for row, term in enumerate(result.noise_terms):
            expected = format_metric_value(term.value_e, _NOISE_UNIT)
            cell = tab.table.item(row, 1).text()
            assert cell == expected
            assert cell.endswith(_NOISE_UNIT)

    def test_click_term_shows_describe(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """Selecting a row shows that term's describe metadata (Gap 87 fallback)."""
        tab = NoiseBudgetTab()
        qtbot.addWidget(tab)
        tab.show_result(result)
        tab.select_term(0)
        text = tab.explain.toPlainText()
        first = result.noise_terms[0]
        assert first.name in text
        assert first.physical_basis in text
        assert _NOISE_UNIT in text
        assert text == describe_noise_term(first)

    def test_bar_chart_renders(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        tab = NoiseBudgetTab()
        qtbot.addWidget(tab)
        tab.show_result(result)
        assert tab.canvas.has_figure()


# ---------------------------------------------------------------------------
# Variable Explorer tab
# ---------------------------------------------------------------------------


class TestVariableExplorerTab:
    def test_pre_result_is_empty(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        tab = VariableExplorerTab()
        qtbot.addWidget(tab)
        assert not tab.is_populated()

    def test_tree_non_empty_and_collapsible(self, qtbot, result) -> None:  # type: ignore[no-untyped-def]
        """The tree is non-empty and has nested (collapsible) structure."""
        tab = VariableExplorerTab()
        qtbot.addWidget(tab)
        tab.show_result(result)
        assert tab.is_populated()
        assert tab.node_count() > 10
        root = tab.tree.topLevelItem(0)
        assert root is not None
        # At least one top-level node has children — i.e. the tree is collapsible.
        assert any(
            tab.tree.topLevelItem(i).childCount() > 0
            for i in range(tab.tree.topLevelItemCount())
        )

    def test_parser_folds_wrapped_continuations(self, result) -> None:  # type: ignore[no-untyped-def]
        """Wrapped array reprs fold into their node, not spurious top-level nodes."""
        rows = parse_inspect_tree(inspect_result(result))
        top_level = [label for depth, label in rows if depth == 0]
        # Exactly one true root — the array continuation lines are folded away.
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


# ---------------------------------------------------------------------------
# YAML tab
# ---------------------------------------------------------------------------


class TestYamlTab:
    def test_pre_result_is_empty(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        tab = YamlTab()
        qtbot.addWidget(tab)
        assert not tab.is_populated()

    def test_shows_serialized_config(self, qtbot, sensor) -> None:  # type: ignore[no-untyped-def]
        """Populating shows the sensor's serialized YAML text."""
        tab = YamlTab()
        qtbot.addWidget(tab)
        tab.show_sensor(sensor)
        assert tab.is_populated()
        text = tab.yaml_text()
        assert text.strip()
        assert text == serialize_yaml(sensor)

    def test_text_round_trips_through_loader(self, qtbot, sensor, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """The displayed YAML text loads back through the public loader."""
        tab = YamlTab()
        qtbot.addWidget(tab)
        tab.show_sensor(sensor)
        path = tmp_path / "roundtrip.yaml"
        path.write_text(tab.yaml_text(), encoding="utf-8")
        reloaded = Sensor.load(path)
        assert reloaded is not None

    def test_export_writes_loadable_file(self, qtbot, sensor, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Export writes a YAML file that the public loader can reopen."""
        tab = YamlTab()
        qtbot.addWidget(tab)
        tab.show_sensor(sensor)
        out = tmp_path / "exported.yaml"
        tab.export_to(str(out))
        assert out.exists()
        assert Sensor.load(out) is not None

    def test_provenance_data_path(self, sensor) -> None:  # type: ignore[no-untyped-def]
        """At least one YAML line resolves to a provenance token (colouring source)."""
        text = serialize_yaml(sensor)
        tokens = dotpath_provenance(sensor)
        assert tokens  # some parameters resolve to a provenance
        line_tokens = line_provenance(text, tokens)
        assert any(token is not None for _line, token in line_tokens)


# ---------------------------------------------------------------------------
# DetailTabs container + window wiring
# ---------------------------------------------------------------------------


class TestDetailTabsContainer:
    def test_five_tabs_in_order(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        tabs = DetailTabs()
        qtbot.addWidget(tabs)
        assert tabs.tab_labels() == list(TAB_LABELS)
        assert tabs.tab_labels() == ["Spectral", "MTF", "Noise Budget", "Variables", "YAML"]

    def test_show_result_populates_all_five(self, qtbot, result, sensor) -> None:  # type: ignore[no-untyped-def]
        tabs = DetailTabs()
        qtbot.addWidget(tabs)
        tabs.show_result(result, sensor)
        assert tabs.spectral_tab.is_populated()
        assert tabs.mtf_tab.is_populated()
        assert tabs.noise_tab.is_populated()
        assert tabs.variables_tab.is_populated()
        assert tabs.yaml_tab.is_populated()

    def test_window_populates_detail_tabs_on_evaluate(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A real window evaluation refreshes every detail tab (main-window wiring)."""
        app = _app()
        apply_theme(app)
        window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
        qtbot.addWidget(window)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            pass
        tabs = window.detail_tabs
        assert tabs.spectral_tab.is_populated()
        assert tabs.mtf_tab.is_populated()
        assert tabs.noise_tab.is_populated()
        assert tabs.variables_tab.is_populated()
        assert tabs.yaml_tab.is_populated()


def _app():  # type: ignore[no-untyped-def]
    """The live QApplication (qtbot guarantees one exists)."""
    from PySide6.QtWidgets import QApplication

    instance = QApplication.instance()
    assert instance is not None
    return instance
