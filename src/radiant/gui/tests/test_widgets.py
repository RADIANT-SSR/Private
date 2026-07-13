"""Contract tests for the Phase-1 shell chrome widgets (GUI plan Phase 1 punch-list).

These assert the *static* content the owner judges the design system against renders:
the 9-stage strip in chain order with stale dots, the five KPI badges awaiting
evaluation, the disabled parameter filter over an empty tree, the plot placeholder,
and the five detail tabs. Behaviour (clicks, evaluation) is Phase 3/4 and not tested
here — these widgets are deliberately behaviour-free in Phase 1.
"""

from __future__ import annotations

from radiant.gui.metric_format import format_metric_value
from radiant.gui.widgets.detail_tabs import TAB_LABELS, DetailTabs
from radiant.gui.widgets.health_dot import VALID_STATUSES, HealthDot
from radiant.gui.widgets.kpi_badge_row import METRIC_KEYS, KpiBadgeRow
from radiant.gui.widgets.parameter_panel import ParameterPanel
from radiant.gui.widgets.plot_placeholder import PlotPlaceholder
from radiant.gui.widgets.stage_strip import STAGE_TITLES, StageStrip


class TestStageStrip:
    def test_nine_stages_in_chain_order(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The strip renders the 9 stages, geometry-first, in ADR-0006 order."""
        strip = StageStrip()
        qtbot.addWidget(strip)
        titles = [chip.stage_title for chip in strip.chips]
        assert titles == [
            "Geometry",
            "Source",
            "Atmosphere",
            "Optics",
            "Platform",
            "Spectral Int.",
            "Detector",
            "Readout",
            "Performance",
        ]
        assert titles == list(STAGE_TITLES)

    def test_every_stage_dot_is_stale(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Nothing is evaluated in Phase 1, so every health dot reads 'stale' (§8.4)."""
        strip = StageStrip()
        qtbot.addWidget(strip)
        assert len(strip.chips) == 9
        for chip in strip.chips:
            assert isinstance(chip.dot, HealthDot)
            assert chip.dot.status == "stale"


class TestHealthDot:
    def test_default_is_stale(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A dot defaults to the stale (not-yet-evaluated) state."""
        dot = HealthDot()
        qtbot.addWidget(dot)
        assert dot.status == "stale"
        assert dot.property("status") == "stale"

    def test_set_status_valid(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Setting a valid status updates the property (Phase 4 uses this)."""
        dot = HealthDot()
        qtbot.addWidget(dot)
        for status in VALID_STATUSES:
            dot.set_status(status)
            assert dot.status == status
            assert dot.property("status") == status

    def test_set_status_invalid_raises(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """An unknown status raises rather than rendering an unstyled dot (Rule 17)."""
        dot = HealthDot()
        qtbot.addWidget(dot)
        try:
            dot.set_status("purple")
        except ValueError:
            pass
        else:  # pragma: no cover - defensive
            raise AssertionError("expected ValueError for an unknown status")


class TestKpiBadgeRow:
    def test_five_metrics_present(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The row shows exactly the five v1 metrics, keyed and in order (§4.4)."""
        row = KpiBadgeRow()
        qtbot.addWidget(row)
        assert list(row.badges.keys()) == ["SNR", "NEDT", "NIIRS", "GSD", "MTF@Nyquist"]
        assert tuple(row.badges.keys()) == METRIC_KEYS

    def test_values_are_em_dash(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """No fake numbers: every badge value is an em-dash until Phase 3 evaluates."""
        row = KpiBadgeRow()
        qtbot.addWidget(row)
        for badge in row.badges.values():
            assert badge.value_text() == "—"

    def test_units_sourced_from_api_not_hardcoded(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Badges carry no hardcoded unit; units come from result metadata (R-UNITS).

        The old shell hardcoded a unit per badge ("mK", "m", …). Phase 3 removes
        that — the unit is sourced from ``ChainResult.metric_records()`` at fill
        time (see :func:`radiant.gui.metric_format.format_metric_value`). This
        guards against a unit string creeping back into the widget.
        """
        row = KpiBadgeRow()
        qtbot.addWidget(row)
        assert not hasattr(row.badges["NEDT"], "unit")
        # The formatting helper appends the API-supplied unit for a dimensional
        # metric and omits it for a pure ratio / rating level.
        assert format_metric_value(0.0446, "K") == "0.0446 K"
        assert format_metric_value(615.96, "dimensionless") == "616"
        assert format_metric_value(10.62, "NIIRS level") == "10.62"

    def test_run_button_present_and_disabled(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The accent Run button is present but disabled in Phase 1."""
        row = KpiBadgeRow()
        qtbot.addWidget(row)
        assert row.run_button.objectName() == "runButton"
        assert not row.run_button.isEnabled()


class TestParameterPanel:
    def test_filter_present_with_placeholder(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The filter box is present with its placeholder; disabled until populated."""
        panel = ParameterPanel()
        qtbot.addWidget(panel)
        # A bare panel (no sensor) shows the empty state, so the filter is disabled.
        assert not panel.filter_box.isEnabled()
        assert panel.filter_box.placeholderText() == "Filter parameters…"

    def test_tree_three_columns_empty_state(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A bare panel has the three Parameter/Value/Source columns and empty state."""
        panel = ParameterPanel()
        qtbot.addWidget(panel)
        assert panel.tree.topLevelItemCount() == 0
        assert panel.tree.columnCount() == 3
        header = panel.tree.headerItem()
        assert header.text(0) == "Parameter"
        assert header.text(1) == "Value"
        assert header.text(2) == "Source"
        # Empty state (no config): tree hidden, filter disabled.
        assert not panel.tree.isVisible()


class TestPlotPlaceholder:
    def test_renders(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The placeholder builds with its named message region."""
        placeholder = PlotPlaceholder()
        qtbot.addWidget(placeholder)
        assert placeholder.objectName() == "plotPlaceholder"


class TestDetailTabs:
    def test_five_tabs_right_labels(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The detail panel has the five v1 tabs with the right labels, in order."""
        tabs = DetailTabs()
        qtbot.addWidget(tabs)
        assert tabs.count() == 5
        assert tabs.tab_labels() == ["Spectral", "MTF", "Noise Budget", "Variables", "YAML"]
        assert tabs.tab_labels() == list(TAB_LABELS)

    def test_tabs_selectable(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Each tab can be selected so the owner can judge tab styling (Phase 1)."""
        tabs = DetailTabs()
        qtbot.addWidget(tabs)
        for i in range(tabs.count()):
            tabs.setCurrentIndex(i)
            assert tabs.currentIndex() == i
