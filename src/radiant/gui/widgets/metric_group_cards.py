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
(Rule 19); ``_MetricRow``, ``_MetricLabel`` and ``_ColumnHeader`` are its private helpers.

**Multi-configuration mode (Phase 4d).** When the session is a study, the same cards
render each group as a **metric × configuration matrix**: the group card is still the
grouping unit (the owner's 2026-07-25 layout), and each metric row grows one column per
configuration. The whole presentation model — column order, cell text, absence and
failure states — is decided Qt-free in :mod:`radiant.gui.metric_matrix`; this widget only
lays it out. **Plain values only** (ADR-0010 D-9): no delta, no best-mark.

A single-configuration session never enters that mode: the host pushes no matrix, and
:meth:`MetricGroupCards.show_metrics` builds exactly the widgets it built before Phase 4d
— no headers, no chips, no extra grid columns (the tested zero-regression requirement).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QEnterEvent, QPixmap
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QStyle,
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
    from collections.abc import Mapping

    from radiant.api import ChainResult
    from radiant.gui.metric_matrix import MatrixColumn, MetricMatrix

# The pin affordance glyph (a push-pin) — the same glyph the Outputs readout rows use.
_PIN_GLYPH: str = "📌"

# Column-header markers. Text content, not style tokens: the failure marker says the
# configuration produced no result, the warning marker points at the Messages panel
# entries this configuration already owns (Phase 4a) — both explained on hover.
_FAILED_GLYPH: str = "✕"
_WARNING_GLYPH: str = "⚠"

# Cards flow into this many columns (the owner-approved two-up mockup layout). A study
# lays the cards out **one-up** instead: a card carrying N configuration columns needs
# the full pane width, and two-up would squeeze the numbers the study exists to compare.
_COLUMNS: int = 2
_COLUMNS_MATRIX: int = 1

# Side of the square accent chip drawn on a configuration column header, matching the
# selector band's chip (:class:`~radiant.gui.widgets.configuration_bar.ConfigurationBar`).
# Geometry, not a design token (GUI plan §4.9 keeps colours/fonts in themes/).
_CHIP_PX: int = 10


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
        self._value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._pin = QToolButton(self)
        self._pin.setObjectName("outputsPinButton")
        self._pin.setText(_PIN_GLYPH)
        self._pin.setToolTip("Pin this value to the right rail")
        self._pin.clicked.connect(self.pinClicked)
        # Hover-revealed (owner: 36 always-on pins were visual noise). The width is
        # RESERVED permanently and only the glyph's visibility toggles — the earlier
        # max-width 0↔unbounded toggle shifted the value label leftward under the
        # reader's eyes on every hover (2026-08-03 critique). Reveal also follows
        # keyboard focus: a zero-affordance hover-only control was unreachable
        # without a mouse.
        self._pin.setAutoRaise(True)
        self._pin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._pin.setAccessibleName(f"Pin {label} to the right rail")
        self._pin.focusInEvent = self._pin_focus_in  # type: ignore[method-assign]
        self._pin.focusOutEvent = self._pin_focus_out  # type: ignore[method-assign]
        self._set_pin_shown(False)

        layout.addWidget(name)
        layout.addStretch(1)
        layout.addWidget(self._value)
        layout.addWidget(self._pin)

    def _set_pin_shown(self, shown: bool) -> None:
        """Show/hide the pin glyph without changing the row's layout geometry."""
        # Transparent text, not width collapse: the reserved slot keeps the value
        # label's x-position fixed whether or not the pin is revealed.
        effect = self._pin.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(self._pin)
            self._pin.setGraphicsEffect(effect)
        effect.setOpacity(1.0 if shown else 0.0)

    def _pin_focus_in(self, event: Any) -> None:
        self._set_pin_shown(True)
        QToolButton.focusInEvent(self._pin, event)

    def _pin_focus_out(self, event: Any) -> None:
        if not self.underMouse():
            self._set_pin_shown(False)
        QToolButton.focusOutEvent(self._pin, event)

    def enterEvent(self, event: QEnterEvent) -> None:  # noqa: N802 — Qt override
        self._set_pin_shown(True)
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:  # noqa: N802 — Qt override
        if not self._pin.hasFocus():
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


class _MetricLabel(QWidget):
    """A matrix row's leading cell: the metric's human label + a hover-revealed pin.

    The single-configuration :class:`_MetricRow` keeps label, value and pin in one
    widget; in matrix mode the values live in their own grid columns, so the label and
    its pin are their own cell. The pin means the same thing in both modes — pin this
    *metric* — and the right rail keeps showing the **displayed** configuration's value
    for it, exactly as it does for every other rail card.
    """

    pinClicked = Signal()

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        name = QLabel(label, self)
        name.setObjectName("outputsRowLabel")

        self._pin = QToolButton(self)
        self._pin.setObjectName("outputsPinButton")
        self._pin.setText(_PIN_GLYPH)
        self._pin.setToolTip("Pin this value to the right rail")
        self._pin.setAutoRaise(True)
        self._pin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._pin.setAccessibleName(f"Pin {label} to the right rail")
        self._pin.focusInEvent = self._pin_focus_in  # type: ignore[method-assign]
        self._pin.focusOutEvent = self._pin_focus_out  # type: ignore[method-assign]
        self._pin.clicked.connect(self.pinClicked)
        self._set_pin_shown(False)

        layout.addWidget(name)
        layout.addStretch(1)
        layout.addWidget(self._pin)

    def _set_pin_shown(self, shown: bool) -> None:
        """Show/hide the pin glyph without changing the cell's layout geometry.

        Same reserved-slot treatment as :class:`_MetricRow` (2026-08-03 critique):
        opacity toggles, geometry never moves, keyboard focus reveals.
        """
        effect = self._pin.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(self._pin)
            self._pin.setGraphicsEffect(effect)
        effect.setOpacity(1.0 if shown else 0.0)

    def _pin_focus_in(self, event: Any) -> None:
        self._set_pin_shown(True)
        QToolButton.focusInEvent(self._pin, event)

    def _pin_focus_out(self, event: Any) -> None:
        if not self.underMouse():
            self._set_pin_shown(False)
        QToolButton.focusOutEvent(self._pin, event)

    def enterEvent(self, event: QEnterEvent) -> None:  # noqa: N802 — Qt override
        self._set_pin_shown(True)
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:  # noqa: N802 — Qt override
        if not self._pin.hasFocus():
            self._set_pin_shown(False)
        super().leaveEvent(event)

    @property
    def pin_button(self) -> QToolButton:
        """The pin affordance (for tests)."""
        return self._pin


class _ColumnHeader(QWidget):
    """One configuration's column header: accent chip, name, and state markers.

    The chip hue is handed down by the host and is the **selector band's** hue for that
    configuration slot (§8.1 ``config_accents``, both themes) — this widget picks no
    colour of its own. The displayed configuration is marked by a text emphasis carried
    on a dynamic Qt property, never by a second colour, so it cannot compete with the
    accent chips for meaning.
    """

    def __init__(self, column: MatrixColumn, accent: str | None, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("metricColumnHeader")
        self._column = column

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addStretch(1)

        self._chip: QLabel | None = None
        if accent is not None:
            chip = QLabel(self)
            chip.setObjectName("metricColumnChip")
            chip.setPixmap(self._chip_pixmap(accent))
            chip.setFixedSize(QSize(_CHIP_PX, _CHIP_PX))
            layout.addWidget(chip)
            self._chip = chip

        name = QLabel(column.name, self)
        name.setObjectName("metricColumnName")
        # Dynamic property, resolved by the themed QSS — the emphasis lives in
        # themes/stylesheet.py, not in a font/colour literal here (GUI plan §4.9).
        name.setProperty("displayed", column.displayed)
        layout.addWidget(name)
        self._name = name

        self._marker: QLabel | None = None
        if column.failed:
            self._marker = self._add_marker(layout, _FAILED_GLYPH, "metricColumnFailed")
        elif column.warnings:
            self._marker = self._add_marker(layout, _WARNING_GLYPH, "metricColumnWarning")

        self.setToolTip(self._tooltip())

    def _add_marker(self, layout: QHBoxLayout, glyph: str, object_name: str) -> QLabel:
        """Append a state marker glyph to the header."""
        marker = QLabel(glyph, self)
        marker.setObjectName(object_name)
        layout.addWidget(marker)
        return marker

    def _tooltip(self) -> str:
        """Hover text: the failure's what-line, or the warnings this configuration owns.

        The warning text is a **pointer** to the right-rail Messages entries Phase 4a
        already attributes to this configuration, not a second rendering of them.
        """
        column = self._column
        if column.failure is not None:
            return column.failure
        if column.warnings:
            head = f"{len(column.warnings)} warning(s) from {column.name} — see Messages:"
            return "\n".join([head, *column.warnings])
        return f"Configuration {column.name!r}"

    @staticmethod
    def _chip_pixmap(colour: str) -> QPixmap:
        """A small solid square of *colour* — the selector band's accent chip."""
        pixmap = QPixmap(_CHIP_PX, _CHIP_PX)
        pixmap.fill(QColor(colour))
        return pixmap

    # -- accessors (tests) --------------------------------------------------

    @property
    def configuration(self) -> str:
        """The configuration this header names."""
        return self._column.name

    @property
    def is_displayed(self) -> bool:
        """True when this column is the configuration the window is showing."""
        return bool(self._name.property("displayed"))

    @property
    def has_chip(self) -> bool:
        """True when an accent chip is painted on this header."""
        return self._chip is not None

    @property
    def marker_text(self) -> str:
        """The state-marker glyph (empty when the configuration ran cleanly)."""
        return self._marker.text() if self._marker is not None else ""


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
        self._cells: dict[tuple[str, str], QLabel] = {}
        self._headers: dict[str, _ColumnHeader] = {}
        self._labels: dict[str, _MetricLabel] = {}
        self._columns: tuple[str, ...] = ()
        self._matrix_scrolls: list[QScrollArea] = []

    # -- result delivery ----------------------------------------------------

    def show_metrics(self, result: ChainResult) -> None:
        """Rebuild the group cards from *result*'s metric surface.

        The **single-configuration** path, unchanged since the owner's 2026-07-25
        redesign: sections come from
        :func:`~radiant.gui.metric_format.grouped_metric_records` (heading order and
        within-group physics order are decided there, not here); each card is rebuilt
        from scratch on every result — the readout is a pure view.
        """
        self._clear()
        # Two-up flow: both grid columns share the width (CU-333: mode-dependent —
        # matrix mode zeroes column 1, so re-assert on every single-model render).
        for column in range(_COLUMNS):
            self._grid.setColumnStretch(column, 1)
        for index, (heading, records) in enumerate(grouped_metric_records(result.metric_records())):
            card = self._build_card(heading, records, result)
            self._grid.addWidget(
                card, index // _COLUMNS, index % _COLUMNS, Qt.AlignmentFlag.AlignTop
            )
            self._headings.append(heading)

    def show_matrix(self, matrix: MetricMatrix, accents: Mapping[str, str]) -> None:
        """Rebuild the group cards as metric × configuration matrices (Phase 4d).

        The grouping is unchanged — one card per Gap-96 metric group, in the shared
        section order — and each card gains one column per configuration, in the set
        order *matrix* was built with. Cards lay out one-up so the columns get the full
        pane width.

        Parameters
        ----------
        matrix:
            The presentation model from
            :func:`~radiant.gui.metric_matrix.build_metric_matrix`. Every cell's text —
            value + registry unit, ``—`` for a metric a configuration did not compute,
            the failure state for a configuration that did not evaluate — is decided
            there; this method never formats a number or names a unit.
        accents:
            Configuration name → the selector band's accent hue for it. A name with no
            entry simply gets no chip (never a locally-chosen colour).
        """
        self._clear()
        self._columns = matrix.names
        # One-up flow (CU-333): every matrix card lives in grid column 0. The
        # constructor gave BOTH columns stretch 1 for the two-up single-model flow,
        # and with the CU-332 scroll area no longer forcing the card's width, the
        # empty column 1 was silently taking half the pane — a half-width card
        # showing one clipped configuration column.
        self._grid.setColumnStretch(0, 1)
        for column in range(1, _COLUMNS):
            self._grid.setColumnStretch(column, 0)
        for index, (heading, rows) in enumerate(matrix.groups):
            card = self._build_matrix_card(heading, matrix.columns, rows, accents)
            self._grid.addWidget(
                card, index // _COLUMNS_MATRIX, index % _COLUMNS_MATRIX, Qt.AlignmentFlag.AlignTop
            )
            self._headings.append(heading)

    def _build_matrix_card(
        self,
        heading: str,
        columns: tuple[MatrixColumn, ...],
        rows: tuple[Any, ...],
        accents: Mapping[str, str],
    ) -> QWidget:
        """One themed group card: frozen metric labels beside scrolling value columns.

        CU-332: labels and values live in two height-synchronized grids. The
        label grid never scrolls; only the value grid (headers + cells) sits
        inside a per-card horizontal scroll area, so a matrix wider than the
        pane slides its configuration columns under a fixed metric-label
        column instead of carrying the row names off-screen. Every card's
        scrollbar is linked through :meth:`_sync_matrix_scrolls`, so the
        surface still scrolls as one.
        """
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

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(14)

        label_host = QWidget(card)
        label_grid = QGridLayout(label_host)
        label_grid.setContentsMargins(0, 0, 0, 0)
        label_grid.setHorizontalSpacing(0)
        label_grid.setVerticalSpacing(4)

        value_host = QWidget(card)
        value_grid = QGridLayout(value_host)
        value_grid.setContentsMargins(0, 0, 0, 0)
        value_grid.setHorizontalSpacing(14)
        value_grid.setVerticalSpacing(4)
        # Leading stretch column: when the columns fit the viewport they stay
        # right-packed against the card edge (the pre-CU-332 look); once they
        # overflow, surplus is zero and the stretch is inert.
        value_grid.setColumnStretch(0, 1)

        header_spacer = QWidget(label_host)
        label_grid.addWidget(header_spacer, 0, 0)
        header_widgets: list[QWidget] = []
        for index, column in enumerate(columns):
            header = _ColumnHeader(column, accents.get(column.name), value_host)
            value_grid.addWidget(header, 0, index + 1)
            header_widgets.append(header)
            self._headers[column.name] = header

        label_widgets: list[_MetricLabel] = []
        row_cells: list[list[QLabel]] = []
        for row_index, row in enumerate(rows, start=1):
            label = _MetricLabel(row.label, label_host)
            label.pinClicked.connect(
                lambda k=row.key, la=row.label: self.pinMetricRequested.emit(k, la)
            )
            label_grid.addWidget(label, row_index, 0)
            self._labels[row.key] = label
            label_widgets.append(label)
            cells: list[QLabel] = []
            for index, (column, cell) in enumerate(zip(columns, row.cells, strict=True)):
                value = QLabel(cell.text, value_host)
                value.setObjectName("outputsRowValue" if cell.is_value else "metricCellAbsent")
                value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                value.setToolTip(cell.tooltip)
                value_grid.addWidget(value, row_index, index + 1)
                self._cells[(row.key, column.name)] = value
                cells.append(value)
            row_cells.append(cells)

        # Park any vertical surplus (the reserved scrollbar strip, rounding) in an
        # empty stretch row at the bottom: with every real row at a fixed height and
        # no stretch target, QGridLayout would otherwise spread the surplus BETWEEN
        # the rows — walking the value rows out of register with the label column,
        # which has no surplus to spread.
        value_grid.setRowStretch(len(rows) + 1, 1)
        label_grid.setRowStretch(len(rows) + 1, 1)

        # Two grids stay row-aligned only by force: same vertical spacing plus
        # equal fixed heights per row (labels carry a pin button and can out-size
        # a bare value QLabel, so neither side's natural height can be trusted).
        if header_widgets:
            header_h = max(widget.sizeHint().height() for widget in header_widgets)
            header_spacer.setFixedHeight(header_h)
            # Pin the headers to the same number: QSS polish can re-size a
            # header after this method runs, and any one-sided growth walks the
            # label column out of register with its rows.
            for widget in header_widgets:
                widget.setFixedHeight(header_h)
        for label, cells in zip(label_widgets, row_cells, strict=True):
            heights = [label.sizeHint().height(), *(cell.sizeHint().height() for cell in cells)]
            row_h = max(heights)
            label.setFixedHeight(row_h)
            for cell in cells:
                cell.setFixedHeight(row_h)

        scroll = QScrollArea(card)
        scroll.setObjectName("metricMatrixScroll")
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(value_host)
        # Reserve the content height plus the as-needed bar's extent up front, so
        # the bar's appearance never squeezes the last metric row.
        bar_extent = scroll.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent, None, scroll)
        scroll.setMinimumHeight(value_host.sizeHint().height() + bar_extent + 2)
        scroll.horizontalScrollBar().valueChanged.connect(self._sync_matrix_scrolls)
        self._matrix_scrolls.append(scroll)

        body.addWidget(label_host, 0, Qt.AlignmentFlag.AlignTop)
        # No alignment flag here (CU-333): aligning a widget in a box layout opts
        # it out of stretching on BOTH axes, which pinned the scroll area at its
        # size hint — one clipped column beside dead whitespace. The stretch
        # factor needs the cell unaligned to fill the card's width; vertical
        # surplus is already parked in the grids' bottom stretch rows.
        body.addWidget(scroll, 1)
        box.addLayout(body)
        return card

    def _sync_matrix_scrolls(self, value: int) -> None:
        """One horizontal position for every card — the matrix scrolls as one surface.

        Safe against feedback: ``setValue`` on an already-matching bar emits no
        ``valueChanged``, so propagation terminates after one fan-out.
        """
        for scroll in self._matrix_scrolls:
            bar = scroll.horizontalScrollBar()
            if bar.value() != value:
                bar.setValue(value)

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
        """The metric keys currently rendered as rows (both modes)."""
        return set(self._rows) | set(self._labels)

    def rendered_group_headings(self) -> tuple[str, ...]:
        """The card headings currently rendered, in display order."""
        return tuple(self._headings)

    def value_text(self, key: str) -> str:
        """The rendered 'value + unit' text for metric *key* (KeyError if unknown)."""
        return self._rows[key].value_text()

    def row(self, key: str) -> _MetricRow:
        """The row widget for metric *key* (KeyError if unknown)."""
        return self._rows[key]

    def is_matrix(self) -> bool:
        """True while the cards render per-configuration columns (a study session)."""
        return bool(self._columns)

    def column_names(self) -> tuple[str, ...]:
        """The configuration columns currently rendered, in set order (``()`` if none)."""
        return self._columns

    def cell_text(self, key: str, configuration: str) -> str:
        """The rendered cell text for metric *key* in *configuration* (KeyError if absent)."""
        return self._cells[(key, configuration)].text()

    def cell_tooltip(self, key: str, configuration: str) -> str:
        """The hover text of metric *key*'s cell in *configuration*."""
        return self._cells[(key, configuration)].toolTip()

    def column_header(self, configuration: str) -> _ColumnHeader:
        """A column header widget for *configuration* (KeyError if unknown).

        Every card repeats the header row, so this returns the last card's — they are
        built from one :class:`~radiant.gui.metric_matrix.MatrixColumn` each and carry
        identical name, chip, marker and tooltip state.
        """
        return self._headers[configuration]

    def metric_label(self, key: str) -> _MetricLabel:
        """The matrix row's label cell for metric *key* (KeyError if unknown)."""
        return self._labels[key]

    # -- internal -----------------------------------------------------------

    def _clear(self) -> None:
        """Remove every card before a re-populate."""
        self._rows.clear()
        self._headings.clear()
        self._cells.clear()
        self._headers.clear()
        self._labels.clear()
        self._columns = ()
        self._matrix_scrolls.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()


__all__ = ["MetricGroupCards"]
