"""The Performance metric readout as themed group cards (owner redesign 2026-07-25).

:class:`MetricGroupCards` replaces the old single-column ``OutputsReadout`` metrics grid —
the "wall of text" the owner rejected twice (Windows finding 12, then the 2026-07-25
walkthrough). It renders the ``ChainResult`` metric surface as **side-by-side themed
cards**, one card per Gap-96 metric group, in the shared section order
(:data:`~radiant.gui.metric_format.METRIC_GROUP_HEADINGS`). Each row shows the metric's
**human display label** (:func:`~radiant.gui.metric_format.metric_display_label` — never
the raw registry key) and its value **with its registry unit**
(:func:`~radiant.gui.metric_format.metric_value_display`, R-UNITS; result-typed failures
render as ``n/a (<failure_reason>)`` — Rule 17 carve-out, never a bare ``nan``).

The per-row **pin** affordance (arch doc §4.5 — pin any metric to the right rail) is
hover-revealed: 36 always-on pin glyphs were part of the visual noise, so a row shows its
pin only while the pointer is over it. Pinning emits :attr:`pinMetricRequested` with the
metric key and its human label, so the rail card is labelled like the readout row.

The cards reuse the input-form visual language by object name (``geoModeFamily`` card,
``geoModeGroupHeading`` heading, ``outputsRowLabel`` / ``outputsRowValue`` rows) — no new
QSS, no colour/font literal here (GUI plan §4.9). One public widget class per file
(Rule 19); ``_MetricRow`` is its private row helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.metric_format import (
    grouped_metric_records,
    metric_display_label,
    metric_value_display,
)

if TYPE_CHECKING:
    from radiant.api import ChainResult

# The pin affordance glyph (a push-pin) — the same glyph the Outputs readout rows use.
_PIN_GLYPH: str = "📌"

# Cards flow into this many columns (the owner-approved two-up mockup layout).
_COLUMNS: int = 2


class _MetricRow(QWidget):
    """One metric row: human label, value+unit, and a hover-revealed pin affordance."""

    pinClicked = Signal()

    def __init__(self, label: str, value_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        name = QLabel(label, self)
        name.setObjectName("outputsRowLabel")
        self._value = QLabel(value_text, self)
        self._value.setObjectName("outputsRowValue")
        self._value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._pin = QToolButton(self)
        self._pin.setObjectName("outputsPinButton")
        self._pin.setText(_PIN_GLYPH)
        self._pin.setToolTip("Pin this value to the right rail")
        self._pin.clicked.connect(self.pinClicked)
        # Hover-revealed (owner: 36 always-on pins were visual noise). Hidden via a
        # transparent state, not setVisible(False), so the row height never jumps.
        self._pin.setAutoRaise(True)
        self._set_pin_shown(False)

        layout.addWidget(name)
        layout.addStretch(1)
        layout.addWidget(self._value)
        layout.addWidget(self._pin)

    def _set_pin_shown(self, shown: bool) -> None:
        """Show/hide the pin without changing the row's layout size."""
        self._pin.setMaximumWidth(16777215 if shown else 0)

    def enterEvent(self, event: QEnterEvent) -> None:  # noqa: N802 — Qt override
        self._set_pin_shown(True)
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:  # noqa: N802 — Qt override
        self._set_pin_shown(False)
        super().leaveEvent(event)

    # -- accessors (tests) --------------------------------------------------

    def value_text(self) -> str:
        """The rendered 'value + unit' text of this row."""
        return self._value.text()

    @property
    def pin_button(self) -> QToolButton:
        """The pin affordance (for tests)."""
        return self._pin


class MetricGroupCards(QWidget):
    """The grouped Performance metric readout: one themed card per metric group.

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    pinMetricRequested(str, str):
        Emitted ``(metric_key, display_label)`` when a row's pin is clicked; the
        Pinned panel reads the metric surface (the same path as the old readout).
    """

    pinMetricRequested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("metricGroupCards")

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(12)
        for column in range(_COLUMNS):
            self._grid.setColumnStretch(column, 1)

        self._rows: dict[str, _MetricRow] = {}
        self._headings: list[str] = []

    # -- result delivery ----------------------------------------------------

    def show_metrics(self, result: ChainResult) -> None:
        """Rebuild the group cards from *result*'s metric surface.

        Sections come from :func:`~radiant.gui.metric_format.grouped_metric_records`
        (heading order and within-group physics order are decided there, not here);
        each card is rebuilt from scratch on every result — the readout is a pure view.
        """
        self._clear()
        for index, (heading, records) in enumerate(grouped_metric_records(result.metric_records())):
            card = self._build_card(heading, records, result)
            self._grid.addWidget(
                card, index // _COLUMNS, index % _COLUMNS, Qt.AlignmentFlag.AlignTop
            )
            self._headings.append(heading)

    def _build_card(self, heading: str, records: tuple[Any, ...], result: ChainResult) -> QWidget:
        """One themed group card: an uppercase heading over its metric rows."""
        card = QWidget(self)
        card.setObjectName("geoModeFamily")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setProperty("state", "normal")
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(5)

        head = QLabel(heading, card)
        head.setObjectName("geoModeGroupHeading")
        box.addWidget(head)

        for rec in records:
            label = metric_display_label(rec.name)
            row = _MetricRow(label, metric_value_display(result, rec), card)
            row.pinClicked.connect(lambda k=rec.name, la=label: self.pinMetricRequested.emit(k, la))
            box.addWidget(row)
            self._rows[rec.name] = row
        return card

    # -- accessors (tests) --------------------------------------------------

    def rendered_keys(self) -> set[str]:
        """The metric keys currently rendered as rows."""
        return set(self._rows)

    def rendered_group_headings(self) -> tuple[str, ...]:
        """The card headings currently rendered, in display order."""
        return tuple(self._headings)

    def value_text(self, key: str) -> str:
        """The rendered 'value + unit' text for metric *key* (KeyError if unknown)."""
        return self._rows[key].value_text()

    def row(self, key: str) -> _MetricRow:
        """The row widget for metric *key* (KeyError if unknown)."""
        return self._rows[key]

    # -- internal -----------------------------------------------------------

    def _clear(self) -> None:
        """Remove every card before a re-populate."""
        self._rows.clear()
        self._headings.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()


__all__ = ["MetricGroupCards"]
