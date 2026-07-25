"""The Performance stage's **Metric selection** control — group enable toggles (Gap 96).

:class:`PerformanceMetricsForm` lets the analyst choose *which* performance metric families
the chain computes and surfaces. It exposes the five ``performance.metrics.*`` boolean group
flags as one compact "Compute:" row of checkboxes sitting directly above the grouped metric
cards. **The checkbox order is derived from the shared section-order table**
(:data:`~radiant.gui.metric_format.METRIC_GROUP_HEADINGS` — sampling/geometry first, owner
feedback 2026-07-25), so each toggle lines up with the card section it controls by
construction and the two orders can never drift. Turning a group off truly stops its
*computation* — and any warnings it would emit — not merely its display (Gap 96);
:class:`~radiant.performance.stage.PerformanceStage` still computes any hidden
prerequisites via the metric dependency closure.

**One GUI action ↔ one API call (owner hard rule).** Each toggle performs exactly one
``sensor.set("performance.metrics.<group>", checked)`` and re-emits :attr:`parameterEdited`,
so the host debounces a full re-evaluation and every metric surface (the grouped cards, the
Summary badges, the pinned rail) re-renders with the reduced set. The hover tooltip is read
from the live schema (:meth:`Sensor.parameter_def`) — never transcribed. Programmatic
state-sync in :meth:`bind_sensor` blocks signals so binding never fires a spurious edit.

All colour/typography come from the QSS theme via object names (``metricGroupCheck`` /
``outputsRowLabel``); this file holds no colour/font literal. One widget class per file
(Rule 19).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget

from radiant.api.metric_groups import GROUP_PARAMS
from radiant.core.exceptions import RadiantError
from radiant.gui.metric_format import METRIC_GROUP_HEADINGS

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor


class PerformanceMetricsForm(QWidget):
    """The Performance metric-selection control: one checkbox per metric group.

    Signals
    -------
    parameterEdited(str):
        Emitted with the ``performance.metrics.<group>`` dot-path after a toggle, so the
        host window refreshes the parameter tree and schedules a re-evaluation — the same
        contract as the stage input forms' ``parameterEdited``.
    """

    parameterEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("performanceMetricsForm")

        self._sensor: Sensor | None = None

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)

        prompt = QLabel("Compute:", self)
        prompt.setObjectName("outputsRowLabel")
        row.addWidget(prompt)

        # One checkbox per group, in the shared section order (METRIC_GROUP_HEADINGS) —
        # the checkbox row and the card sections below stay aligned by construction.
        self._checks: dict[str, QCheckBox] = {}
        for group, heading in METRIC_GROUP_HEADINGS:
            dotpath = GROUP_PARAMS[group]
            check = QCheckBox(heading, self)
            check.setObjectName("metricGroupCheck")
            check.setChecked(True)  # schema default; corrected on bind
            check.toggled.connect(lambda checked, dp=dotpath: self._on_toggle(dp, checked))
            row.addWidget(check)
            self._checks[dotpath] = check
        row.addStretch(1)

    # -- binding / refresh --------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor* and sync each checkbox to its current flag value.

        *display_units* is accepted for signature parity with the stage input forms
        (metric flags are unitless booleans, so it is unused). Signals are blocked during
        the sync so binding never emits :attr:`parameterEdited`.
        """
        self._sensor = sensor
        self.refresh()

    def refresh(self) -> None:
        """Re-read each flag from the bound sensor and set the checkbox (no signal)."""
        for dotpath, check in self._checks.items():
            checked = True
            tooltip = ""
            if self._sensor is not None:
                try:
                    checked = bool(self._sensor.get_input(dotpath))
                except (KeyError, RadiantError):
                    # KeyError: flag present-but-unresolved. RadiantError: the whole
                    # config cannot resolve yet (a blank File → New) — the box shows the
                    # default (on), not a crash (CU-140 guard pattern in param_format).
                    checked = True
                try:
                    tooltip = self._sensor.parameter_def(dotpath).description
                except (KeyError, RadiantError):
                    tooltip = ""
            blocked = check.blockSignals(True)
            check.setChecked(checked)
            check.blockSignals(blocked)
            check.setToolTip(tooltip)

    # -- editing (one sensor.set per toggle) --------------------------------

    def _on_toggle(self, dotpath: str, checked: bool) -> None:
        """Commit one ``sensor.set`` for the toggled group and signal the edit."""
        if self._sensor is None:
            return
        self._sensor.set(dotpath, checked)
        self.parameterEdited.emit(dotpath)

    # -- accessors (tests) --------------------------------------------------

    def group_dotpaths(self) -> tuple[str, ...]:
        """The ``performance.metrics.*`` dot-paths this form toggles, in order."""
        return tuple(self._checks)

    def is_checked(self, dotpath: str) -> bool:
        """Whether the checkbox for *dotpath* is currently checked."""
        return self._checks[dotpath].isChecked()

    def checkbox(self, dotpath: str) -> QCheckBox:
        """The :class:`QCheckBox` for *dotpath* (KeyError if unknown)."""
        return self._checks[dotpath]


__all__ = ["PerformanceMetricsForm"]
