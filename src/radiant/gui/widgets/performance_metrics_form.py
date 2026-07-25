"""The Performance stage's **Metric selection** control — group enable toggles (Gap 96).

:class:`PerformanceMetricsForm` lets the analyst choose *which* performance metric families
the chain computes and surfaces. It exposes the five ``performance.metrics.*`` boolean group
flags (Radiometric / Spatial-MTF / Interpretability / Sampling / Saturation) as a compact
two-column list: a bold group name (the checkbox) beside a dimmed hint naming the group's
metrics. Turning a group off truly stops its *computation* — and any warnings it would emit —
not merely its display (Gap 96); :class:`~radiant.performance.stage.PerformanceStage` still
computes any hidden prerequisites via the metric dependency closure.

**One GUI action ↔ one API call (owner hard rule).** Each toggle performs exactly one
``sensor.set("performance.metrics.<group>", checked)`` and re-emits :attr:`parameterEdited`,
so the host debounces a full re-evaluation and every metric surface (the Metrics readout, the
pinned rail) re-renders with the reduced set. The hover tooltip is read from the live schema
(:meth:`Sensor.parameter_def`) — never transcribed. Programmatic state-sync in
:meth:`bind_sensor` blocks signals so binding never fires a spurious edit.

All colour/typography come from the QSS theme via object names (``metricGroupCheck`` /
``metricGroupHint``); this file holds no colour/font literal. One widget class per file
(Rule 19).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QGridLayout, QLabel, QWidget

from radiant.api.metric_groups import GROUP_PARAMS
from radiant.core.exceptions import RadiantError
from radiant.gui.metric_format import METRIC_GROUP_HEADINGS

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

# The shared group → display-heading table (metric_format), so a group's checkbox here
# and its section heading in the Metrics readout read identically (finding 12).
_HEADINGS: Final[dict[str, str]] = dict(METRIC_GROUP_HEADINGS)

# (group, bold name, dimmed metric hint), in reading order. The dot-path comes from
# ``GROUP_PARAMS`` (the single source of truth shared with the schema and the stage); the
# hint is the only literal here (the name is the shared heading).
_GROUP_ROWS: Final[tuple[tuple[str, str, str], ...]] = (
    ("radiometric", _HEADINGS["radiometric"], "SNR, contrast, SCNR, NEDT, detection range"),
    ("spatial_mtf", _HEADINGS["spatial_mtf"], "FWHM, RER, EE, Strehl, MTF at Nyquist"),
    ("interpretability", _HEADINGS["interpretability"], "NIIRS / IIRS, MRT"),
    ("sampling", _HEADINGS["sampling"], "GSD, Q, swath, diffraction limit"),
    ("saturation", _HEADINGS["saturation"], "well margin, ADC margin, dynamic range"),
)


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

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(4)

        self._checks: dict[str, QCheckBox] = {}
        for row, (group, name, hint) in enumerate(_GROUP_ROWS):
            dotpath = GROUP_PARAMS[group]
            check = QCheckBox(name, self)
            check.setObjectName("metricGroupCheck")
            check.setChecked(True)  # schema default; corrected on bind
            check.toggled.connect(lambda checked, dp=dotpath: self._on_toggle(dp, checked))
            hint_label = QLabel(hint, self)
            hint_label.setObjectName("metricGroupHint")
            grid.addWidget(check, row, 0)
            grid.addWidget(hint_label, row, 1)
            self._checks[dotpath] = check
        grid.setColumnStretch(1, 1)

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
