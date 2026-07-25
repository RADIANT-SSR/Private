"""Tests for the Performance stage instrument (GUI plan Phase PS-6, arch doc §4.4.1).

The Performance stage is the terminal, output-only stage: a single flat pane with the metric
summary (all of ``result.metric_records()`` — SNR / NEDT / NIIRS / GSD / MTF@Nyquist and any
others — each value with its registry unit, sectioned under the Gap-96 metric-group headings
per Windows-deployment finding 12) above the system-MTF and MTF-budget plots. It has
no editable inputs (it consumes the chain). A result-typed metric failure (a non-finite value,
Rule 17 carve-out for the ``radiant.performance`` metric layer) renders as ``n/a
(<failure_reason>)`` — never a bare ``nan``, never a blank. Every figure is one call on the
bound ``result.plot.*`` accessor; every test drives the real widgets offscreen.
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path
from typing import NamedTuple

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.metric_groups import METRIC_GROUPS  # noqa: E402
from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.metric_format import (  # noqa: E402
    METRIC_GROUP_HEADINGS,
    NOT_AVAILABLE,
    UNGROUPED_HEADING,
    grouped_metric_records,
)
from radiant.gui.stage_views import STAGE_COMPOSITIONS  # noqa: E402
from radiant.gui.widgets.outputs_readout import OutputsReadout  # noqa: E402
from radiant.gui.widgets.performance_metrics_form import _GROUP_ROWS  # noqa: E402
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402


class _Record(NamedTuple):
    """A minimal stand-in for ``io.results.MetricRecord`` — the fields ``show_metrics`` reads.

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
# Composition (Qt-free) — metrics + system MTF + MTF budget, no editable inputs
# ---------------------------------------------------------------------------


class TestPerformanceComposition:
    def test_composition_binds_metrics_and_the_two_mtf_plots(self) -> None:
        comp = STAGE_COMPOSITIONS["performance"]
        assert comp.metrics is True
        assert [p.method for p in comp.plots] == ["mtf", "mtf_budget"]

    def test_performance_has_no_editable_inputs(self) -> None:
        """The terminal stage consumes the chain — no input forms of any kind."""
        comp = STAGE_COMPOSITIONS["performance"]
        assert not any(
            (
                comp.source_inputs,
                comp.optics_inputs,
                comp.detector_inputs,
                comp.spectral_inputs,
                comp.platform_inputs,
                comp.readout_inputs,
                comp.geometry_form,
            )
        )


# ---------------------------------------------------------------------------
# The pane renders: the metric summary with units + both MTF figures
# ---------------------------------------------------------------------------


class TestPerformancePane:
    def test_metric_summary_shows_every_metric_with_units(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """All computed metrics render; dimensional ones carry their registry unit (R-UNITS)."""
        # The example config is outside the GIQE-5 envelope (SNR ~978); opt
        # into extrapolated NIIRS (CU-166 gate) so the niirs row renders —
        # this test's subject is unit-labelled rendering, not the gate.
        sensor = Sensor.from_yaml(_EXAMPLE).set("performance.niirs.allow_extrapolated", True)
        pane = _performance_pane(qtbot, sensor)
        readout = pane.metrics_readout
        assert readout is not None
        keys = readout.rendered_keys()
        # The v1 metric set (units from metric_records(), never hardcoded).
        for name in ("snr", "nedt_K", "niirs", "gsd_geometric_mean_m", "mtf_at_nyquist"):
            assert name in keys
        # NEDT is in kelvin, GSD in metres — the dimensional metrics carry their unit.
        assert readout.value_text("nedt_K").endswith("K")
        assert readout.value_text("gsd_geometric_mean_m").endswith("m")
        # SNR is a dimensionless ratio — a bare number, no fake unit.
        assert readout.value_text("snr") == readout.value_text("snr").strip()
        assert "dimensionless" not in readout.value_text("snr")

    def test_system_mtf_and_budget_figures_render(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        pane = _performance_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        assert len(pane.plot_canvases) == 2
        assert all(c.has_figure() for c in pane.plot_canvases)


# ---------------------------------------------------------------------------
# Finding 12 (Windows deployment review): the metric readout is grouped, not a
# flat alphabetical dump — labeled sections in a fixed reading order, headings
# shared with the Metric-selection card, values/units untouched.
# ---------------------------------------------------------------------------


class TestGroupedMetricReadout:
    def test_sections_partition_by_taxonomy_and_keep_order(self) -> None:
        """Qt-free contract: every record lands in its Gap-96 group's section, sections
        follow the declared reading order, and no record is dropped or duplicated."""
        sensor = Sensor.from_yaml(_EXAMPLE).set("performance.niirs.allow_extrapolated", True)
        result = _evaluate(sensor)
        records = result.metric_records()  # type: ignore[attr-defined]
        sections = grouped_metric_records(records)

        heading_order = [h for _k, h in METRIC_GROUP_HEADINGS]
        rendered_headings = [heading for heading, _recs in sections]
        # Sections appear in declared order (empty ones dropped, none invented).
        assert rendered_headings == [h for h in heading_order if h in rendered_headings]
        # The partition is exact: every metric appears once, in its taxonomy group.
        flat = [rec.name for _heading, recs in sections for rec in recs]
        assert sorted(flat) == sorted(rec.name for rec in records)
        by_heading = {heading: {rec.name for rec in recs} for heading, recs in sections}
        heading_of = dict(METRIC_GROUP_HEADINGS)
        for group, members in METRIC_GROUPS.items():
            expected = members & set(flat)
            if expected:
                assert by_heading[heading_of[group]] == expected

    def test_unknown_metric_key_lands_in_other_section(self) -> None:
        """A metric key outside the taxonomy renders under 'Other' — never dropped."""
        records = (
            _Record(name="snr", value=1.0, unit="dimensionless"),
            _Record(name="not_a_registered_metric", value=2.0, unit="m"),
        )
        sections = grouped_metric_records(records)
        assert sections[-1][0] == UNGROUPED_HEADING
        assert [rec.name for rec in sections[-1][1]] == ["not_a_registered_metric"]

    def test_widget_renders_group_headings_with_values_and_units_intact(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Performance readout shows the section headings in order; grouping is
        presentation-only (same keys, same value+unit texts as the metric surface)."""
        sensor = Sensor.from_yaml(_EXAMPLE).set("performance.niirs.allow_extrapolated", True)
        pane = _performance_pane(qtbot, sensor)
        readout = pane.metrics_readout
        assert readout is not None
        headings = readout.rendered_group_headings()
        assert len(headings) >= 3  # the example computes several groups
        declared = [h for _k, h in METRIC_GROUP_HEADINGS]
        assert list(headings) == [h for h in declared if h in headings]
        # Grouping did not change what renders: every computed metric is still a row,
        # and the dimensional rows keep their units (R-UNITS).
        result = _evaluate(sensor)
        assert readout.rendered_keys() == {rec.name for rec in result.metric_records()}  # type: ignore[attr-defined]
        assert readout.value_text("gsd_geometric_mean_m").endswith("m")

    def test_headings_match_metric_selection_card_labels(self) -> None:
        """A group's checkbox label and its readout section heading are the same string."""
        card_labels = {group: name for group, name, _hint in _GROUP_ROWS}
        assert card_labels == dict(METRIC_GROUP_HEADINGS)


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
        readout = OutputsReadout()
        qtbot.addWidget(readout)
        records = (_Record(name="snr", value=math.nan, unit="dimensionless"),)
        result = _FakeResult(records, {"snr_result": _FailedSnrResult()})
        readout.show_metrics(result)  # type: ignore[arg-type]

        text = readout.value_text("snr")
        assert text.startswith(NOT_AVAILABLE)
        assert "signal below noise floor" in text
        assert "nan" not in text.lower()

    def test_non_finite_metric_without_reason_shows_generic_note(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A non-finite metric with no named reason still never renders a bare number."""
        readout = OutputsReadout()
        qtbot.addWidget(readout)
        records = (_Record(name="mtf_at_nyquist", value=math.inf, unit="dimensionless"),)
        result = _FakeResult(records, {})  # no result object for this key
        readout.show_metrics(result)  # type: ignore[arg-type]

        text = readout.value_text("mtf_at_nyquist")
        assert text.startswith(NOT_AVAILABLE)
        assert "non-finite" in text  # the generic named note, not a bare "inf"
