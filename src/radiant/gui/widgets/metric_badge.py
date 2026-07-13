"""A single performance-metric badge for the KPI row (§4.4, §8.2).

:class:`MetricBadge` renders one KPI cell from the mockup's ``.kpi``: an uppercase
label, a large **mono** value slot, and a caption line. In GUI plan Phase 1 the value
is an em-dash and the caption reads "awaiting evaluation" — the badge shows *no* number
until the Phase 3 evaluate loop fills it, and when a real value arrives it carries its
unit (the owner's R-UNITS hard rule). Colour/typography is entirely themed (GUI plan
§4.9); the mono value slot is set by the QSS keyed on ``#metricValue``.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

# The em-dash placeholder shown before the first evaluation. A glyph, not a number —
# there are no fake values in the shell (task ground rule).
_AWAITING_VALUE: str = "—"  # —
_AWAITING_CAPTION: str = "awaiting evaluation"


class MetricBadge(QFrame):
    """One KPI badge: label, mono value slot, caption.

    Parameters
    ----------
    key:
        Stable metric key (e.g. ``"SNR"``, ``"NEDT"``, ``"MTF@Nyquist"``). Exposed
        via :attr:`metric_key` so callers look a badge up without walking children.
    label:
        Display label; rendered upper-cased (Qt QSS has no ``text-transform``).
    unit:
        The metric's unit (e.g. ``"mK"``, ``"m"``); stored for the Phase 3 value
        render (R-UNITS) and empty for dimensionless metrics. Not shown while awaiting.
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
        unit: str = "",
        primary: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._key = key
        self._unit = unit
        self.setObjectName("metricBadge")
        # Dynamic properties drive the QSS variants (accent value / awaiting muting).
        self.setProperty("primary", primary)
        self.setProperty("state", "awaiting")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 4, 14, 4)
        layout.setSpacing(2)

        self._label = QLabel(label.upper(), self)
        self._label.setObjectName("metricLabel")

        self._value = QLabel(_AWAITING_VALUE, self)
        self._value.setObjectName("metricValue")

        self._caption = QLabel(_AWAITING_CAPTION, self)
        self._caption.setObjectName("metricCaption")

        layout.addWidget(self._label)
        layout.addWidget(self._value)
        layout.addWidget(self._caption)

    @property
    def metric_key(self) -> str:
        """The stable metric key this badge shows."""
        return self._key

    @property
    def unit(self) -> str:
        """The metric's unit (empty for dimensionless metrics)."""
        return self._unit

    def value_text(self) -> str:
        """The current text in the value slot (an em-dash until Phase 3)."""
        return self._value.text()
