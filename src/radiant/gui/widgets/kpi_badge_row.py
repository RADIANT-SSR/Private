"""The KPI badge row above the plot canvas (§4.4).

:class:`KpiBadgeRow` is the mockup's ``.kpis`` strip: the five v1 performance metrics
(SNR · NEDT · NIIRS · GSD · MTF@Nyquist) as :class:`~radiant.gui.widgets.metric_badge.MetricBadge`
cells, a stretch, and the accent :class:`~radiant.gui.widgets.run_button.RunButton` at
the trailing edge. GUI plan Phase 1 ships it static: every badge awaits evaluation
(em-dash value) and the Run button is disabled. Phase 3 fills the badges from the
``ChainResult`` metric surface (each value with its unit, R-UNITS).

``METRICS`` is the canonical v1 badge set (arch doc §4.4); SNR is the headline.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtWidgets import QHBoxLayout, QWidget

from radiant.gui.widgets.metric_badge import MetricBadge
from radiant.gui.widgets.run_button import RunButton

# (key, display label, unit, primary?) for the five v1 metrics (§4.4). Units are the
# canonical display units carried in Phase 3; SNR/NIIRS/MTF are dimensionless.
METRICS: Final[tuple[tuple[str, str, str, bool], ...]] = (
    ("SNR", "SNR", "", True),
    ("NEDT", "NEDT", "mK", False),
    ("NIIRS", "NIIRS", "", False),
    ("GSD", "GSD", "m", False),
    ("MTF@Nyquist", "MTF @ Nyq", "", False),
)

# The metric keys in display order, exported for tests / later phases.
METRIC_KEYS: Final[tuple[str, ...]] = tuple(key for key, _, _, _ in METRICS)


class KpiBadgeRow(QWidget):
    """The static five-badge KPI row with the trailing Run button (Phase 1 shell).

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

        self._badges: dict[str, MetricBadge] = {}
        for key, label, unit, primary in METRICS:
            badge = MetricBadge(key, label, unit=unit, primary=primary, parent=self)
            self._badges[key] = badge
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
        """The trailing accent Run/Evaluate button (disabled in Phase 1)."""
        return self._run_button
