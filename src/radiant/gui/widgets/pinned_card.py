"""A single pinned metric card for the right-rail Pinned panel (arch doc §4.5).

:class:`PinnedCard` is the contextual-layout replacement for a KPI badge cell: a
card carrying a metric's label, its **value with unit** (sourced from the result
metric surface via :func:`radiant.gui.metric_format.badge_display` — never a
hardcoded unit, R-UNITS), a source line (the stage the value comes from), and an
**unpin** affordance. It is the relocation of the shipped global metric-badge row
into a pinnable rail card (badges → pinnable cards); the value-formatting and honest
failure/stale states are unchanged.

The three honest states mirror the old badge (never a blank, never a fake number):

* **value** — the metric with its unit inline; source line shows the source stage.
* **failure** — a result-typed metric failure (Rule 17 carve-out): the value slot
  reads ``n/a`` and the source line carries the ``failure_reason``.
* **stale** — the last evaluation failed, so the shown value predates the current
  inputs; a ``→?`` marker is appended (§8.4).

One widget class per file (Rule 19). Colour/typography is entirely themed via object
names and dynamic properties (GUI plan §4.9); this file holds no colour/font/size
literal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from radiant.gui.metric_format import badge_display

if TYPE_CHECKING:
    from radiant.api import ChainResult

# The em-dash placeholder shown before the first evaluation. A glyph, not a number.
_AWAITING_VALUE: str = "—"
# Appended to a stale value (§8.4): "this number predates the last evaluation".
_STALE_MARKER: str = " →?"
# The unpin affordance glyph (a pencil in the wireframe's card corner).
_UNPIN_GLYPH: str = "✎"


class PinnedCard(QFrame):
    """One pinned metric card: label, mono value slot, source line, unpin button.

    Parameters
    ----------
    pin_key:
        Stable pin identifier — the ``ChainResult`` metric key this card reads
        (e.g. ``"snr"``). Exposed via :attr:`pin_key` and emitted on unpin.
    label:
        Display label (e.g. ``"SNR"``, ``"MTF @ Nyq"``).
    source:
        The source-stage line shown under the value (e.g. ``"performance"``).
    primary:
        Whether this is the headline metric (accent-coloured value).
    parent:
        The owning widget, if any.

    Signals
    -------
    unpinRequested(str):
        Emitted with :attr:`pin_key` when the unpin affordance is clicked.
    """

    unpinRequested = Signal(str)

    def __init__(
        self,
        pin_key: str,
        label: str,
        source: str,
        *,
        primary: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._pin_key = pin_key
        self._source_text = source
        self._value_text = _AWAITING_VALUE
        self._stale = False
        self.setObjectName("pinnedCard")
        self.setProperty("primary", primary)
        self.setProperty("state", "awaiting")
        self.setProperty("stale", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(1)

        self._label = QLabel(label, self)
        self._label.setObjectName("pinnedCardLabel")

        self._value = QLabel(_AWAITING_VALUE, self)
        self._value.setObjectName("pinnedCardValue")

        self._source = QLabel(source, self)
        self._source.setObjectName("pinnedCardSource")
        self._source.setWordWrap(True)

        body.addWidget(self._label)
        body.addWidget(self._value)
        body.addWidget(self._source)
        layout.addLayout(body, 1)

        self._unpin = QToolButton(self)
        self._unpin.setObjectName("pinnedCardUnpin")
        self._unpin.setText(_UNPIN_GLYPH)
        self._unpin.setToolTip(f"Unpin {label}")
        self._unpin.clicked.connect(lambda: self.unpinRequested.emit(self._pin_key))
        layout.addWidget(self._unpin, 0)

    # -- accessors ----------------------------------------------------------

    @property
    def pin_key(self) -> str:
        """The metric key this card reads (and emits on unpin)."""
        return self._pin_key

    @property
    def unpin_button(self) -> QToolButton:
        """The unpin affordance (for tests / callers)."""
        return self._unpin

    def value_text(self) -> str:
        """The current text in the value slot (includes the stale marker if stale)."""
        return self._value.text()

    def source_text(self) -> str:
        """The current source line (the failure reason in the failure state)."""
        return self._source.text()

    # -- result delivery ----------------------------------------------------

    def update_from_result(self, result: ChainResult) -> None:
        """Fill the card from *result*'s metric surface (unit from metadata, R-UNITS).

        Shows the value with its unit, a result-typed ``failure_reason``, or an
        explicit "not computed" — never a blank. Filling clears any stale marker.
        """
        value_text, reason = badge_display(result, self._pin_key)
        if reason is None:
            self._value_text = value_text
            self._source.setText(self._source_text)
            self._set_state("ok")
        else:
            self._value_text = "n/a"
            self._source.setText(reason)
            self._set_state("failed")
        self.set_stale(False)

    def set_stale(self, stale: bool) -> None:
        """Mark (or clear) the shown value as stale — appends/removes the ``→?`` marker."""
        self._stale = stale
        self.setProperty("stale", stale)
        self._render_value()
        self._repolish()

    # -- rendering ----------------------------------------------------------

    def _set_state(self, state: str) -> None:
        """Set the card state property and re-render (state drives the QSS variant)."""
        self.setProperty("state", state)
        self._render_value()
        self._repolish()

    def _render_value(self) -> None:
        """Paint the value slot: the value text plus the stale marker when stale."""
        text = self._value_text
        if self._stale and text not in ("", _AWAITING_VALUE):
            text = f"{text}{_STALE_MARKER}"
        self._value.setText(text)

    def _repolish(self) -> None:
        """Re-apply the stylesheet so changed dynamic properties take effect."""
        for widget in (self, self._value, self._source):
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)


__all__ = ["PinnedCard"]
