"""Scene-class → default metric relevance — the one declarative map (guardrail G3).

``docs/plans/Geometry_Flexibility_Plan.md`` §3.5 guardrail **G3** is explicit:
scene-class conditioning is **data, not scattered branches**.  Per-metric
``if scene_class == ...`` tests inside ``performance/`` modules are
review-blocking.  This module is that data — a single map consulted **once**
per chain run by :class:`~radiant.performance.stage.PerformanceStage`, feeding
the *defaults* of the Gap 96 selection machinery
(:mod:`radiant.performance.metric_selection`).

What it changes and what it does not
------------------------------------
The map only moves the **default** relevance of individual metrics.  It never
touches the override semantics: an analyst who explicitly sets a
``performance.metrics.*`` group flag gets that group verbatim, exactly as
before.  The gate is parameter *provenance* — a group is conditioned only
while its flag is still at :attr:`~radiant.core.parameters.Provenance.DEFAULT`.
The stage resolves that and hands the result to :func:`suppressed_metrics`;
nothing here reads a ``ParameterSet``.

Physics never consults this map (ADR-0011 decision 8): the scene class drives
defaults, metric relevance, validation, and GUI composition only.  Every
radiometric quantity stays continuous in the real inputs.

The discriminator is the **target** band
----------------------------------------
The nine scene classes are ``"<observer>_to_<target>"``, but for *these*
metrics the observer band is not the discriminator — the target band is.  GSD,
ground range, swath width, access rate, the ground projection of the
diffraction limit, the pushbroom dwell limit, and NIIRS/GIQE are all defined
by projecting the sample footprint onto **the target's ground plane** through
``incidence_angle_rad ∈ [0, π/2)``.  A ground-observing airborne sensor and a
ground-observing spaceborne sensor both have a ground plane to project onto; an
air or space *target* has none, whichever band the observer sits in.  The map
is therefore authored once per target band (:data:`OFF_BY_TARGET_BAND`) and
expanded to the full nine-class table (:data:`SCENE_RELEVANCE`) so the
published surface is still an exhaustive, auditable class → relevance map.

Zero drift
----------
For every ``*_to_ground`` class the off-set contains **only the target-plane
metrics introduced by this same phase** — keys that did not exist before — so
a ground-target scene's default metric selection is bit-identical to today's.
The same holds when no scene class is published at all (a partial fixture that
runs ``PerformanceStage`` without ``GeometryStage``): :func:`default_off_metrics`
falls back to the ground rule.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from radiant.performance.errors import PerformanceValidationError
from radiant.performance.metric_selection import ALL_GROUPED_METRICS, group_of

__all__ = [
    "ALTITUDE_BANDS",
    "GROUND_PROJECTION_METRICS",
    "OFF_BY_TARGET_BAND",
    "SCENE_CLASS_KEYS",
    "SCENE_RELEVANCE",
    "TARGET_PLANE_METRICS",
    "default_off_metrics",
    "suppressed_metrics",
    "target_band_of",
]

#: Altitude bands, low to high.  Mirrors ``radiant.geometry.scene_class``'s
#: ``ALTITUDE_BANDS``; declared locally because a physics stage may not import
#: another physics stage (Rule 11).  ``tests/integration/test_scene_relevance_chain.py``
#: (``TestDeclaredBandsMatchGeometry``) asserts the two agree — that test lives
#: above the package seam, where crossing it is legal — so drift fails CI rather
#: than silently mis-keying.
ALTITUDE_BANDS: Final[tuple[str, ...]] = ("ground", "air", "space")

#: The nine ``"<observer>_to_<target>"`` class keys, in the same order the
#: geometry stage builds them.
SCENE_CLASS_KEYS: Final[tuple[str, ...]] = tuple(
    f"{observer}_to_{target}" for observer in ALTITUDE_BANDS for target in ALTITUDE_BANDS
)

#: Metrics that project the sample footprint onto the target's ground plane.
#: Meaningless for an air or space target — there is no ground plane at the
#: target, and ``incidence_angle_rad`` is not even in ``[0, π/2)`` for an
#: up-looking line of sight.
GROUND_PROJECTION_METRICS: Final[frozenset[str]] = frozenset(
    {
        "gsd_cross_track_m",
        "gsd_along_track_m",
        "gsd_geometric_mean_m",
        "ground_range_m",
        "swath_width_m",
        "access_rate_m2_s",
        "diffraction_limit_ground_m",
        "max_integration_time_s",
        "niirs",
        "niirs_extrapolated",
    }
)

#: The non-ground counterpart of GSD (Rule 19 module
#: :mod:`radiant.performance.target_plane_sample_distance`).  Off by default for
#: a ground target, where GSD is the right answer and these would be a second,
#: redundant sample-distance family.
TARGET_PLANE_METRICS: Final[frozenset[str]] = frozenset(
    {
        "target_plane_sample_distance_x_m",
        "target_plane_sample_distance_y_m",
        "target_plane_sample_distance_geometric_mean_m",
    }
)

#: **The map.**  Target altitude band → metrics whose *default* relevance is
#: off.  Angular-resolution metrics (``diffraction_limit_angular_urad``), the
#: sampling parameter Q, the sampling-regime code, and every radiometric,
#: spatial-MTF and saturation metric are absent from every off-set: they are
#: band-independent and stay on for all nine classes.
OFF_BY_TARGET_BAND: Final[Mapping[str, frozenset[str]]] = {
    "ground": TARGET_PLANE_METRICS,
    "air": GROUND_PROJECTION_METRICS,
    "space": GROUND_PROJECTION_METRICS,
}

#: The nine-class expansion of :data:`OFF_BY_TARGET_BAND` — the published,
#: exhaustive scene-class → default-off-metrics table.
SCENE_RELEVANCE: Final[Mapping[str, frozenset[str]]] = {
    key: OFF_BY_TARGET_BAND[key.split("_to_")[1]] for key in SCENE_CLASS_KEYS
}


def _validate_map() -> None:
    """Import-time defence in depth: every metric named here must be grouped.

    A typo or a renamed metric would otherwise silently suppress nothing (or
    fail later inside :func:`suppressed_metrics`' ``group_of`` lookup).  Rule 16
    — validate before compute, at the earliest moment the error is knowable.
    """
    named = GROUND_PROJECTION_METRICS | TARGET_PLANE_METRICS
    unknown = named - ALL_GROUPED_METRICS
    if unknown:
        raise PerformanceValidationError(
            f"scene_relevance names metric(s) unknown to the Gap 96 taxonomy: "
            f"{sorted(unknown)}. Every metric in a relevance off-set must be "
            "registered in radiant.performance.registry.METRIC_SPECS and assigned "
            "a group in radiant.performance.metric_selection.METRIC_GROUPS."
        )


_validate_map()


def target_band_of(scene_class: str) -> str:
    """Return the target altitude band of *scene_class* (``"ground_to_air"`` → ``"air"``).

    Raises
    ------
    PerformanceValidationError
        If *scene_class* is not one of the nine class keys.
    """
    if scene_class not in SCENE_RELEVANCE:
        raise PerformanceValidationError(
            f"Unknown scene class {scene_class!r}. Expected one of: "
            f"{', '.join(SCENE_CLASS_KEYS)}."
        )
    return scene_class.split("_to_")[1]


def default_off_metrics(scene_class: str | None) -> frozenset[str]:
    """Metrics whose *default* relevance is off for *scene_class*.

    Parameters
    ----------
    scene_class:
        The label ``GeometryStage`` published as
        ``stage_outputs["geometry"]["scene_class"]``, or ``None`` when no
        geometry stage ran.  ``None`` (and only ``None``) falls back to the
        ground-target rule, which reproduces today's default selection exactly.

    Raises
    ------
    PerformanceValidationError
        If *scene_class* is a non-``None`` string that is not a known class —
        a published label the metric layer cannot interpret is a contract
        break, not something to guess at (Rule 17: no silent fallback).
    """
    if scene_class is None:
        return OFF_BY_TARGET_BAND["ground"]
    return OFF_BY_TARGET_BAND[target_band_of(scene_class)]


def suppressed_metrics(
    scene_class: str | None,
    groups_at_default: frozenset[str],
) -> frozenset[str]:
    """The off-set of *scene_class*, restricted to groups the analyst left alone.

    Parameters
    ----------
    scene_class:
        As for :func:`default_off_metrics`.
    groups_at_default:
        Names of the metric groups whose ``performance.metrics.*`` flag is
        still at ``Provenance.DEFAULT``.  A metric is suppressed only when its
        own group is in this set — explicitly selecting a group always wins,
        which is the Gap 96 override semantics, unchanged.
    """
    return frozenset(
        metric
        for metric in default_off_metrics(scene_class)
        if group_of(metric) in groups_at_default
    )
