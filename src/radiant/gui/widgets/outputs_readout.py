"""Themed Outputs readout for the contextual center — values with units + pin (§4.4).

:class:`OutputsReadout` renders a stage's read-only *Outputs* section (arch doc §4.4,
section 2): a titled key/value grid where every row shows a human label, the value **with
its unit** (R-UNITS, an owner hard rule), and a small **pin affordance** that adds the
value to the right-rail Pinned panel (arch doc §4.5). It is the generic sibling of the
Geometry angle readout, used for the scalar ``stage_outputs`` of the Source, Optics,
Platform, Spectral-Integration, Detector, and Readout views.

One row source: :meth:`show_stage_outputs` — the scalar entries of
``stage_outputs["<stage>"]`` (arrays and structured objects are skipped; they are shown as
plots, not scalars). The unit is read from the framework's single authoritative table
(:func:`radiant.api.stage_output_units.stage_output_unit`, keyed by ``(stage, key)`` per
``RADIANT_Conventions.md``), never inferred in this widget; no unit maths happens here
(Rule 2 — display only). A pinned row routes to the stage-output pin path (the value is
re-read from ``stage_outputs`` on each evaluation) — the §4.5 / CU-115 Step-B capability.

The **performance metric** readout is no longer this widget: the 2026-07-25 owner redesign
moved it to :class:`~radiant.gui.widgets.metric_group_cards.MetricGroupCards` (grouped
themed cards, human labels), which owns the metric pin path.

All colour/typography comes from the QSS theme via object names (GUI plan §4.9); this file
holds no colour/font/size literal.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import Enum
from typing import Any, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QToolButton,
    QWidget,
)

from radiant.api.stage_output_units import stage_output_unit
from radiant.gui.param_format import format_value

# The pin affordance glyph (a push-pin). A glyph, not a style token.
_PIN_GLYPH: Final[str] = "📌"

# Trailing tokens trimmed from a *label* (display only — the unit itself is sourced from
# the framework table, not from these). Most-specific (longest) first so ``_e_per_s`` and
# ``_e_per_k`` strip before ``_e``. These shorten "Jitter sigma x m" → "Jitter sigma x".
_LABEL_TRIM_SUFFIXES: Final[tuple[str, ...]] = (
    "_e_per_s",
    "_e_per_k",
    "_per_s",
    "_m2",
    "_rad",
    "_e",
    "_k",
    "_m",
    "_s",
)


def _humanize(key: str) -> str:
    """A human label for an output *key*, trimming a known unit-token suffix."""
    label = key
    for suffix in _LABEL_TRIM_SUFFIXES:
        if label.lower().endswith(suffix):
            label = label[: -len(suffix)]
            break
    return label.replace("_", " ").strip().capitalize() or key


# Descriptor-typed stage outputs that are ``None`` when absent (a *present* one is a
# structured object and is skipped as non-scalar). Rendering the absent case as a bare
# "— " row reads backwards, so these are skipped when None (CU-135).
_NULLABLE_DESCRIPTOR_KEYS = frozenset({"background", "target", "los_geometry"})


def _is_scalar(value: Any) -> bool:
    """True for the primitive scalars the readout renders (numbers, strings, enums, None).

    An :class:`~enum.Enum` (e.g. the Source stage's ``regime_tentative``
    :class:`~radiant.core.regime.RadiometricRegime`) is a scalar for display purposes —
    rendered by its ``.value`` in :meth:`OutputsReadout.show_stage_outputs`. Arrays and
    structured objects are not scalars; they surface as plots, not readout rows.
    """
    return value is None or isinstance(value, (bool, int, float, str, Enum))


def _format_scalar(display: Any, unit: str) -> str:
    """Format a scalar for a readout row, rendering non-finite floats as sentinels.

    A non-finite value (``inf`` for an unbounded/extended angular extent, ``nan``
    for undefined) has no meaningful unit, so it shows a bare glyph rather than
    "inf rad" (CU-135). Booleans are ``bool`` subclasses of ``int`` but always
    finite, so they take the normal path.
    """
    if isinstance(display, float) and not math.isfinite(display):
        if display == math.inf:
            return "∞"  # ∞ — unbounded (e.g. extended-target angular extent)
        if display == -math.inf:
            return "−∞"  # −∞
        return "n/a"  # nan
    return format_value(display, unit)


class OutputsReadout(QWidget):
    """Titled value/unit grid with a per-row pin affordance (arch doc §4.4 / §4.5).

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    pinOutputRequested(str, str, str, str):
        Emitted ``(stage, key, label, unit)`` when a stage-output row's pin is clicked;
        the Pinned panel re-reads ``stage_outputs[stage][key]`` on each evaluation.
    """

    pinOutputRequested = Signal(str, str, str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("outputsReadout")

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(5)
        self._grid.setColumnStretch(0, 1)  # let the label column take the slack

        # Keyed by output key so tests can read a rendered value back.
        self._value_labels: dict[str, QLabel] = {}

    # -- row sources --------------------------------------------------------

    def show_stage_outputs(self, stage: str, outputs: Mapping[str, Any]) -> None:
        """Render the scalar entries of *outputs* (``stage_outputs[stage]``) as rows.

        Non-scalar entries (arrays, structured objects) are skipped — they are shown as
        plots, not scalars. Each row's pin routes to :attr:`pinOutputRequested`.
        """
        self._clear()
        row = 0
        for key, value in outputs.items():
            if not _is_scalar(value):
                continue
            # A descriptor key that is None means "absent" — skip it rather than
            # render a backwards "— " row (a present descriptor is non-scalar and
            # already skipped above) (CU-135).
            if value is None and key in _NULLABLE_DESCRIPTOR_KEYS:
                continue
            # An enum (e.g. regime_tentative) renders by its value string ("extended"),
            # never its ``RadiometricRegime.EXTENDED`` repr.
            display = value.value if isinstance(value, Enum) else value
            unit = stage_output_unit(stage, key)
            label = _humanize(key)
            self._add_row(row, key, label, _format_scalar(display, unit))
            self._add_pin(
                row, lambda k=key, la=label, u=unit: self.pinOutputRequested.emit(stage, k, la, u)
            )
            row += 1
        self._grid.setRowStretch(row, 1)

    # -- accessors (tests) --------------------------------------------------

    def rendered_keys(self) -> set[str]:
        """The output keys currently rendered as rows."""
        return set(self._value_labels)

    def value_text(self, key: str) -> str:
        """The rendered 'value + unit' text for an output *key* (for tests)."""
        return self._value_labels[key].text()

    # -- internal -----------------------------------------------------------

    def _add_row(self, row: int, key: str, label: str, value_text: str) -> None:
        """Add a label + value cell pair at grid *row*."""
        name_label = QLabel(label, self)
        name_label.setObjectName("outputsRowLabel")
        value_label = QLabel(value_text, self)
        value_label.setObjectName("outputsRowValue")
        value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._grid.addWidget(name_label, row, 0)
        self._grid.addWidget(value_label, row, 1)
        self._value_labels[key] = value_label

    def _add_pin(self, row: int, on_click) -> None:  # type: ignore[no-untyped-def]
        """Add the pin affordance at grid *row*, column 2, wired to *on_click*."""
        pin = QToolButton(self)
        pin.setObjectName("outputsPinButton")
        pin.setText(_PIN_GLYPH)
        pin.setToolTip("Pin this value to the right rail")
        pin.clicked.connect(on_click)
        self._grid.addWidget(pin, row, 2)

    def _clear(self) -> None:
        """Remove all existing rows before a re-populate."""
        self._value_labels.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()


__all__ = ["OutputsReadout"]
