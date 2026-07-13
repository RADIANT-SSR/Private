"""The KPI badge row above the plot canvas (§4.4).

:class:`KpiBadgeRow` is the mockup's ``.kpis`` strip: the five v1 performance metrics
(SNR · NEDT · NIIRS · GSD · MTF@Nyquist) as :class:`~radiant.gui.widgets.metric_badge.MetricBadge`
cells, a stretch, and the accent :class:`~radiant.gui.widgets.run_button.RunButton` at
the trailing edge. Before evaluation every badge awaits (em-dash value); the Phase 3
evaluate loop fills them from a ``ChainResult`` via :meth:`update_from_result` — each
value with its unit sourced from the result's metric metadata (R-UNITS, GUI plan §4.6),
result-typed failures shown as a failure state (Rule 17 carve-out), never a blank.

The badge set and each badge's metric key live in
:mod:`radiant.gui.metric_format` (``BADGE_METRICS``); ``METRIC_KEYS`` is re-exported
here for back-compat with callers that imported it from this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtWidgets import QHBoxLayout, QWidget

from radiant.gui.metric_format import BADGE_KEYS, BADGE_METRICS, badge_display
from radiant.gui.widgets.metric_badge import MetricBadge
from radiant.gui.widgets.run_button import RunButton

if TYPE_CHECKING:
    from radiant.api import ChainResult

# The metric keys in display order (arch doc §4.4), re-exported for tests / callers.
METRIC_KEYS: Final[tuple[str, ...]] = BADGE_KEYS


class KpiBadgeRow(QWidget):
    """The five-badge KPI row with the trailing Run button (live in Phase 3).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("kpiRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(0)

        # Map each badge key to the ChainResult metric it reads (for update_from_result).
        self._metric_for: dict[str, str] = {}
        self._badges: dict[str, MetricBadge] = {}
        for key, label, metric_key, primary in BADGE_METRICS:
            badge = MetricBadge(key, label, primary=primary, parent=self)
            self._badges[key] = badge
            self._metric_for[key] = metric_key
            layout.addWidget(badge)

        layout.addStretch(1)

        self._run_button = RunButton(self)
        layout.addWidget(self._run_button)

    @property
    def badges(self) -> dict[str, MetricBadge]:
        """The metric badges keyed by metric key (e.g. ``"SNR"``)."""
        return dict(self._badges)

    @property
    def run_button(self) -> RunButton:
        """The trailing accent Run/Evaluate button."""
        return self._run_button

    # -- evaluate loop (Phase 3) --------------------------------------------

    def update_from_result(self, result: ChainResult) -> None:
        """Fill every badge from *result*'s metric surface (units from metadata).

        Each badge shows its value with its unit, a result-typed failure's
        ``failure_reason``, or an explicit "not computed" — never a blank. Filling
        clears any stale marker left by a prior failed evaluation.
        """
        for key, badge in self._badges.items():
            value_text, reason = badge_display(result, self._metric_for[key])
            if reason is None:
                badge.show_value(value_text)
            else:
                badge.show_failure(reason)
        self.set_stale(False)

    def set_stale(self, stale: bool) -> None:
        """Mark (or clear) every badge's shown value as stale (§8.4)."""
        for badge in self._badges.values():
            badge.set_stale(stale)

    def reset(self) -> None:
        """Return every badge to the pre-evaluation awaiting state."""
        for badge in self._badges.values():
            badge.show_awaiting()
