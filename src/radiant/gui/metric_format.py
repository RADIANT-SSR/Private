"""Presentation helpers for the performance-metric cards + readout (arch doc §4.4/§4.5).

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
from typing import TYPE_CHECKING, Any, Final

from radiant.api.metric_groups import group_of

if TYPE_CHECKING:
    from collections.abc import Iterable

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

# (taxonomy group key, display heading) in the Performance readout's *section order*
# (Windows-deployment finding 12: the flat ~30-metric alphabetical dump was unusable —
# geometric/sampling first, then spatial, then radiometric/interpretability, saturation
# last). The keys are the Gap-96 metric-group taxonomy names
# (:mod:`radiant.api.metric_groups` — the owner-ratified single source of the
# metric → group partition, CI-enforced to cover the registry exactly), so a newly
# registered metric lands in the right section automatically. The headings are shared
# with the Metric-selection card (:mod:`.widgets.performance_metrics_form`), so a
# group's checkbox and its readout section read identically.
METRIC_GROUP_HEADINGS: Final[tuple[tuple[str, str], ...]] = (
    ("sampling", "Sampling / geometry"),
    ("spatial_mtf", "Spatial / MTF"),
    ("radiometric", "Radiometric"),
    ("interpretability", "Interpretability"),
    ("saturation", "Saturation"),
)

# Fallback section for a metric key the taxonomy does not know (defensive — the
# partition test makes this unreachable for registry metrics; a foreign key still
# renders rather than vanishing).
UNGROUPED_HEADING: Final[str] = "Other"

# Human display labels for the metric readout (owner feedback 2026-07-25: raw registry
# keys — ``gsd_cross_track_m``, ``mtf_folded_at_nyquist`` — read as a wall of text; every
# other screen shows human labels). Presentation-only: the *unit* still comes from the
# registry via ``metric_records()`` (R-UNITS), never from this table — a label therefore
# never repeats the unit. **Insertion order is meaningful**: within a group section,
# rows render in this table's order (the registry's physics reading order), not
# alphabetically. A test asserts every taxonomy metric has an entry, so a newly
# registered metric without a label fails CI instead of silently rendering its raw key.
METRIC_DISPLAY_LABELS: Final[dict[str, str]] = {
    # Radiometric
    "snr": "SNR",
    "contrast_snr": "Contrast SNR",
    "scnr": "SCNR",
    "detection_range_m": "Detection range",
    "nedt_K": "NEDT",
    # Interpretability
    "mrt_at_nyquist_K": "MRT @ Nyquist",
    "niirs": "NIIRS",
    "niirs_extrapolated": "NIIRS (extrapolated)",
    # Spatial / MTF
    "fwhm_x_m": "FWHM (x)",
    "fwhm_y_m": "FWHM (y)",
    "rer": "RER",
    "ee_1x1": "Ensquared energy 1×1",
    "ee_3x3": "Ensquared energy 3×3",
    "mtf_at_nyquist": "MTF @ Nyquist",
    "strehl": "Strehl ratio",
    "strehl_marechal": "Strehl (Maréchal)",
    "mtf_system_at_nyquist_x": "System MTF @ Nyq (x)",
    "mtf_system_at_nyquist_y": "System MTF @ Nyq (y)",
    "mtf_folded_at_nyquist": "Folded MTF @ Nyquist",
    "alias_fraction_at_nyquist": "Alias fraction @ Nyquist",
    # Sampling / geometry
    "gsd_cross_track_m": "GSD (cross-track)",
    "gsd_along_track_m": "GSD (along-track)",
    "gsd_geometric_mean_m": "GSD (geometric mean)",
    "target_plane_sample_distance_x_m": "Target-plane sample distance (x)",
    "target_plane_sample_distance_y_m": "Target-plane sample distance (y)",
    "target_plane_sample_distance_geometric_mean_m": (
        "Target-plane sample distance (geometric mean)"
    ),
    "ground_range_m": "Ground range",
    "swath_width_m": "Swath width",
    "access_rate_m2_s": "Access rate",
    "q_center": "Q (band center)",
    "q_min": "Q (min λ)",
    "q_max": "Q (max λ)",
    "sampling_regime_code": "Sampling regime",
    "diffraction_limit_angular_urad": "Diffraction limit (angular)",
    "diffraction_limit_ground_m": "Diffraction limit (ground)",
    "max_integration_time_s": "Max integration time",
    # Saturation
    "well_margin_dB": "Well margin",
    "adc_margin_dB": "ADC margin",
    "dynamic_range_dB": "Dynamic range",
}


def metric_display_label(metric_key: str) -> str:
    """The human display label for *metric_key* (the raw key when unlabelled).

    The raw-key fallback keeps a foreign / not-yet-labelled metric visible (never a
    blank row); the labels test keeps the fallback unreachable for registry metrics.
    """
    return METRIC_DISPLAY_LABELS.get(metric_key, metric_key)


def grouped_metric_records(records: Iterable[Any]) -> tuple[tuple[str, tuple[Any, ...]], ...]:
    """Partition metric *records* into the labeled display sections (finding 12).

    Takes the (duck-typed, ``.name``-carrying) records from
    :meth:`ChainResult.metric_records` and returns ``(heading, records)`` sections in
    :data:`METRIC_GROUP_HEADINGS` order, each record placed by the Gap-96 taxonomy
    (:func:`radiant.api.metric_groups.group_of`). Within a section, records follow the
    :data:`METRIC_DISPLAY_LABELS` insertion order (the registry's physics reading
    order — owner feedback 2026-07-25: alphabetical scattered related rows), with
    unlabelled records trailing in their incoming order; empty sections are dropped.
    A record whose key the taxonomy does not know lands in a trailing
    :data:`UNGROUPED_HEADING` section — shown, never silently dropped. Pure and
    Qt-free, so the section contract is unit-tested directly.
    """
    display_rank = {key: i for i, key in enumerate(METRIC_DISPLAY_LABELS)}
    unranked = len(display_rank)
    buckets: dict[str, list[Any]] = {key: [] for key, _ in METRIC_GROUP_HEADINGS}
    ungrouped: list[Any] = []
    for rec in records:
        try:
            buckets[group_of(rec.name)].append(rec)
        except KeyError:
            ungrouped.append(rec)
    for bucket in buckets.values():
        bucket.sort(key=lambda rec: display_rank.get(rec.name, unranked))
    sections = [
        (heading, tuple(buckets[key])) for key, heading in METRIC_GROUP_HEADINGS if buckets[key]
    ]
    if ungrouped:
        sections.append((UNGROUPED_HEADING, tuple(ungrouped)))
    return tuple(sections)


def metric_value_display(result: ChainResult, rec: Any) -> str:
    """The value+unit text for a metric record, or its named failure (Rule 17 carve-out).

    A finite value renders through :func:`format_metric_value` (value + registry unit,
    R-UNITS); a non-finite value renders as ``n/a (<failure_reason>)`` — the
    ``failure_reason`` from the metric's result object when one exists, else a generic
    non-finite note. Never a bare ``nan``, never a blank. (Relocated from the old
    ``OutputsReadout`` metrics path so every metric surface formats identically.)
    """
    if math.isfinite(rec.value):
        return format_metric_value(rec.value, rec.unit)
    reason = metric_failure_reason(result, rec.name) or "unavailable (non-finite result)"
    return f"{NOT_AVAILABLE} ({reason})"


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
    "METRIC_DISPLAY_LABELS",
    "METRIC_GROUP_HEADINGS",
    "NOT_AVAILABLE",
    "UNGROUPED_HEADING",
    "format_metric_value",
    "grouped_metric_records",
    "metric_display_label",
    "metric_value_display",
    "scale_for_display",
    "metric_failure_reason",
    "badge_display",
]
