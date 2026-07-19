"""Tests for metric-group taxonomy and dependency closure (Gap 96).

Level 0: the group partition and the transitive dependency closure are pure
set algebra over the registry — no chain state required.

Covers the hard-requirement closure cases from Gap 96:
  * enabling NIIRS with the Radiometric/Sampling groups off still *computes*
    snr/rer/gsd (they are in the closure) even though they are not surfaced;
  * disabling a group removes exactly that group's metrics from the surfaced
    set;
  * the group→metric map partitions the registry exactly (drift guard).
"""

from __future__ import annotations

import pytest

from radiant.performance.metric_selection import (
    ALL_GROUPED_METRICS,
    GROUP_PARAMS,
    METRIC_GROUPS,
    dependency_closure,
    group_of,
    resolve_selection,
)
from radiant.performance.registry import METRIC_SPECS

ALL_GROUPS = frozenset(METRIC_GROUPS)


# ---------------------------------------------------------------------------
# Taxonomy integrity — the partition and its lock-step with the registry/schema
# ---------------------------------------------------------------------------


class TestTaxonomyIntegrity:
    @pytest.mark.level0
    def test_groups_partition_registry_exactly(self) -> None:
        """Every registered metric is in exactly one group; no extras.

        This is the drift guard: adding a MetricSpec without assigning it a
        group (or grouping a non-existent metric) fails here.
        """
        registered = set(METRIC_SPECS)
        assert registered == ALL_GROUPED_METRICS, (
            "METRIC_GROUPS must partition the registry exactly. "
            f"Only in registry: {sorted(registered - ALL_GROUPED_METRICS)}; "
            f"only in groups: {sorted(ALL_GROUPED_METRICS - registered)}"
        )

    @pytest.mark.level0
    def test_groups_are_disjoint(self) -> None:
        """No metric belongs to two groups (the union size equals the sum)."""
        total = sum(len(members) for members in METRIC_GROUPS.values())
        assert total == len(ALL_GROUPED_METRICS)

    @pytest.mark.level0
    def test_group_params_match_group_names(self) -> None:
        """Every group has exactly one enabling parameter and vice versa."""
        assert set(GROUP_PARAMS) == set(METRIC_GROUPS)
        # Parameter dot-paths follow the performance.metrics.<group> convention.
        for group, param in GROUP_PARAMS.items():
            assert param == f"performance.metrics.{group}"

    @pytest.mark.level0
    def test_group_of_round_trips(self) -> None:
        for group, members in METRIC_GROUPS.items():
            for metric in members:
                assert group_of(metric) == group

    @pytest.mark.level0
    def test_group_of_unknown_raises(self) -> None:
        with pytest.raises(KeyError):
            group_of("not_a_metric")

    @pytest.mark.level0
    def test_owner_ratified_assignments(self) -> None:
        """Owner decision 2026-07-18: mrt→interpretability, gsd→sampling."""
        assert group_of("mrt_at_nyquist_K") == "interpretability"
        assert group_of("gsd_along_track_m") == "sampling"
        assert group_of("gsd_cross_track_m") == "sampling"


# ---------------------------------------------------------------------------
# Dependency closure — the transitive walk over requires_metrics
# ---------------------------------------------------------------------------


class TestDependencyClosure:
    @pytest.mark.level0
    def test_closure_is_superset_of_seed(self) -> None:
        seed = frozenset({"niirs"})
        assert seed <= dependency_closure(seed)

    @pytest.mark.level0
    def test_niirs_pulls_in_snr_rer_gsd(self) -> None:
        """NIIRS's registry prerequisites are all in its closure."""
        closure = dependency_closure(frozenset({"niirs"}))
        for req in ("snr", "rer", "gsd_along_track_m", "gsd_cross_track_m"):
            assert req in closure

    @pytest.mark.level0
    def test_mrt_pulls_in_nedt_and_mtf(self) -> None:
        closure = dependency_closure(frozenset({"mrt_at_nyquist_K"}))
        assert "nedt_K" in closure
        assert "mtf_at_nyquist" in closure

    @pytest.mark.level0
    def test_leaf_metric_closure_is_itself(self) -> None:
        """snr has no metric prerequisites → closure is the singleton."""
        assert dependency_closure(frozenset({"snr"})) == frozenset({"snr"})

    @pytest.mark.level0
    def test_empty_seed_empty_closure(self) -> None:
        assert dependency_closure(frozenset()) == frozenset()

    @pytest.mark.level0
    def test_closure_of_full_set_is_full_set(self) -> None:
        """Closure over every registered metric adds nothing (deps are internal)."""
        allm = frozenset(METRIC_SPECS)
        assert dependency_closure(allm) == allm


# ---------------------------------------------------------------------------
# resolve_selection — surfaced vs compute, the Gap-96 contract
# ---------------------------------------------------------------------------


class TestResolveSelection:
    @pytest.mark.level0
    def test_all_groups_on_surfaces_everything(self) -> None:
        surfaced, compute = resolve_selection(ALL_GROUPS)
        assert surfaced == ALL_GROUPED_METRICS
        assert compute == ALL_GROUPED_METRICS  # closure adds nothing

    @pytest.mark.level0
    def test_all_groups_off_computes_nothing(self) -> None:
        surfaced, compute = resolve_selection(frozenset())
        assert surfaced == frozenset()
        assert compute == frozenset()

    @pytest.mark.level0
    def test_interpretability_only_computes_but_hides_prereqs(self) -> None:
        """Enable only Interpretability: niirs surfaced; snr/rer/gsd computed,
        not surfaced (the core Gap-96 closure case)."""
        surfaced, compute = resolve_selection(frozenset({"interpretability"}))

        # Surfaced = exactly the interpretability group.
        assert surfaced == METRIC_GROUPS["interpretability"]
        assert "niirs" in surfaced

        # Prerequisites are computed (in the closure) but NOT surfaced.
        for prereq in ("snr", "rer", "gsd_along_track_m", "gsd_cross_track_m"):
            assert prereq in compute
            assert prereq not in surfaced

    @pytest.mark.level0
    def test_compute_is_always_superset_of_surfaced(self) -> None:
        for group in ALL_GROUPS:
            surfaced, compute = resolve_selection(frozenset({group}))
            assert surfaced <= compute

    @pytest.mark.level0
    def test_disabling_a_group_drops_its_metrics(self) -> None:
        """Turning off Saturation removes exactly its metrics from surfaced."""
        without_sat = ALL_GROUPS - {"saturation"}
        surfaced, _compute = resolve_selection(without_sat)
        assert surfaced.isdisjoint(METRIC_GROUPS["saturation"])
        # And nothing else was dropped.
        assert surfaced == ALL_GROUPED_METRICS - METRIC_GROUPS["saturation"]
