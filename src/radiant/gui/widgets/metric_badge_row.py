"""The Performance Summary tab's headline badge row (owner redesign 2026-07-25).

:class:`MetricBadgeRow` puts the five headline metrics — SNR (accented), NEDT, NIIRS,
GSD, MTF@Nyquist, the :data:`~radiant.gui.metric_format.BADGE_METRICS` set — across the
top of the Performance **Summary** tab as full-width cards, so the post-evaluate landing
answers "how did it do" at a glance before any table or plot.

Each badge **is** a right-rail :class:`~radiant.gui.widgets.pinned_card.PinnedCard`
(one implementation, two homes — Rule 19): the same value formatting via
``badge_display`` (unit from the metric surface, R-UNITS), the same honest failure state
(``n/a`` + the result-typed ``failure_reason``, Rule 17 carve-out), the same theming.
The unpin affordance is hidden here — the Summary set is fixed, not a pin-set.

One public widget class per file (Rule 19). No colour/font literal (GUI plan §4.9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QHBoxLayout, QWidget

from radiant.gui.metric_format import BADGE_METRICS
from radiant.gui.widgets.pinned_card import PinnedCard

if TYPE_CHECKING:
    from radiant.api import ChainResult


class MetricBadgeRow(QWidget):
    """A fixed row of the five headline metric badges (Summary tab, arch doc §4.4.1).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("metricBadgeRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._cards: dict[str, PinnedCard] = {}
        for _badge_key, label, metric_key, primary in BADGE_METRICS:
            card = PinnedCard(metric_key, label, "performance", primary=primary, parent=self)
            card.unpin_button.hide()  # the Summary set is fixed, not a pin-set
            layout.addWidget(card, 1)
            self._cards[metric_key] = card

    # -- result delivery ----------------------------------------------------

    def update_from_result(self, result: ChainResult) -> None:
        """Fill every badge from *result*'s metric surface (the PinnedCard path)."""
        for card in self._cards.values():
            card.update_from_result(result)

    # -- accessors (tests) --------------------------------------------------

    def card(self, metric_key: str) -> PinnedCard:
        """The badge card for *metric_key* (KeyError if unknown)."""
        return self._cards[metric_key]

    def metric_keys(self) -> tuple[str, ...]:
        """The badge metric keys, in display order."""
        return tuple(self._cards)


__all__ = ["MetricBadgeRow"]
