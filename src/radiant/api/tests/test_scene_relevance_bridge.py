"""The ``radiant.api.scene_relevance`` bridge re-exports, nothing more (guardrail G3).

The GUI may not import ``radiant.performance`` (import-linter contract), so the
scene-class → default-off-metrics map reaches the view layer through this bridge.
The contract these tests pin down:

* every name is the **same object** as the physics-side one — a re-export, not a
  transcribed copy that could drift from the map the chain actually applies (G3:
  the conditioning is data in exactly one place);
* ``__all__`` names exactly what the module re-exports;
* the re-exported callables behave identically through either import path.
"""

from __future__ import annotations

import pytest

from radiant.api import scene_relevance as bridge
from radiant.performance import scene_relevance as source


class TestReExportIdentity:
    def test_every_public_name_is_the_same_object(self) -> None:
        """Each ``__all__`` name is literally the physics-side object (no copy)."""
        for name in bridge.__all__:
            assert getattr(bridge, name) is getattr(source, name), name

    def test_all_lists_exactly_the_documented_surface(self) -> None:
        """The bridge publishes the map, the class keys, and the two lookups."""
        assert set(bridge.__all__) == {
            "OFF_BY_TARGET_BAND",
            "SCENE_CLASS_KEYS",
            "SCENE_RELEVANCE",
            "default_off_metrics",
            "target_band_of",
        }

    def test_bridge_declares_no_data_of_its_own(self) -> None:
        """No second table: every public attribute came from the source module."""
        own = {
            name
            for name, value in vars(bridge).items()
            if not name.startswith("_") and getattr(source, name, None) is not value
        }
        assert own == set()


class TestBehaviourThroughTheBridge:
    def test_nine_class_keys(self) -> None:
        """The published taxonomy is the full 3 × 3 observer × target grid."""
        assert len(bridge.SCENE_CLASS_KEYS) == 9
        assert "ground_to_air" in bridge.SCENE_CLASS_KEYS
        assert set(bridge.SCENE_RELEVANCE) == set(bridge.SCENE_CLASS_KEYS)

    def test_ground_target_turns_off_the_target_plane_family(self) -> None:
        """A ground target keeps GSD and drops the target-plane sample distances."""
        off = bridge.default_off_metrics("space_to_ground")
        assert "target_plane_sample_distance_x_m" in off
        assert "gsd_geometric_mean_m" not in off

    def test_air_target_turns_off_the_ground_projection_family(self) -> None:
        """An air target has no ground plane to project onto — GSD/NIIRS go off."""
        off = bridge.default_off_metrics("air_to_air")
        assert "gsd_geometric_mean_m" in off
        assert "niirs" in off
        assert "target_plane_sample_distance_x_m" not in off

    def test_target_band_of_matches_the_class_suffix(self) -> None:
        """``target_band_of`` reads the target half of the class key."""
        assert bridge.target_band_of("ground_to_space") == "space"
        assert bridge.target_band_of("space_to_ground") == "ground"

    def test_unknown_class_raises_through_the_bridge(self) -> None:
        """A label the metric layer cannot interpret is an error, not a guess (Rule 17)."""
        with pytest.raises(Exception, match="Unknown scene class"):
            bridge.target_band_of("sea_to_ground")
