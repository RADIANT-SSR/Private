"""The Performance stage's **Metrics** selection card — group enable toggles (Gap 96).

:class:`PerformanceMetricsForm` is the contextual-center control that lets the analyst
choose *which* performance metric families the chain computes and surfaces. It exposes the
five ``performance.metrics.*`` boolean group flags (Radiometric / Spatial-MTF /
Interpretability / Sampling / Saturation) as checkboxes. Turning a group off truly stops
its *computation* — and any warnings it would emit — not merely its display (Gap 96);
:class:`~radiant.performance.stage.PerformanceStage` still computes any hidden prerequisites
via the metric dependency closure.

**One GUI action ↔ one API call (owner hard rule).** Each toggle performs exactly one
``sensor.set("performance.metrics.<group>", checked)`` and re-emits :attr:`parameterEdited`,
so the host debounces a full re-evaluation and every metric surface (the Metrics readout,
the pinned rail) re-renders with the reduced set. Labels come from a small human map; the
tooltip/description is read from the live schema
(:meth:`Sensor.parameter_def`) — never transcribed. Programmatic state-sync in
:meth:`bind_sensor` blocks signals so binding never fires a spurious edit.

All colour/typography come from the QSS theme via object names; this file holds no
colour/font literal. One widget class per file (Rule 19).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget

from radiant.api.metric_groups import GROUP_PARAMS
from radiant.core.exceptions import RadiantError

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

# Human labels for the five metric groups, in reading order. The dot-path comes from
# ``GROUP_PARAMS`` (the single source of truth shared with the schema and the stage), so the
# label is the only literal here.
_GROUP_LABELS: Final[tuple[tuple[str, str], ...]] = (
    ("radiometric", "Radiometric — SNR, contrast, SCNR, NEDT, detection range"),
    ("spatial_mtf", "Spatial / MTF — FWHM, RER, EE, Strehl, MTF at Nyquist"),
    ("interpretability", "Interpretability — NIIRS / IIRS, MRT"),
    ("sampling", "Sampling / geometry — GSD, Q, swath, diffraction limit"),
    ("saturation", "Saturation — well margin, ADC margin, dynamic range"),
)

_TITLE = "Metrics — select which groups are computed and shown"


class PerformanceMetricsForm(QWidget):
    """The Performance metric-selection card: one checkbox per metric group.

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        card = QWidget(self)
        card.setObjectName("geoModeFamily")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setProperty("state", "normal")
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(6)

        title = QLabel(_TITLE, card)
        title.setObjectName("geoModeFamilyTitle")
        title.setWordWrap(True)
        box.addWidget(title)

        self._checks: dict[str, QCheckBox] = {}
        for group, label in _GROUP_LABELS:
            dotpath = GROUP_PARAMS[group]
            check = QCheckBox(label, card)
            check.setObjectName("metricGroupCheck")
            check.setChecked(True)  # schema default; corrected on bind
            check.toggled.connect(lambda checked, dp=dotpath: self._on_toggle(dp, checked))
            box.addWidget(check)
            self._checks[dotpath] = check

        layout.addWidget(card)

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
            if self._sensor is not None:
                try:
                    checked = bool(self._sensor.get_input(dotpath))
                except (KeyError, RadiantError):
                    # KeyError: flag present-but-unresolved. RadiantError: the whole
                    # config cannot resolve yet (a blank File → New) — the box shows the
                    # default (on), not a crash (CU-140 guard pattern in param_format).
                    checked = True
            blocked = check.blockSignals(True)
            check.setChecked(checked)
            check.blockSignals(blocked)

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
