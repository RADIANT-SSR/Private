"""Metric-group taxonomy and dependency-closure resolution (Gap 96).

Selects *which* performance metrics :class:`~radiant.performance.stage.PerformanceStage`
computes and surfaces. The analyst enables/disables coarse metric **groups**
(five boolean flags in :mod:`radiant.performance._schema`); this module turns
that choice into two sets:

* **surfaced** — the metric keys the run emits and the GUI shows. A metric is
  surfaced *iff* its group is enabled.
* **compute** — the transitive closure of ``surfaced`` over the inter-metric
  dependency graph declared in :mod:`radiant.performance.registry`
  (``MetricSpec.requires_metrics``). Enabling NIIRS therefore pulls in
  ``snr``/``rer``/``gsd_*`` even when the Radiometric/Spatial/Sampling groups
  are off; those prerequisites are *computed* but not *surfaced*.

The dependency graph is **not** re-declared here — it is derived from the
registry's ``requires_metrics`` fields (the single source of metric metadata),
so a new inter-metric dependency is picked up automatically. Only the
group→metric partition is declared here, and a test
(``tests/test_metric_selection.py``) asserts it partitions the registry exactly,
catching drift when a metric is added.

Turning a group off truly stops the *computation* of its metrics (and any
warnings they would emit), not merely their display — see Gap 96 and the
gating in :func:`PerformanceStage.run`.
"""

from __future__ import annotations

from collections.abc import Mapping

from radiant.performance.registry import METRIC_SPECS

# Group name → the ``performance.metrics.*`` boolean parameter that enables it.
# Kept in lock-step with the ParameterDefs in ``performance/_schema.py``.
GROUP_PARAMS: Mapping[str, str] = {
    "radiometric": "performance.metrics.radiometric",
    "spatial_mtf": "performance.metrics.spatial_mtf",
    "interpretability": "performance.metrics.interpretability",
    "sampling": "performance.metrics.sampling",
    "saturation": "performance.metrics.saturation",
}

# Explicit metric → group taxonomy. This MUST partition ``METRIC_SPECS`` exactly
# (every registered metric in exactly one group); ``test_metric_selection.py``
# enforces it, so adding a metric to the registry without grouping it fails CI.
#
# Group assignment (owner-ratified 2026-07-18): ``mrt_at_nyquist_K`` →
# Interpretability (a contrast-limited resolution metric); the GSD/geometry
# family → Sampling (matches the registry's "Geometry / sampling" section).
METRIC_GROUPS: Mapping[str, frozenset[str]] = {
    "radiometric": frozenset(
        {
            "snr",
            "contrast_snr",
            "scnr",
            "detection_range_m",
            "nedt_K",
        }
    ),
    "spatial_mtf": frozenset(
        {
            "fwhm_x_m",
            "fwhm_y_m",
            "rer",
            "ee_1x1",
            "ee_3x3",
            "mtf_at_nyquist",
            "strehl",
            "strehl_marechal",
            "mtf_system_at_nyquist_x",
            "mtf_system_at_nyquist_y",
            "mtf_folded_at_nyquist",
            "alias_fraction_at_nyquist",
        }
    ),
    "interpretability": frozenset(
        {
            "niirs",
            "niirs_extrapolated",
            "mrt_at_nyquist_K",
        }
    ),
    "sampling": frozenset(
        {
            "gsd_cross_track_m",
            "gsd_along_track_m",
            "gsd_geometric_mean_m",
            "ground_range_m",
            "swath_width_m",
            "access_rate_m2_s",
            "q_center",
            "q_min",
            "q_max",
            "sampling_regime_code",
            "diffraction_limit_angular_urad",
            "diffraction_limit_ground_m",
            "max_integration_time_s",
        }
    ),
    "saturation": frozenset(
        {
            "well_margin_dB",
            "adc_margin_dB",
            "dynamic_range_dB",
        }
    ),
}

# All metrics known to the taxonomy — the set the surfacing filter is allowed to
# drop (never touches foreign metric keys written outside PerformanceStage).
ALL_GROUPED_METRICS: frozenset[str] = frozenset().union(*METRIC_GROUPS.values())


def group_of(metric: str) -> str:
    """Return the group name owning *metric*.

    Raises
    ------
    KeyError
        If *metric* is not assigned to any group (registry drift — a new
        metric was registered without a group).
    """
    for group, members in METRIC_GROUPS.items():
        if metric in members:
            return group
    raise KeyError(
        f"Metric '{metric}' is not assigned to any group in METRIC_GROUPS. "
        "Add it to radiant.performance.metric_selection.METRIC_GROUPS."
    )


def surfaced_metrics(enabled_groups: frozenset[str]) -> frozenset[str]:
    """Metrics that are surfaced (emitted + shown): union of the enabled groups."""
    surfaced: set[str] = set()
    for group in enabled_groups:
        surfaced |= METRIC_GROUPS.get(group, frozenset())
    return frozenset(surfaced)


def dependency_closure(seed: frozenset[str]) -> frozenset[str]:
    """Transitive closure of *seed* over ``MetricSpec.requires_metrics``.

    Walks the inter-metric dependency graph declared in the registry, adding
    every prerequisite metric reachable from the seed. Robust to cycles (none
    exist today, but the fixed-point walk terminates regardless).
    """
    closure: set[str] = set(seed)
    frontier: set[str] = set(seed)
    while frontier:
        current = frontier.pop()
        spec = METRIC_SPECS.get(current)
        if spec is None:
            continue
        for req in spec.requires_metrics:
            if req not in closure:
                closure.add(req)
                frontier.add(req)
    return frozenset(closure)


def resolve_selection(
    enabled_groups: frozenset[str],
) -> tuple[frozenset[str], frozenset[str]]:
    """Resolve enabled groups into ``(surfaced, compute)`` metric sets.

    ``surfaced`` = union of the enabled groups' metrics (what the run emits).
    ``compute`` = transitive dependency closure of ``surfaced`` (what the stage
    must actually calculate so the surfaced metrics are well-defined).
    ``compute ⊇ surfaced`` always holds.
    """
    surfaced = surfaced_metrics(enabled_groups)
    compute = dependency_closure(surfaced)
    return surfaced, compute
