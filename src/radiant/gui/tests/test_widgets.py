"""Contract tests for the Phase-1 shell chrome widgets (GUI plan Phase 1 punch-list).

These assert the *static* content the owner judges the design system against renders:
the 9-stage strip in chain order with stale dots, the disabled parameter filter over an
empty tree, and the plot placeholder. The dissolved bottom detail tabs are covered by
``test_stage_center.py`` (their content relocated to the per-stage center + Inspector).
Behaviour (clicks, evaluation) is exercised in the evaluate-loop / stage-center tests.
"""

from __future__ import annotations

import pytest

from radiant.gui.metric_format import format_metric_value, scale_for_display
from radiant.gui.widgets.health_dot import VALID_STATUSES, HealthDot
from radiant.gui.widgets.parameter_panel import ParameterPanel
from radiant.gui.widgets.plot_placeholder import PlotPlaceholder
from radiant.gui.widgets.run_button import RunButton
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


class TestMetricFormat:
    def test_units_sourced_from_api_not_hardcoded(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Metric text carries no hardcoded unit; the unit comes from the API (R-UNITS).

        The old shell hardcoded a unit per badge ("mK", "m", …). The formatting helper
        (:func:`radiant.gui.metric_format.format_metric_value`, reused by the pinned
        cards) appends the API-supplied unit for a dimensional metric and omits it for a
        pure ratio / rating level. This guards against a unit string creeping back in.
        """
        assert format_metric_value(0.0446, "K") == "0.0446 K"
        assert format_metric_value(615.96, "dimensionless") == "616"
        assert format_metric_value(10.62, "NIIRS level") == "10.62"

    def test_nedt_scales_to_millikelvin(self) -> None:
        """CU-108: NEDT's canonical K value displays in mK (0.0446 K → 44.6 mK)."""
        value, unit = scale_for_display("nedt_K", 0.0446, "K")
        assert unit == "mK"
        assert value == pytest.approx(44.6, rel=1e-6)
        assert format_metric_value(value, unit) == "44.6 mK"

    def test_scale_for_display_leaves_unlisted_metrics_unchanged(self) -> None:
        """A metric with no scaling entry keeps its registry unit and value."""
        assert scale_for_display("snr", 616.0, "dimensionless") == (616.0, "dimensionless")
        assert scale_for_display("gsd_geometric_mean_m", 1.2, "m") == (1.2, "m")


class TestRunButton:
    def test_run_button_present_and_disabled(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The accent Run button is present but disabled by default (no sensor)."""
        button = RunButton()
        qtbot.addWidget(button)
        assert button.objectName() == "runButton"
        assert not button.isEnabled()


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
