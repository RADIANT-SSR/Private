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

# CU-242 (owner-directed, 2026-07-27): a stage screen shows the values *calculated at
# that stage*, not every scalar it happens to publish. These two tables are keyed by
# stage namespace so the policy is declarative and greppable rather than branch logic
# inside the render loop.
#
# ``_INPUT_ECHO_KEYS`` — published for downstream use but *not* products of the stage.
# `qe_scalar` is a detector property averaged for the integration; presenting it
# beside signal_e implies the stage computed it.
_INPUT_ECHO_KEYS: dict[str, frozenset[str]] = {
    "spectral_integration": frozenset({"qe_scalar"}),
}

# ``_HIDE_WHEN_ZERO_KEYS`` — conditionally-relevant terms whose zero means "this path
# is not configured", not "this path contributes nothing measurable". Rendering
# `0 e-` invites the reader to conclude the model found the term negligible.
_HIDE_WHEN_ZERO_KEYS: dict[str, frozenset[str]] = {
    "spectral_integration": frozenset({"nearfield_e", "stray_e"}),
}

# Per-output tooltips (owner-supplied text, CU-242): why the value is computed *here*.
# Rule 8 is the reason this stage exists — band integrals must happen while the
# spectral arrays still exist — and the tooltips are where that is said to the operator.
_OUTPUT_TOOLTIPS: dict[str, dict[str, str]] = {
    "spectral_integration": {
        "signal_e": (
            "Target electrons collected in-band this integration: spectral radiance "
            "× chain throughput × QE, integrated over the filter band (Rule 8 — "
            "spectral collapses to scalar exactly here)."
        ),
        "e_rate_per_s": (
            "The same band integral per second, before the integration time is applied."
        ),
        "background_e": (
            "Background-path electrons in the pixel over the same band and integration time."
        ),
        "contrast_e": (
            "Detectable target-vs-reference-pixel differential; regime-dependent: "
            "point source = Signal (background is common-mode and cancels), sub-pixel "
            "subtracts only the displaced footprint background, extended compares "
            "against the reference scene (ADR-0005)."
        ),
        "ds_dt_e_per_K": (
            "Temperature sensitivity of the in-band signal via the Planck derivative "
            "(1/B)(dB/dT) — exact-NEDT support (Gap 43); downstream "
            "NEDT = σ_total / (dS/dT)."
        ),
        "nearfield_e": (
            "Electrons from the configured nearfield path; row hidden when the path "
            "is not configured."
        ),
        "stray_e": (
            "Electrons from the configured straylight path; row hidden when the path "
            "is not configured."
        ),
    },
}


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
            # CU-242: an input echo is not this stage's product — never render it.
            if key in _INPUT_ECHO_KEYS.get(stage, frozenset()):
                continue
            # CU-242: a conditionally-relevant term at exactly zero means "not
            # configured"; showing `0 e-` reads as "computed and negligible".
            if key in _HIDE_WHEN_ZERO_KEYS.get(stage, frozenset()) and value == 0:
                continue
            # An enum (e.g. regime_tentative) renders by its value string ("extended"),
            # never its ``RadiometricRegime.EXTENDED`` repr.
            display = value.value if isinstance(value, Enum) else value
            unit = stage_output_unit(stage, key)
            label = _humanize(key)
            self._add_row(
                row,
                key,
                label,
                _format_scalar(display, unit),
                tooltip=_OUTPUT_TOOLTIPS.get(stage, {}).get(key, ""),
            )
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

    def tooltip_for(self, key: str) -> str:
        """The row's explanatory tooltip, or "" when it has none (CU-242)."""
        return self._value_labels[key].toolTip()

    # -- internal -----------------------------------------------------------

    def _add_row(
        self, row: int, key: str, label: str, value_text: str, *, tooltip: str = ""
    ) -> None:
        """Add a label + value cell pair at grid *row*, with an optional *tooltip*.

        The tooltip (CU-242) says why the value is computed at this stage — it goes
        on both cells so a hover anywhere on the row finds it.
        """
        name_label = QLabel(label, self)
        name_label.setObjectName("outputsRowLabel")
        value_label = QLabel(value_text, self)
        value_label.setObjectName("outputsRowValue")
        if tooltip:
            name_label.setToolTip(tooltip)
            value_label.setToolTip(tooltip)
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
