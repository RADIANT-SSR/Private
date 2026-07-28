"""Tests for the scene-class → default metric relevance map (guardrail G3).

Level 0: the map is pure data and the two accessors are pure set algebra over
it — no chain state required.

The load-bearing property is **zero drift**: for every ``*_to_ground`` class
the default selection must be exactly today's, which is asserted here as an
exact list equality against the selection resolved with an empty suppression
set (the pre-Phase-3 behaviour).
"""

from __future__ import annotations

import pytest

from radiant.performance.errors import PerformanceValidationError
from radiant.performance.metric_selection import (
    ALL_GROUPED_METRICS,
    METRIC_GROUPS,
    group_of,
    resolve_selection,
)
from radiant.performance.scene_relevance import (
    ALTITUDE_BANDS,
    GROUND_PROJECTION_METRICS,
    OFF_BY_TARGET_BAND,
    SCENE_CLASS_KEYS,
    SCENE_RELEVANCE,
    TARGET_PLANE_METRICS,
    default_off_metrics,
    suppressed_metrics,
    target_band_of,
)

ALL_GROUPS = frozenset(METRIC_GROUPS)


class TestMapIntegrity:
    @pytest.mark.level0
    def test_map_covers_exactly_the_nine_classes(self) -> None:
        assert set(SCENE_RELEVANCE) == set(SCENE_CLASS_KEYS)
        assert len(SCENE_CLASS_KEYS) == 9

    @pytest.mark.level0
    def test_every_named_metric_is_registered_and_grouped(self) -> None:
        """A typo in the map would otherwise suppress nothing, silently."""
        named = GROUND_PROJECTION_METRICS | TARGET_PLANE_METRICS
        assert named <= ALL_GROUPED_METRICS

    @pytest.mark.level0
    def test_target_band_is_the_discriminator(self) -> None:
        """All three observer bands share one off-set per target band."""
        for target in ALTITUDE_BANDS:
            off_sets = {SCENE_RELEVANCE[f"{obs}_to_{target}"] for obs in ALTITUDE_BANDS}
            assert len(off_sets) == 1

    @pytest.mark.level0
    def test_target_band_of_parses_every_class(self) -> None:
        for observer in ALTITUDE_BANDS:
            for target in ALTITUDE_BANDS:
                assert target_band_of(f"{observer}_to_{target}") == target

    @pytest.mark.level0
    def test_unknown_class_is_rejected_not_guessed(self) -> None:
        """Rule 17: a label the metric layer cannot interpret is an error."""
        with pytest.raises(PerformanceValidationError, match="Unknown scene class"):
            default_off_metrics("orbit_to_seabed")

    @pytest.mark.level0
    def test_angular_and_radiometric_metrics_are_never_suppressed(self) -> None:
        """Only ground-projection / target-plane families ever appear in an off-set."""
        always_on = {
            "snr",
            "contrast_snr",
            "scnr",
            "nedt_K",
            "detection_range_m",
            "rer",
            "mtf_at_nyquist",
            "q_center",
            "q_min",
            "q_max",
            "sampling_regime_code",
            "diffraction_limit_angular_urad",
            "mrt_at_nyquist_K",
            "well_margin_dB",
        }
        for off in SCENE_RELEVANCE.values():
            assert not (always_on & off)


class TestZeroDriftForGroundTargets:
    """Anchor 1: a ground-target scene's default metric set == today's set."""

    @pytest.mark.level0
    @pytest.mark.parametrize("observer", ALTITUDE_BANDS)
    def test_ground_target_default_selection_is_exactly_todays(self, observer: str) -> None:
        scene = f"{observer}_to_ground"
        suppressed = suppressed_metrics(scene, ALL_GROUPS)
        surfaced_new, compute_new = resolve_selection(ALL_GROUPS, suppressed)

        # The pre-Phase-3 resolution, minus the metrics this phase introduced
        # (which did not exist then and are off for ground targets).
        surfaced_old, compute_old = resolve_selection(ALL_GROUPS)
        expected_surfaced = surfaced_old - TARGET_PLANE_METRICS
        expected_compute = compute_old - TARGET_PLANE_METRICS

        assert sorted(surfaced_new) == sorted(expected_surfaced)
        assert sorted(compute_new) == sorted(expected_compute)

    @pytest.mark.level0
    def test_ground_off_set_contains_only_new_metrics(self) -> None:
        """Nothing that existed before Phase 3 is turned off for a ground target."""
        assert default_off_metrics("space_to_ground") == TARGET_PLANE_METRICS

    @pytest.mark.level0
    def test_absent_scene_class_falls_back_to_the_ground_rule(self) -> None:
        """Partial fixtures without GeometryStage keep today's behaviour."""
        assert default_off_metrics(None) == OFF_BY_TARGET_BAND["ground"]


class TestNonGroundTargets:
    @pytest.mark.level0
    @pytest.mark.parametrize("target", ["air", "space"])
    def test_ground_projection_metrics_default_off(self, target: str) -> None:
        surfaced, _ = resolve_selection(
            ALL_GROUPS, suppressed_metrics(f"ground_to_{target}", ALL_GROUPS)
        )
        for metric in (
            "gsd_cross_track_m",
            "gsd_along_track_m",
            "gsd_geometric_mean_m",
            "ground_range_m",
            "swath_width_m",
            "access_rate_m2_s",
            "niirs",
            "niirs_extrapolated",
            "diffraction_limit_ground_m",
            "max_integration_time_s",
        ):
            assert metric not in surfaced

    @pytest.mark.level0
    @pytest.mark.parametrize("target", ["air", "space"])
    def test_angular_resolution_stays_on(self, target: str) -> None:
        surfaced, _ = resolve_selection(
            ALL_GROUPS, suppressed_metrics(f"air_to_{target}", ALL_GROUPS)
        )
        assert "diffraction_limit_angular_urad" in surfaced
        assert "q_center" in surfaced
        assert "sampling_regime_code" in surfaced

    @pytest.mark.level0
    @pytest.mark.parametrize("target", ["air", "space"])
    def test_target_plane_sample_distance_is_on(self, target: str) -> None:
        surfaced, _ = resolve_selection(
            ALL_GROUPS, suppressed_metrics(f"space_to_{target}", ALL_GROUPS)
        )
        assert surfaced >= TARGET_PLANE_METRICS

    @pytest.mark.level0
    def test_suppressed_metrics_are_still_computed_when_a_dependency_needs_them(
        self,
    ) -> None:
        """Suppression is a *surfacing* rule; the closure is unaffected.

        With only the interpretability group explicitly enabled (so its flag is
        not at default and NIIRS survives), the GSD prerequisites it needs are
        still computed even though the sampling group's map entry suppresses
        them.
        """
        suppressed = suppressed_metrics("ground_to_air", frozenset({"sampling"}))
        surfaced, compute = resolve_selection(ALL_GROUPS, suppressed)
        assert "niirs" in surfaced  # interpretability was not at default
        assert "gsd_along_track_m" not in surfaced
        assert "gsd_along_track_m" in compute


class TestOverrideSemanticsUnchanged:
    @pytest.mark.level0
    def test_explicitly_selected_group_is_never_conditioned(self) -> None:
        """A group the analyst set explicitly is exempt from the map."""
        # No group at default ⇒ nothing suppressed, whatever the scene class.
        assert suppressed_metrics("ground_to_space", frozenset()) == frozenset()

    @pytest.mark.level0
    def test_suppression_is_restricted_to_the_metrics_own_group(self) -> None:
        """Sampling at default, interpretability explicit ⇒ NIIRS survives."""
        suppressed = suppressed_metrics("air_to_air", frozenset({"sampling"}))
        assert "niirs" not in suppressed
        assert "gsd_cross_track_m" in suppressed
        assert all(group_of(m) == "sampling" for m in suppressed)

    @pytest.mark.level0
    def test_disabled_group_wins_over_an_on_by_map_metric(self) -> None:
        """Turning sampling off removes the target-plane metrics too."""
        enabled = ALL_GROUPS - {"sampling"}
        surfaced, _ = resolve_selection(
            enabled, suppressed_metrics("ground_to_space", frozenset({"interpretability"}))
        )
        assert not (TARGET_PLANE_METRICS & surfaced)
