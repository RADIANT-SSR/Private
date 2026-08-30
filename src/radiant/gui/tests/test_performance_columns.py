"""Multi-configuration Phase 4d: per-configuration columns on the Performance stage.

Category D — the GUI half of plan §4 item 6 / ADR-0010 D-9. Two layers are covered:

* **Qt-free** (:mod:`radiant.gui.metric_matrix`) — the presentation model: column order
  is set order, the row set is the *union* of metrics, a metric a configuration did not
  compute is ``—`` and never zero (Rule 17), a failed configuration keeps its column
  with the error's what-line, and every cell's text is the *same* registry-unit
  rendering the single-model readout uses (R-UNITS).
* **Widget + window** — the group cards render that model as metric × configuration
  matrices, the column headers carry the selector band's accent chips, the displayed
  configuration is marked and the mark follows a selector switch **without
  re-evaluating**, and a warning marker appears on the warning configuration's header
  only.

The **zero-regression** contract has its own class: a single-configuration session must
render the pre-Phase-4d readout — no columns, no headers, no chips — with the same rows
and the same text.

Numbers are never re-derived here: every expected cell string is computed from the
public ``run.result_for(<name>).metric_records()`` surface, so a test failure means the
GUI diverged from the API, not that a physics value moved.

Window-release discipline (CU-212): this module opens one main window per test; the
session-wide ``_release_widgets`` fixture in ``conftest.py`` closes, deletes, and drains
them after each test.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")


from radiant.api.config_set import ConfigurationSet  # noqa: E402
from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.metric_format import metric_value_display  # noqa: E402
from radiant.gui.metric_matrix import (  # noqa: E402
    NOT_COMPUTED,
    NOT_EVALUATED,
    build_metric_matrix,
)
from radiant.gui.widgets.metric_group_cards import MetricGroupCards  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

_FILTER_MIN = "spectral_integration.filter_min_um"
_FILTER_MAX = "spectral_integration.filter_max_um"
_SATURATION = "performance.metrics.saturation"
_F_NUMBER = "optics.f_number"

_WAIT_MS = 20000  # headroom over an 8-configuration evaluate-all pass

# A dimensional metric (registry unit "m") and a saturation-group one (unit "dB"):
# both are asserted to carry their unit in the rendered cell.
_GSD = "gsd_geometric_mean_m"
_WELL_MARGIN = "well_margin_dB"


# ---------------------------------------------------------------------------
# Fixtures — three-configuration studies
# ---------------------------------------------------------------------------


def _three_band_set() -> ConfigurationSet:
    """MWIR / LWIR / MWIR-narrow: three bands, so every λ-dependent metric differs."""
    cs = ConfigurationSet(Sensor.load(_EXAMPLE), names=["MWIR", "LWIR", "NARROW"])
    cs.configure(_FILTER_MIN, [3.5, 8.0, 4.0])
    cs.configure(_FILTER_MAX, [5.0, 12.0, 4.5])
    return cs


def _write(cs: ConfigurationSet, tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    cs.save(path)
    return path


def _open(qtbot, path: Path) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """Open *path* as a study and await its first evaluate-all pass."""
    window = RADIANTMainWindow(config_set=ConfigurationSet.load(path), path=str(path))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


def _open_three_band(qtbot, tmp_path: Path) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    return _open(qtbot, _write(_three_band_set(), tmp_path, "three_band.yaml"))


def _open_plain(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """Open the shipped single-configuration example and await its first pass."""
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


def _cards(window: RADIANTMainWindow) -> MetricGroupCards:
    """The Performance pane's metric cards, rendered for the current result."""
    window.central_canvas.stage_center.select_stage("performance")
    cards = window.central_canvas.stage_center.pane("performance").metric_cards
    assert cards is not None
    return cards


def _evaluate_all(cs: ConfigurationSet) -> Any:
    """Evaluate every configuration, suppressing the chain's physical-regime warnings."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return cs.evaluate_all()


def _expected_cell(run: Any, name: str, key: str) -> str:
    """What the API says configuration *name*'s cell for metric *key* must read."""
    result = run.result_for(name)
    for rec in result.metric_records():
        if rec.name == key:
            return metric_value_display(result, rec)
    return NOT_COMPUTED


# ---------------------------------------------------------------------------
# The Qt-free presentation model
# ---------------------------------------------------------------------------


class TestMatrixModel:
    def test_columns_follow_set_order_not_evaluation_order(self) -> None:
        cs = _three_band_set()
        cs.active = "NARROW"  # evaluation order becomes NARROW, MWIR, LWIR
        run = _evaluate_all(cs)
        assert run.names == ("NARROW", "MWIR", "LWIR")
        matrix = build_metric_matrix(run, cs.names(), cs.active)
        assert matrix.names == ("MWIR", "LWIR", "NARROW") == cs.names()

    def test_every_cell_is_the_api_rendering_of_that_configurations_value(self) -> None:
        cs = _three_band_set()
        run = _evaluate_all(cs)
        matrix = build_metric_matrix(run, cs.names(), cs.active)
        checked = 0
        for _heading, rows in matrix.groups:
            for row in rows:
                for column, cell in zip(matrix.columns, row.cells, strict=True):
                    assert cell.text == _expected_cell(run, column.name, row.key)
                    checked += 1
        assert checked > 0

    def test_dimensional_values_carry_their_registry_unit(self) -> None:
        cs = _three_band_set()
        matrix = build_metric_matrix(_evaluate_all(cs), cs.names(), cs.active)
        for cell in matrix.row(_GSD).cells:
            assert cell.text.endswith(" m")  # the registry unit, never hardcoded here

    def test_absent_metric_is_an_em_dash_never_zero(self) -> None:
        cs = _three_band_set()
        cs.configure(_SATURATION, [True, True, False])  # NARROW computes no saturation
        matrix = build_metric_matrix(_evaluate_all(cs), cs.names(), cs.active)
        row = matrix.row(_WELL_MARGIN)
        assert row.cells[2].text == NOT_COMPUTED
        assert row.cells[2].text not in {"0", "0.0", "0 dB", ""}
        for cell in row.cells[:2]:
            assert cell.text.endswith(" dB")

    def test_failed_configuration_keeps_its_column_with_the_what_line(self) -> None:
        cs = _three_band_set()
        cs.configure(_F_NUMBER, [4.0, 4.0, 6.0])  # NARROW over-constrains f/#
        run = _evaluate_all(cs)
        assert set(run.failures) == {"NARROW"}
        matrix = build_metric_matrix(run, cs.names(), cs.active)
        assert matrix.names == ("MWIR", "LWIR", "NARROW")
        failed = matrix.columns[2]
        assert failed.failed
        assert "NARROW" in (failed.failure or "")
        row = matrix.row(_GSD)
        assert row.cells[2].text == NOT_EVALUATED
        # The survivors keep real numbers — a failure never blanks the other columns.
        assert row.cells[0].text == _expected_cell(run, "MWIR", _GSD)
        assert row.cells[1].text == _expected_cell(run, "LWIR", _GSD)

    def test_displayed_flag_marks_exactly_one_column(self) -> None:
        cs = _three_band_set()
        matrix = build_metric_matrix(_evaluate_all(cs), cs.names(), "LWIR")
        assert [c.displayed for c in matrix.columns] == [False, True, False]

    def test_group_headings_match_the_single_model_sections(self) -> None:
        """A study partitions metrics exactly as one configuration does."""
        cs = _three_band_set()
        run = _evaluate_all(cs)
        matrix = build_metric_matrix(run, cs.names(), cs.active)
        from radiant.gui.metric_format import grouped_metric_records

        single = grouped_metric_records(run.result_for("MWIR").metric_records())
        assert [h for h, _ in matrix.groups] == [h for h, _ in single]


# ---------------------------------------------------------------------------
# The rendered Performance surface
# ---------------------------------------------------------------------------


class TestRenderedColumns:
    def test_cards_render_a_metric_by_configuration_matrix(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_three_band(qtbot, tmp_path)
        cards = _cards(window)
        assert cards.is_matrix()
        assert cards.column_names() == ("MWIR", "LWIR", "NARROW")
        run = window.last_run
        assert run is not None
        # Every rendered cell equals that configuration's own API value.
        keys = cards.rendered_keys()
        assert {_GSD, "snr"} <= keys
        for key in sorted(keys):
            for name in cards.column_names():
                assert cards.cell_text(key, name) == _expected_cell(run, name, key)
        # A dimensional metric shows its unit in every column (R-UNITS).
        for name in cards.column_names():
            assert cards.cell_text(_GSD, name).endswith(" m")
        # The three bands really do differ — the matrix is not showing one result three
        # times. (GSD is band-independent here; SNR is the wavelength-driven column.)
        assert len({cards.cell_text("snr", n) for n in cards.column_names()}) == 3

    def test_headers_carry_the_selector_bands_accent_hues(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_three_band(qtbot, tmp_path)
        cards = _cards(window)
        for name in cards.column_names():
            assert cards.column_header(name).has_chip

    def test_displayed_column_is_marked_and_follows_a_switch(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """The mark tracks the selector, and the switch renders from cache."""
        window = _open_three_band(qtbot, tmp_path)
        cards = _cards(window)
        assert [cards.column_header(n).is_displayed for n in cards.column_names()] == [
            True,
            False,
            False,
        ]
        before = window.last_run
        window.configuration_bar.buttons[1].click()  # display LWIR
        cards = _cards(window)
        assert [cards.column_header(n).is_displayed for n in cards.column_names()] == [
            False,
            True,
            False,
        ]
        # No re-evaluation: the retained pass object is the very one the switch rendered.
        assert window.last_run is before
        assert window.configuration_set is not None
        assert window.configuration_set.active == "LWIR"

    def test_column_order_is_set_order_after_a_switch(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_three_band(qtbot, tmp_path)
        window.configuration_bar.buttons[2].click()  # display NARROW (evaluates first)
        assert _cards(window).column_names() == ("MWIR", "LWIR", "NARROW")

    def test_metric_absent_from_one_configuration_shows_an_em_dash(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        cs = _three_band_set()
        cs.configure(_SATURATION, [True, True, False])
        window = _open(qtbot, _write(cs, tmp_path, "saturation_study.yaml"))
        cards = _cards(window)
        assert cards.cell_text(_WELL_MARGIN, "NARROW") == NOT_COMPUTED
        assert cards.cell_text(_WELL_MARGIN, "MWIR").endswith(" dB")
        assert cards.cell_text(_WELL_MARGIN, "LWIR").endswith(" dB")

    def test_failed_configuration_shows_its_state_and_leaves_the_others_intact(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path
    ) -> None:
        cs = _three_band_set()
        cs.configure(_F_NUMBER, [4.0, 4.0, 6.0])
        window = _open(qtbot, _write(cs, tmp_path, "failing_study.yaml"))
        cards = _cards(window)
        assert cards.column_names() == ("MWIR", "LWIR", "NARROW")  # no silent drop
        header = cards.column_header("NARROW")
        assert header.marker_text == "✕"
        assert "NARROW" in header.toolTip()
        assert cards.cell_text(_GSD, "NARROW") == NOT_EVALUATED
        run = window.last_run
        assert run is not None
        for name in ("MWIR", "LWIR"):
            assert cards.cell_text(_GSD, name) == _expected_cell(run, name, _GSD)

    def test_warning_marker_appears_only_on_the_warning_configuration(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path
    ) -> None:
        """LWIR saturates the shared well; the two MWIR bands do not, and stay unmarked."""
        # No extra configuration needed: on the shipped example's well capacity the
        # 8–12 µm band clips and the 3.5–5 / 4–4.5 µm bands do not, so the study
        # produces exactly the per-configuration warning attribution this asserts.
        window = _open(qtbot, _write(_three_band_set(), tmp_path, "warning_study.yaml"))
        cards = _cards(window)
        run = window.last_run
        assert run is not None
        assert set(run.warnings) == {"LWIR"}, run.warnings
        assert cards.column_header("LWIR").marker_text == "⚠"
        assert cards.column_header("MWIR").marker_text == ""
        assert cards.column_header("NARROW").marker_text == ""
        # The tooltip points at the Messages entries rather than re-rendering them.
        assert "Messages" in cards.column_header("LWIR").toolTip()

    def test_pinning_a_metric_still_works_from_a_matrix_row(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_three_band(qtbot, tmp_path)
        cards = _cards(window)
        with qtbot.waitSignal(cards.pinMetricRequested, timeout=1000) as blocker:
            cards.metric_label(_GSD).pin_button.click()
        assert blocker.args[0] == _GSD


# ---------------------------------------------------------------------------
# Zero regression — one configuration renders the pre-Phase-4d surface
# ---------------------------------------------------------------------------


class TestSingleConfigurationZeroRegression:
    def test_no_columns_no_headers_no_chips(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _open_plain(qtbot)
        cards = _cards(window)
        assert cards.is_matrix() is False
        assert cards.column_names() == ()
        assert window.central_canvas.stage_center.configuration_columns is None
        with pytest.raises(KeyError):
            cards.column_header("Configuration 1")

    def test_rows_are_the_single_model_rows_with_their_units(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _open_plain(qtbot)
        cards = _cards(window)
        result = window.last_result
        assert result is not None
        for rec in result.metric_records():
            assert cards.value_text(rec.name) == metric_value_display(result, rec)
        assert cards.value_text(_GSD).endswith(" m")

    def test_the_row_widget_path_is_unchanged(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The pre-4d ``_MetricRow`` (label + value + hover pin) still backs each row."""
        window = _open_plain(qtbot)
        cards = _cards(window)
        row = cards.row(_GSD)
        assert row.value_text() == cards.value_text(_GSD)
        with qtbot.waitSignal(cards.pinMetricRequested, timeout=1000) as blocker:
            row.pin_button.click()
        assert blocker.args[0] == _GSD


class TestFrozenLabelColumn:
    """CU-332: the metric-label column must stay put while configurations scroll.

    With 8 configurations the matrix outgrows the pane; pre-fix, the whole card
    grid scrolled sideways and carried the row labels off-screen. Now only the
    header + value columns live inside each card's horizontal scroll area, the
    label column is force-height-synced beside it, and every card's scrollbar
    is linked so the surface scrolls as one.
    """

    def _scrolls(self, cards: MetricGroupCards) -> list[Any]:
        from PySide6.QtWidgets import QScrollArea

        return list(cards.findChildren(QScrollArea, "metricMatrixScroll"))

    def test_labels_frozen_values_scrollable(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_three_band(qtbot, tmp_path)
        cards = _cards(window)
        scrolls = self._scrolls(cards)
        assert scrolls, "matrix cards must carry their horizontal scroll areas"
        for label in cards._labels.values():
            assert not any(s.isAncestorOf(label) for s in scrolls)
        for cell in cards._cells.values():
            assert any(s.isAncestorOf(cell) for s in scrolls)

    def test_cards_scroll_as_one_surface(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_three_band(qtbot, tmp_path)
        cards = _cards(window)
        scrolls = self._scrolls(cards)
        assert len(scrolls) >= 2, "the study renders multiple group cards"
        # Force a scrollable range regardless of the test screen's width.
        for scroll in scrolls:
            scroll.setFixedWidth(120)
        window.show()
        qtbot.waitExposed(window)
        first = scrolls[0].horizontalScrollBar()
        assert first.maximum() > 0
        target = min(30, first.maximum())
        first.setValue(target)
        for other in scrolls[1:]:
            bar = other.horizontalScrollBar()
            if bar.maximum() >= target:
                assert bar.value() == target

    def test_labels_align_with_their_rows(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_three_band(qtbot, tmp_path)
        cards = _cards(window)
        window.show()
        qtbot.waitExposed(window)
        name = cards._columns[0]
        checked = 0
        for key, label in cards._labels.items():
            cell = cards._cells.get((key, name))
            if cell is None:
                continue
            label_y = label.mapTo(cards, label.rect().center()).y()
            cell_y = cell.mapTo(cards, cell.rect().center()).y()
            assert abs(label_y - cell_y) <= 2, f"row {key!r} drifted {label_y - cell_y}px"
            checked += 1
        assert checked >= 5

    def test_value_area_fills_the_card_width(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """CU-333: the scroll area must take the card's width, not its size hint.

        The CU-332 rework passed an alignment flag to ``addWidget``, which opts
        the widget out of stretching entirely — every card showed one clipped
        configuration column beside dead whitespace.
        """
        window = _open_three_band(qtbot, tmp_path)
        window.resize(1200, 800)
        cards = _cards(window)
        window.show()
        qtbot.waitExposed(window)
        for scroll in self._scrolls(cards):
            card = scroll.parentWidget()
            # The empty second grid column must not steal pane width from the card…
            assert card.width() >= cards.width() * 0.9, (
                f"matrix card is {card.width()}px in a {cards.width()}px pane — "
                "the two-up flow's empty grid column is taking half the width"
            )
            # …and at 1200 px a three-configuration value grid must fit unclipped.
            content_w = scroll.widget().sizeHint().width()
            assert scroll.viewport().width() >= content_w, (
                f"value viewport {scroll.viewport().width()}px clips its "
                f"{content_w}px content — the scroll area is not stretching"
            )
