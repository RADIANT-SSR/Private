"""A single performance-metric badge for the KPI row (§4.4, §8.2).

:class:`MetricBadge` renders one KPI cell from the mockup's ``.kpi``: an uppercase
label, a large **mono** value slot, and a caption line. Before the first
evaluation the value is an em-dash and the caption reads "awaiting evaluation".
The Phase 3 evaluate loop then drives the badge into one of three honest states —
never a blank or a fake number:

* **value** (:meth:`show_value`) — the metric with its unit inline (R-UNITS), the
  unit sourced from the ``ChainResult`` metric metadata, never hardcoded here.
* **failure** (:meth:`show_failure`) — a result-typed metric failure (Rule 17
  carve-out): the value slot shows ``n/a`` and the caption shows the
  ``failure_reason``.
* **stale** (:meth:`set_stale`) — the last evaluation failed, so the shown value
  predates the current inputs; a ``→?`` marker is appended (§8.4).

Colour/typography is entirely themed (GUI plan §4.9); the mono value slot and the
state/stale variants are keyed on object names and dynamic properties in the QSS.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

# The em-dash placeholder shown before the first evaluation. A glyph, not a number.
_AWAITING_VALUE: str = "—"  # —
_AWAITING_CAPTION: str = "awaiting evaluation"

# Appended to a stale value (§8.4 KPI stale marker): "this number predates the
# last edit / the last evaluation failed".
_STALE_MARKER: str = " →?"  # →?


class MetricBadge(QFrame):
    """One KPI badge: label, mono value slot, caption (live in Phase 3).

    Parameters
    ----------
    key:
        Stable metric key (e.g. ``"SNR"``, ``"NEDT"``, ``"MTF@Nyquist"``). Exposed
        via :attr:`metric_key` so callers look a badge up without walking children.
    label:
        Display label; rendered upper-cased (Qt QSS has no ``text-transform``).
    primary:
        Whether this is the headline metric (accent-coloured value, mockup ``.primary``).
    parent:
        The owning widget, if any.
    """

    def __init__(
        self,
        key: str,
        label: str,
        *,
        primary: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._key = key
        # The current value text (without the stale marker), so set_stale can
        # re-render the marker on/off without losing the underlying value.
        self._value_text = _AWAITING_VALUE
        self._stale = False
        self.setObjectName("metricBadge")
        # Dynamic properties drive the QSS variants (accent value / awaiting muting
        # / failure tint / stale marker colour).
        self.setProperty("primary", primary)
        self.setProperty("state", "awaiting")
        self.setProperty("stale", False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 4, 14, 4)
        layout.setSpacing(2)

        self._label = QLabel(label.upper(), self)
        self._label.setObjectName("metricLabel")

        self._value = QLabel(_AWAITING_VALUE, self)
        self._value.setObjectName("metricValue")

        self._caption = QLabel(_AWAITING_CAPTION, self)
        self._caption.setObjectName("metricCaption")
        self._caption.setWordWrap(True)

        layout.addWidget(self._label)
        layout.addWidget(self._value)
        layout.addWidget(self._caption)

    @property
    def metric_key(self) -> str:
        """The stable metric key this badge shows."""
        return self._key

    def value_text(self) -> str:
        """The current text in the value slot (includes the stale marker if stale)."""
        return self._value.text()

    def caption_text(self) -> str:
        """The current caption text (the failure reason in the failure state)."""
        return self._caption.text()

    # -- state transitions (Phase 3 evaluate loop) --------------------------

    def show_value(self, value_text: str) -> None:
        """Show a computed metric *value_text* (value + unit inline, R-UNITS)."""
        self._value_text = value_text
        self._caption.setText("")
        self._caption.setVisible(False)
        self._set_state("ok")

    def show_failure(self, reason: str) -> None:
        """Show a result-typed metric failure: ``n/a`` value + *reason* caption."""
        self._value_text = _AWAITING_VALUE if reason == "" else "n/a"
        self._caption.setText(reason)
        self._caption.setVisible(True)
        self._set_state("failed")

    def show_awaiting(self) -> None:
        """Reset to the pre-evaluation state (em-dash value, awaiting caption)."""
        self._value_text = _AWAITING_VALUE
        self._caption.setText(_AWAITING_CAPTION)
        self._caption.setVisible(True)
        self.set_stale(False)
        self._set_state("awaiting")

    def set_stale(self, stale: bool) -> None:
        """Mark (or clear) the shown value as stale — appends/removes the ``→?`` marker."""
        self._stale = stale
        self.setProperty("stale", stale)
        self._render_value()
        self._repolish()

    # -- rendering ----------------------------------------------------------

    def _set_state(self, state: str) -> None:
        """Set the badge state property and re-render (state drives the QSS variant)."""
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
        for widget in (self, self._value, self._caption):
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)
