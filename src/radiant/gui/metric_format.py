"""Presentation helpers for the performance-metric cards (arch doc §4.4/§4.5, R-UNITS).

These pure functions turn the *public* ``ChainResult`` metric surface
(:meth:`ChainResult.metric_records`, which joins each value with its registry
unit — Gap 71) into the text a :class:`~radiant.gui.widgets.pinned_card.PinnedCard`
shows (the relocated metric badge). Every dimensional value carries its unit, sourced
from the result's own
metadata and never hardcoded in a widget (the owner's R-UNITS hard rule,
GUI plan §4.6). Result-typed metric failures (Rule 17 carve-out) are surfaced as
an explicit failure state, never a blank or a fake number.

No Qt dependency lives here, so the badge-fill contract is unit-tested directly
without a widget. No colour/font/size literal lives here either — those belong to
:mod:`radiant.gui.themes` (GUI plan §4.9).

The five v1 badges (arch doc §4.4) and the metric each reads:

======  ====================  =========================
Badge   metric key            registry unit
======  ====================  =========================
SNR     ``snr``               dimensionless
NEDT    ``nedt_K``            K (displayed as mK — CU-108)
NIIRS   ``niirs``             NIIRS level
GSD     ``gsd_geometric_mean_m``  m
MTF@Nyq ``mtf_at_nyquist``    dimensionless
======  ====================  =========================
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from radiant.api import ChainResult

# (badge key, display label, ChainResult metric key, primary?) for the five v1
# metrics (arch doc §4.4). SNR is the headline (accent value). The metric keys are
# the registry names read back via ``metric_records()`` — the units come from
# there, never from this table.
BADGE_METRICS: Final[tuple[tuple[str, str, str, bool], ...]] = (
    ("SNR", "SNR", "snr", True),
    ("NEDT", "NEDT", "nedt_K", False),
    ("NIIRS", "NIIRS", "niirs", False),
    ("GSD", "GSD", "gsd_geometric_mean_m", False),
    ("MTF@Nyquist", "MTF @ Nyq", "mtf_at_nyquist", False),
)

# The badge keys in display order, exported for tests / later phases.
BADGE_KEYS: Final[tuple[str, ...]] = tuple(key for key, _, _, _ in BADGE_METRICS)

# Registry "units" that name a pure ratio or a rating-scale level rather than a
# physical dimension; these render as a bare number on a badge (matching the
# mockup, arch doc §4.4, where SNR / NIIRS / MTF carry no suffix). A genuinely
# dimensional unit (K, m, …) is always shown. This is a display rule on the unit
# *string the API supplies*, not a hardcoded unit substituted for a value.
_BARE_UNITS: Final[frozenset[str]] = frozenset({"dimensionless", "NIIRS level"})

# Metric key → the ``stage_outputs["performance"]`` result object that carries a
# structured ``failure_reason`` (Rule 17 carve-out). Only the metrics whose
# metric-layer computation is result-typed appear here; the rest either compute or
# are simply absent from ``metrics`` (rendered as "not computed").
_FAILURE_RESULT_KEY: Final[dict[str, str]] = {
    "snr": "snr_result",
    "nedt_K": "nedt_result",
}

# Shown in the value slot for a failed / unavailable metric — explicitly *not a
# number*, so a stale or failed metric never reads as a real value.
NOT_AVAILABLE: Final[str] = "n/a"

# Per-metric display scaling (CU-108): metric key → (display unit, multiply factor).
# The base unit still comes from the registry (``rec.unit``); this one table only
# chooses a more legible display prefix for metrics whose canonical value sits at an
# awkward magnitude. NEDT is milli-Kelvin-scale, so 0.045 K reads far better as 45 mK.
# A metric with no entry is shown in its registry unit unchanged.
_METRIC_DISPLAY_SCALE: Final[dict[str, tuple[str, float]]] = {
    "nedt_K": ("mK", 1000.0),
}


def scale_for_display(metric_key: str, value: float, unit: str) -> tuple[float, str]:
    """Return *(value, unit)* rescaled to the metric's preferred display prefix (CU-108).

    Consults the single :data:`_METRIC_DISPLAY_SCALE` table. Metrics with no entry
    are returned unchanged (the registry unit is the default), so only opted-in
    metrics — NEDT today — rescale. The scaled unit string lives here, never in a
    widget (R-UNITS, GUI plan §4.6).
    """
    scale = _METRIC_DISPLAY_SCALE.get(metric_key)
    if scale is None:
        return value, unit
    display_unit, factor = scale
    return value * factor, display_unit


def format_metric_value(value: float, unit: str) -> str:
    """Render a metric *value* with its *unit* suffix (R-UNITS).

    Four significant figures (``:.4g``) keep both a large SNR (``616.0``) and a
    small NEDT (``0.04463``) readable. A dimensional unit is appended; a bare unit
    (:data:`_BARE_UNITS`) is omitted so the badge reads ``616`` not
    ``616 dimensionless``.
    """
    text = f"{value:.4g}"
    if unit and unit not in _BARE_UNITS:
        return f"{text} {unit}"
    return text


def metric_failure_reason(result: ChainResult, metric_key: str) -> str | None:
    """Return a structured ``failure_reason`` for *metric_key*, or ``None``.

    Reads the metric's result object from the public ``result.stage_outputs``
    surface (``stage_outputs["performance"][…]``) and returns its
    ``failure_reason`` when set (Rule 17 carve-out). ``None`` means the metric
    carries no named failure — the caller then shows a generic unavailable state.
    """
    output_key = _FAILURE_RESULT_KEY.get(metric_key)
    if output_key is None:
        return None
    performance = result.stage_outputs.get("performance", {})
    obj = performance.get(output_key)
    reason = getattr(obj, "failure_reason", None)
    return str(reason) if reason else None


def badge_display(result: ChainResult, metric_key: str) -> tuple[str, str | None]:
    """Compute a badge's ``(value_text, failure_reason)`` for *metric_key*.

    Returns one of three shapes, all honest (never a blank, never a fake number):

    * ``(value_text, None)`` — the metric is present and finite; ``value_text``
      carries the value and its unit.
    * ``(NOT_AVAILABLE, reason)`` — the metric is present but non-finite (a
      result-typed failure); ``reason`` is its ``failure_reason`` when one exists,
      else a generic "unavailable" note.
    * ``(NOT_AVAILABLE, "not computed for this run")`` — the metric is absent from
      ``metrics`` (a regime that did not populate it).

    Units come from :meth:`ChainResult.metric_records` (registry-sourced), so the
    widget never hardcodes a unit string (R-UNITS, GUI plan §4.6).
    """
    records = {rec.name: rec for rec in result.metric_records()}
    rec = records.get(metric_key)
    if rec is None:
        return NOT_AVAILABLE, "not computed for this run"
    if not math.isfinite(rec.value):
        reason = metric_failure_reason(result, metric_key)
        return NOT_AVAILABLE, reason or "unavailable (non-finite result)"
    scaled_value, display_unit = scale_for_display(metric_key, rec.value, rec.unit)
    return format_metric_value(scaled_value, display_unit), None


__all__ = [
    "BADGE_METRICS",
    "BADGE_KEYS",
    "NOT_AVAILABLE",
    "format_metric_value",
    "scale_for_display",
    "metric_failure_reason",
    "badge_display",
]
