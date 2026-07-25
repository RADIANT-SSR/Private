"""Tests for the Performance stage instrument (arch doc §4.4.1, owner redesign 2026-07-25).

The Performance stage is the terminal, output-only stage, rendered as a tabbed composite
(the §4.4 sub-view hook): **Summary** — the five headline badges (SNR accented) above the
system MTF, the post-evaluate landing; **All metrics** — the Gap-96 compute toggles
(checkbox order matching the card sections, geometry first) above the grouped metric cards
(one themed card per metric group, human display labels, values with registry units,
hover-revealed pins); **MTF budget** — the per-term Nyquist budget chart. A result-typed
metric failure (a non-finite value, Rule 17 carve-out for the ``radiant.performance``
metric layer) renders as ``n/a (<failure_reason>)`` — never a bare ``nan``, never a blank.
Every figure is one call on the bound ``result.plot.*`` accessor; every test drives the
real widgets offscreen.
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path
from typing import NamedTuple

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.metric_groups import GROUP_PARAMS, METRIC_GROUPS  # noqa: E402
from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.metric_format import (  # noqa: E402
    METRIC_DISPLAY_LABELS,
    METRIC_GROUP_HEADINGS,
    NOT_AVAILABLE,
    UNGROUPED_HEADING,
    grouped_metric_records,
    metric_display_label,
)
from radiant.gui.stage_views import STAGE_COMPOSITIONS  # noqa: E402
from radiant.gui.widgets.metric_group_cards import MetricGroupCards  # noqa: E402
from radiant.gui.widgets.performance_metrics_form import PerformanceMetricsForm  # noqa: E402
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402


class _Record(NamedTuple):
    """A minimal stand-in for ``io.results.MetricRecord`` — the fields the readout reads.

    The GUI layer imports only ``radiant.api`` + ``radiant.core`` (import rules), and
    ``MetricRecord`` is not re-exported on the public API surface, so the metric-failure unit
    test builds its own duck-typed record rather than importing from ``radiant.io``.
    """

    name: str
    value: float
    unit: str


_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


def _evaluate(sensor: Sensor) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


def _performance_pane(qtbot, sensor: Sensor) -> StagePane:
    """A bound, populated Performance StagePane on the example config."""
    pane = StagePane("performance", STAGE_COMPOSITIONS["performance"])
    qtbot.addWidget(pane)
    pane.bind_sensor(sensor, {})
    pane.populate(_evaluate(sensor))
    return pane


# ---------------------------------------------------------------------------
# Composition (Qt-free) — the owner-picked tabbed layout (2026-07-25)
# ---------------------------------------------------------------------------


class TestPerformanceComposition:
    def test_three_owner_ordered_tabs(self) -> None:
        """Summary lands first (badges + system MTF), then All metrics, then MTF budget."""
        comp = STAGE_COMPOSITIONS["performance"]
        assert [sub.title for sub in comp.subviews] == ["Summary", "All metrics", "MTF budget"]
        summary, all_metrics, budget = comp.subviews
        assert summary.summary_badges is True
        assert [p.method for p in summary.plots] == ["mtf"]
        assert all_metrics.metric_selection is True
        assert all_metrics.metrics is True
        assert [p.method for p in budget.plots] == ["mtf_budget"]
        # Both MTF figures still ship, one per tab.
        assert [p.method for sub in comp.subviews for p in sub.plots] == ["mtf", "mtf_budget"]

    def test_performance_has_no_editable_inputs(self) -> None:
        """The terminal stage consumes the chain — no input forms on any tab."""
        comp = STAGE_COMPOSITIONS["performance"]
        for spec in (comp, *comp.subviews):
            assert not any(
                (
                    spec.source_inputs,
                    spec.optics_inputs,
                    spec.detector_inputs,
                    spec.spectral_inputs,
                    spec.platform_inputs,
                    spec.readout_inputs,
                    spec.geometry_form,
                )
            )


# ---------------------------------------------------------------------------
# The pane renders: badges + grouped cards with units + both MTF figures
# ---------------------------------------------------------------------------


class TestPerformancePane:
    def test_tabs_render_and_land_on_summary(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        pane = _performance_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        assert pane.has_tabs
        assert pane.tab_titles() == ["Summary", "All metrics", "MTF budget"]

    def test_summary_badges_fill_from_the_metric_surface(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The five headline badges render real values (the PinnedCard badge path)."""
        pane = _performance_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        badges = pane.badge_row
        assert badges is not None
        assert badges.metric_keys() == (
            "snr",
            "nedt_K",
            "niirs",
            "gsd_geometric_mean_m",
            "mtf_at_nyquist",
        )
        assert badges.card("snr").value_text() not in ("", "—")
        # NEDT shows in the CU-108 display prefix (mK), unit sourced from the surface.
        assert badges.card("nedt_K").value_text().endswith("mK")

    def test_metric_cards_show_every_metric_with_units(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """All computed metrics render as card rows; dimensional ones keep their unit."""
        # The example config is outside the GIQE-5 envelope (SNR ~978); opt into
        # extrapolated NIIRS (CU-166 gate) so the niirs row renders.
        sensor = Sensor.from_yaml(_EXAMPLE).set("performance.niirs.allow_extrapolated", True)
        pane = _performance_pane(qtbot, sensor)
        cards = pane.metric_cards
        assert cards is not None
        keys = cards.rendered_keys()
        for name in ("snr", "nedt_K", "niirs", "gsd_geometric_mean_m", "mtf_at_nyquist"):
            assert name in keys
        # NEDT is in kelvin, GSD in metres — the dimensional metrics carry their unit.
        assert cards.value_text("nedt_K").endswith("K")
        assert cards.value_text("gsd_geometric_mean_m").endswith("m")
        # SNR is a dimensionless ratio — a bare number, no fake unit.
        assert "dimensionless" not in cards.value_text("snr")

    def test_system_mtf_and_budget_figures_render(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        pane = _performance_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        assert len(pane.plot_canvases) == 2
        assert all(c.has_figure() for c in pane.plot_canvases)


# ---------------------------------------------------------------------------
# Grouped cards: taxonomy partition, physics order, human labels, hover pins
# ---------------------------------------------------------------------------


class TestGroupedMetricCards:
    def test_sections_partition_by_taxonomy_and_keep_order(self) -> None:
        """Qt-free contract: every record lands in its Gap-96 group's section, sections
        follow the declared reading order, and no record is dropped or duplicated."""
        sensor = Sensor.from_yaml(_EXAMPLE).set("performance.niirs.allow_extrapolated", True)
        result = _evaluate(sensor)
        records = result.metric_records()  # type: ignore[attr-defined]
        sections = grouped_metric_records(records)

        heading_order = [h for _k, h in METRIC_GROUP_HEADINGS]
        rendered_headings = [heading for heading, _recs in sections]
        assert rendered_headings == [h for h in heading_order if h in rendered_headings]
        flat = [rec.name for _heading, recs in sections for rec in recs]
        assert sorted(flat) == sorted(rec.name for rec in records)
        by_heading = {heading: {rec.name for rec in recs} for heading, recs in sections}
        heading_of = dict(METRIC_GROUP_HEADINGS)
        for group, members in METRIC_GROUPS.items():
            expected = members & set(flat)
            if expected:
                assert by_heading[heading_of[group]] == expected

    def test_within_group_rows_follow_the_display_table_order(self) -> None:
        """Rows follow METRIC_DISPLAY_LABELS insertion order (physics reading order),
        not alphabetical — GSD cross/along/mean stay adjacent and lead the Q family."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        result = _evaluate(sensor)
        sections = dict(grouped_metric_records(result.metric_records()))  # type: ignore[attr-defined]
        sampling = [rec.name for rec in sections["Sampling / geometry"]]
        rank = {key: i for i, key in enumerate(METRIC_DISPLAY_LABELS)}
        assert sampling == sorted(sampling, key=lambda k: rank[k])
        assert sampling.index("gsd_cross_track_m") < sampling.index("q_center")

    def test_every_taxonomy_metric_has_a_display_label(self) -> None:
        """A registered metric without a human label fails here, not silently in the GUI."""
        for group_members in METRIC_GROUPS.values():
            for name in group_members:
                assert name in METRIC_DISPLAY_LABELS, f"metric without display label: {name}"
                assert METRIC_DISPLAY_LABELS[name] != name

    def test_unknown_metric_key_lands_in_other_section(self) -> None:
        """A metric key outside the taxonomy renders under 'Other' — never dropped."""
        records = (
            _Record(name="snr", value=1.0, unit="dimensionless"),
            _Record(name="not_a_registered_metric", value=2.0, unit="m"),
        )
        sections = grouped_metric_records(records)
        assert sections[-1][0] == UNGROUPED_HEADING
        assert [rec.name for rec in sections[-1][1]] == ["not_a_registered_metric"]
        # The raw-key fallback keeps it visible (and labelled by its key).
        assert metric_display_label("not_a_registered_metric") == "not_a_registered_metric"

    def test_widget_renders_cards_with_headings_and_hover_pins(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The cards widget shows the section headings in order; a row's pin emits the
        metric key with its human label; grouping is presentation-only."""
        sensor = Sensor.from_yaml(_EXAMPLE).set("performance.niirs.allow_extrapolated", True)
        pane = _performance_pane(qtbot, sensor)
        cards = pane.metric_cards
        assert cards is not None
        headings = cards.rendered_group_headings()
        assert len(headings) >= 3
        declared = [h for _k, h in METRIC_GROUP_HEADINGS]
        assert list(headings) == [h for h in declared if h in headings]
        result = _evaluate(sensor)
        assert cards.rendered_keys() == {rec.name for rec in result.metric_records()}  # type: ignore[attr-defined]
        # The pin carries the human label, so the rail card reads like the row.
        captured: list[tuple] = []  # type: ignore[type-arg]
        cards.pinMetricRequested.connect(lambda *a: captured.append(a))
        cards.row("gsd_cross_track_m").pin_button.click()
        assert captured == [("gsd_cross_track_m", "GSD (cross-track)")]


# ---------------------------------------------------------------------------
# The compute-toggle row lines up with the card sections (owner 2026-07-25)
# ---------------------------------------------------------------------------


class TestSelectionOrderMatchesSections:
    def test_checkbox_order_is_the_section_order(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Compute row's checkboxes follow METRIC_GROUP_HEADINGS (geometry first),
        each labelled with the exact heading of the card section it controls."""
        form = PerformanceMetricsForm()
        qtbot.addWidget(form)
        expected_dotpaths = tuple(GROUP_PARAMS[group] for group, _h in METRIC_GROUP_HEADINGS)
        assert form.group_dotpaths() == expected_dotpaths
        for group, heading in METRIC_GROUP_HEADINGS:
            assert form.checkbox(GROUP_PARAMS[group]).text() == heading


# ---------------------------------------------------------------------------
# Rule 17 carve-out: a result-typed metric failure shows its failure_reason
# ---------------------------------------------------------------------------


class _FailedSnrResult:
    """A stand-in for the ``stage_outputs["performance"]["snr_result"]`` object."""

    failure_reason = "signal below noise floor — SNR undefined"


class _FakeResult:
    """A minimal ChainResult stand-in exposing just the metric-failure surface."""

    def __init__(self, records: tuple[_Record, ...], performance: dict) -> None:  # type: ignore[type-arg]
        self._records = records
        self.stage_outputs = {"performance": performance}

    def metric_records(self) -> tuple[_Record, ...]:
        return self._records


class TestMetricFailureRendering:
    def test_non_finite_metric_shows_failure_reason_not_nan(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A non-finite SNR renders ``n/a (<failure_reason>)`` — never ``nan``, never blank."""
        cards = MetricGroupCards()
        qtbot.addWidget(cards)
        records = (_Record(name="snr", value=math.nan, unit="dimensionless"),)
        result = _FakeResult(records, {"snr_result": _FailedSnrResult()})
        cards.show_metrics(result)  # type: ignore[arg-type]

        text = cards.value_text("snr")
        assert text.startswith(NOT_AVAILABLE)
        assert "signal below noise floor" in text
        assert "nan" not in text.lower()

    def test_non_finite_metric_without_reason_shows_generic_note(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A non-finite metric with no named reason still never renders a bare number."""
        cards = MetricGroupCards()
        qtbot.addWidget(cards)
        records = (_Record(name="mtf_at_nyquist", value=math.inf, unit="dimensionless"),)
        result = _FakeResult(records, {})  # no result object for this key
        cards.show_metrics(result)  # type: ignore[arg-type]

        text = cards.value_text("mtf_at_nyquist")
        assert text.startswith(NOT_AVAILABLE)
        assert "non-finite" in text  # the generic named note, not a bare "inf"
