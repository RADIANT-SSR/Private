"""The metric × configuration matrix behind the Performance columns (Phase 4d).

This module turns a retained :class:`~radiant.api.config_set.ConfigSetRunResult`
(the whole evaluate-all pass the window keeps as ``last_run``) into the **plain
presentation model** the Performance group cards render as one column per
configuration (plan §4 item 6, ADR-0010 D-9).

It is deliberately **Qt-free**, so every binding rule below is unit-tested without a
widget:

* **Plain values only** (D-9). A cell carries a value and its unit and nothing else —
  no delta, no best-mark. Delta-vs-baseline and best-per-metric stay on the scripting
  ``compare`` surface (:meth:`~radiant.api.config_set.ConfigurationSet.compare`).
* **Units from the registry** (R-UNITS). Every value is rendered by
  :func:`~radiant.gui.metric_format.metric_value_display`, the *same* function the
  single-configuration readout uses, so a study cell and a single-model row are
  formatted identically and no unit string is ever written here.
* **Absent is absent** (Rule 17). A metric a configuration did not compute renders as
  :data:`NOT_COMPUTED` (an em dash) — never ``0``, never blank.
* **A failed configuration keeps its column.** Its cells read :data:`NOT_EVALUATED` and
  its column carries the error's *what*-line, so the operator sees which configuration
  failed and why instead of a silently narrower table.
* **Column order is set order.** The run's own ``entries`` are in *evaluation* order
  (active first); this module re-orders to the caller-supplied set order so the columns
  do not reshuffle when the displayed configuration changes.

Row order and grouping are not re-decided here: the sections come from
:func:`~radiant.gui.metric_format.grouped_metric_records` and the labels from
:func:`~radiant.gui.metric_format.metric_display_label`, so the study surface and the
single-model surface partition and order metrics identically by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from radiant.gui.metric_format import (
    grouped_metric_records,
    metric_display_label,
    metric_value_display,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from radiant.api.config_set import ConfigRun, ConfigSetRunResult

# Shown when a configuration's run simply does not carry this metric (a deselected
# Gap-96 metric group, or a regime that never populated it). An em dash, never a zero
# and never a blank — Rule 17: absent is absent.
NOT_COMPUTED: Final[str] = "—"

# Shown in every cell of a configuration whose evaluation failed. Distinct from
# NOT_COMPUTED on purpose: "this configuration produced no result at all" is a
# different fact from "this configuration ran and did not compute this metric".
NOT_EVALUATED: Final[str] = "not evaluated"


@dataclass(frozen=True, slots=True)
class MatrixColumn:
    """One configuration's column header state.

    Attributes
    ----------
    name:
        The configuration name (the header text).
    failure:
        The recorded error's *what*-line when this configuration failed to
        evaluate, else ``None``. Present so the header can show a failure marker
        and name the cause on hover without the caller re-deriving it.
    warnings:
        The warnings ``evaluate_all`` attributed to this configuration. The header
        shows a marker and lists them on hover; they are **already** rendered in the
        right-rail Messages panel (Phase 4a) — this is a pointer to them, not a
        second rendering of the same content.
    displayed:
        True for the configuration the rest of the window is currently showing. The
        card gives it a subtle text emphasis; it is never re-coloured, so it cannot
        compete with the accent chips.
    """

    name: str
    failure: str | None
    warnings: tuple[str, ...]
    displayed: bool

    @property
    def failed(self) -> bool:
        """True when this configuration produced no result."""
        return self.failure is not None


@dataclass(frozen=True, slots=True)
class MatrixCell:
    """One metric × configuration cell: the text to show and its hover text."""

    text: str
    tooltip: str

    @property
    def is_value(self) -> bool:
        """True when this cell shows a computed value rather than an absence state."""
        return self.text not in {NOT_COMPUTED, NOT_EVALUATED}


@dataclass(frozen=True, slots=True)
class MatrixRow:
    """One metric across every configuration, aligned with :attr:`MetricMatrix.columns`."""

    key: str
    label: str
    cells: tuple[MatrixCell, ...]


@dataclass(frozen=True, slots=True)
class MetricMatrix:
    """The whole Performance surface for a study: columns × grouped metric rows.

    Attributes
    ----------
    columns:
        One :class:`MatrixColumn` per configuration, in **set order**.
    groups:
        ``(group heading, rows)`` sections in the shared readout order
        (:data:`~radiant.gui.metric_format.METRIC_GROUP_HEADINGS`). A group with no
        metric in any configuration is absent, exactly as in the single-model readout.
    """

    columns: tuple[MatrixColumn, ...]
    groups: tuple[tuple[str, tuple[MatrixRow, ...]], ...]

    @property
    def names(self) -> tuple[str, ...]:
        """The configuration names, in column order."""
        return tuple(column.name for column in self.columns)

    def row(self, key: str) -> MatrixRow:
        """The row for metric *key* (``KeyError`` when no configuration computed it)."""
        for _heading, rows in self.groups:
            for row in rows:
                if row.key == key:
                    return row
        raise KeyError(key)


@dataclass(frozen=True, slots=True)
class ConfigurationColumns:
    """What the Performance surface needs to render a study: the matrix + its hues.

    The accents are handed **down** from the host (which reads them off the selector
    band, :meth:`~radiant.gui.widgets.configuration_bar.ConfigurationBar.accent_for`),
    so the Performance columns and the selector tabs cannot drift apart in either theme
    — there is one assignment of hue to configuration slot, not two.
    """

    matrix: MetricMatrix
    accents: Mapping[str, str]


def _what_line(entry: ConfigRun) -> str:
    """The failed *entry*'s what-line, the same one ``ConfigSetRunResult.summary`` prints.

    ``ConfigurationSet.sensor_for`` already names the configuration in its ``what`` and
    carries the chained physics error in ``why``, so no unwrapping happens here — the
    GUI shows the API's own actionable text.
    """
    error = entry.error
    if error is None:
        # Not reachable through evaluate_all (which records a result or an error);
        # a hand-built ConfigRun says so rather than rendering an empty column.
        return "no result recorded"
    return str(getattr(error, "what", "") or error)


def _failure_tooltip(entry: ConfigRun) -> str:
    """Header hover text for a failed configuration: what, then why when it differs."""
    what = _what_line(entry)
    why = str(getattr(entry.error, "why", "") or "")
    return f"{what}\n\n{why}" if why else what


def _ordered_entries(
    run: ConfigSetRunResult, order: Sequence[str]
) -> tuple[tuple[str, ConfigRun], ...]:
    """``run``'s entries as ``(name, entry)`` in *order*, then any the order omits.

    *order* is the configuration set's own name order, which is what the columns must
    follow; ``run.entries`` is in evaluation order (active first). A name the run does
    not hold is skipped (the set gained a configuration since the pass) and a name the
    order does not hold is appended (the set lost one) — nothing is dropped silently,
    and the stale pass still renders until the debounced re-run lands.
    """
    by_name = {entry.name: entry for entry in run.entries}
    ordered = [(name, by_name[name]) for name in order if name in by_name]
    seen = {name for name, _ in ordered}
    ordered.extend((entry.name, entry) for entry in run.entries if entry.name not in seen)
    return tuple(ordered)


def build_metric_matrix(
    run: ConfigSetRunResult,
    order: Sequence[str],
    displayed: str | None = None,
) -> MetricMatrix:
    """Build the metric × configuration matrix for *run*, columns in *order*.

    Parameters
    ----------
    run:
        The retained evaluate-all pass (``RADIANTMainWindow.last_run``). Nothing is
        re-evaluated here — the matrix is a pure view over results that already exist.
    order:
        The configuration set's name order; the column order (never the run's
        evaluation order, which puts the active configuration first).
    displayed:
        The configuration the window is currently showing, marked on its column.

    Returns
    -------
    MetricMatrix
        Grouped rows over the **union** of metrics any configuration computed, so a
        metric only one configuration produces still gets a row — with
        :data:`NOT_COMPUTED` in the others (Rule 17).
    """
    entries = _ordered_entries(run, order)
    columns = tuple(
        MatrixColumn(
            name=name,
            failure=_what_line(entry) if entry.result is None else None,
            warnings=tuple(entry.warnings),
            displayed=name == displayed,
        )
        for name, entry in entries
    )
    # Per configuration, in column order: its result (None when it failed), its
    # metric records by key, and the hover text a failed column's cells carry.
    sources: list[tuple[Any, dict[str, Any], str]] = []
    union: dict[str, Any] = {}
    for _name, entry in entries:
        result = entry.result
        by_key = {rec.name: rec for rec in result.metric_records()} if result is not None else {}
        sources.append((result, by_key, "" if result is not None else _failure_tooltip(entry)))
        for key, rec in by_key.items():
            union.setdefault(key, rec)

    groups: list[tuple[str, tuple[MatrixRow, ...]]] = []
    for heading, group_records in grouped_metric_records(union.values()):
        rows: list[MatrixRow] = []
        for rec in group_records:
            label = metric_display_label(rec.name)
            cells: list[MatrixCell] = []
            for column, (result, config_records, failure_tip) in zip(columns, sources, strict=True):
                own = config_records.get(rec.name)
                if result is None:
                    cells.append(MatrixCell(NOT_EVALUATED, failure_tip))
                elif own is None:
                    cells.append(MatrixCell(NOT_COMPUTED, f"{column.name} did not compute {label}"))
                else:
                    cells.append(
                        MatrixCell(metric_value_display(result, own), f"{label} — {column.name}")
                    )
            rows.append(MatrixRow(key=rec.name, label=label, cells=tuple(cells)))
        groups.append((heading, tuple(rows)))

    return MetricMatrix(columns=columns, groups=tuple(groups))


__all__ = [
    "NOT_COMPUTED",
    "NOT_EVALUATED",
    "ConfigurationColumns",
    "MatrixCell",
    "MatrixColumn",
    "MatrixRow",
    "MetricMatrix",
    "build_metric_matrix",
]
