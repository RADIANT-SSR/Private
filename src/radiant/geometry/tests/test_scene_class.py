"""Level-0 tests for the derived scene class (ADR-0011 decision 8).

The class is a *label*: these tests pin the band boundaries (the truth-anchor
table over the nine archetypes plus both boundary altitudes taken exactly),
the optional assertion's raise-on-disagreement behaviour, and the invariant
that matters most — that a scene computes identically whether or not the
assertion is present, because physics never reads the class.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.geometry._schema import ALL_PARAMETERS
from radiant.geometry.errors import GeometrySpecificationError
from radiant.geometry.scene_class import (
    GROUND_CEILING_M,
    SCENE_CLASSES,
    SPACE_FLOOR_M,
    check_scene_class_assertion,
    classify_altitude,
    derive_scene_class,
)
from radiant.geometry.stage import GeometryStage


def make_params(h_sensor: float, **inputs: object) -> ParameterSet:
    ps = ParameterSet(list(ALL_PARAMETERS))
    ps.set("geometry.sensor_altitude_m", h_sensor)
    for name, value in inputs.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


def run_stage(params: ParameterSet) -> dict[str, object]:
    state = ChainState(wavelength_um=np.linspace(3.0, 5.0, 8))
    return dict(GeometryStage().run(state, params).stage_outputs["geometry"])


# ---------------------------------------------------------------------------
# Truth anchor: the band table, including both boundaries taken exactly
# ---------------------------------------------------------------------------


class TestAltitudeBands:
    @pytest.mark.parametrize(
        ("altitude_m", "band"),
        [
            (0.0, "ground"),  # sea level
            (30.0, "ground"),  # a tower
            (999.9999, "ground"),  # just below the ground ceiling
            (GROUND_CEILING_M, "air"),  # 1 km EXACTLY -> air (ground is h < 1 km)
            (1_000.0, "air"),
            (10_000.0, "air"),  # airliner
            (30_000.0, "air"),  # U-2 / balloon
            (99_999.0, "air"),
            (SPACE_FLOOR_M, "air"),  # 100 km EXACTLY -> air (space is h > 100 km)
            (100_000.1, "space"),
            (400_000.0, "space"),  # ISS
            (35_786_000.0, "space"),  # GEO
        ],
    )
    def test_band_table(self, altitude_m: float, band: str) -> None:
        assert classify_altitude(altitude_m) == band

    def test_boundaries_are_the_documented_constants(self) -> None:
        """1 km is a naming convention; 100 km is the h_atm_top (Kármán) value."""
        assert GROUND_CEILING_M == 1.0e3
        assert SPACE_FLOOR_M == 1.0e5

    def test_negative_altitude_raises(self) -> None:
        with pytest.raises(ParameterBoundsError, match="negative"):
            classify_altitude(-1.0)

    def test_non_finite_altitude_raises(self) -> None:
        with pytest.raises(ParameterBoundsError, match="not finite"):
            classify_altitude(math.nan)


class TestNineArchetypes:
    """Truth anchor 4: one archetype per cell of the ADR-0011 3x3 grid."""

    ARCHETYPES = [
        (0.0, 0.0, "ground_to_ground"),  # two towers / lab bench
        (30.0, 10_000.0, "ground_to_air"),  # ground IRST vs airliner
        (30.0, 700_000.0, "ground_to_space"),  # SST site vs LEO satellite
        (10_000.0, 0.0, "air_to_ground"),  # airborne down-look
        (10_000.0, 12_000.0, "air_to_air"),  # air-to-air
        (10_000.0, 700_000.0, "air_to_space"),  # airborne up-look
        (600_000.0, 0.0, "space_to_ground"),  # the v1 baseline
        (600_000.0, 12_000.0, "space_to_air"),  # LEO vs aircraft
        (600_000.0, 35_786_000.0, "space_to_space"),  # LEO -> GEO
    ]

    @pytest.mark.parametrize(("h_sensor", "h_target", "expected"), ARCHETYPES)
    def test_archetype(self, h_sensor: float, h_target: float, expected: str) -> None:
        scene = derive_scene_class(h_sensor, h_target, "down")
        assert scene.key == expected
        assert scene.key in SCENE_CLASSES

    def test_all_nine_classes_are_reachable(self) -> None:
        assert {row[2] for row in self.ARCHETYPES} == set(SCENE_CLASSES)
        assert len(SCENE_CLASSES) == 9

    def test_direction_is_carried_not_rederived(self) -> None:
        """The class carries whatever direction the LOS object derived."""
        for direction in ("down", "up", "level"):
            assert derive_scene_class(1.0e4, 1.0e4, direction).los_direction == direction


# ---------------------------------------------------------------------------
# The optional assertion (CU-093 redundant-entry pattern)
# ---------------------------------------------------------------------------


class TestAssertion:
    def test_unset_skips_the_check(self) -> None:
        derived = derive_scene_class(600_000.0, 0.0, "down")
        check_scene_class_assertion("auto", derived, 600_000.0, 0.0)  # no raise
        check_scene_class_assertion("", derived, 600_000.0, 0.0)  # no raise

    def test_agreeing_assertion_passes(self) -> None:
        derived = derive_scene_class(600_000.0, 0.0, "down")
        check_scene_class_assertion("space_to_ground", derived, 600_000.0, 0.0)

    def test_disagreeing_assertion_raises_naming_both(self) -> None:
        """The wrong-magnitude altitude typo: 600 m entered where 600 km was meant."""
        derived = derive_scene_class(600.0, 0.0, "down")
        with pytest.raises(GeometrySpecificationError) as exc:
            check_scene_class_assertion("space_to_ground", derived, 600.0, 0.0)
        message = str(exc.value)
        assert "space_to_ground" in message  # asserted
        assert "ground_to_ground" in message  # derived
        assert "600" in message  # the offending altitude
        assert exc.value.context["asserted"] == "space_to_ground"
        assert exc.value.context["derived"] == "ground_to_ground"
        assert exc.value.context["geometry.sensor_altitude_m"] == 600.0

    def test_unknown_class_raises_bounds_error(self) -> None:
        derived = derive_scene_class(600_000.0, 0.0, "down")
        with pytest.raises(ParameterBoundsError, match="not a scene class"):
            check_scene_class_assertion("orbit_to_orbit", derived, 600_000.0, 0.0)


# ---------------------------------------------------------------------------
# Stage integration
# ---------------------------------------------------------------------------


class TestStagePublication:
    def test_published_pieces_and_key(self) -> None:
        out = run_stage(make_params(600_000.0))
        assert out["scene_class"] == "space_to_ground"
        assert out["observer_class"] == "space"
        assert out["target_class"] == "ground"
        assert out["los_direction"] == "down"

    def test_uplooking_scene_class(self) -> None:
        out = run_stage(
            make_params(
                30.0,
                geometry__target_altitude_m=10_000.0,
                geometry__path_zenith_rad=0.2,
            )
        )
        assert out["scene_class"] == "ground_to_air"
        assert out["los_direction"] == "up"

    def test_assertion_is_never_required(self) -> None:
        """No user config sets it, and the default resolves inert."""
        params = make_params(600_000.0)
        assert params.get("geometry.scene_class") == "auto"
        run_stage(params)  # no raise

    def test_assertion_disagreement_raises_from_the_stage(self) -> None:
        params = make_params(600.0, geometry__scene_class="space_to_ground")
        with pytest.raises(GeometrySpecificationError, match="scene_class"):
            run_stage(params)

    def test_assertion_does_not_change_any_published_number(self) -> None:
        """ADR-0011 decision 8: the class is a label; asserting it changes nothing."""
        without = run_stage(make_params(600_000.0, geometry__path_zenith_rad=0.4))
        with_assert = run_stage(
            make_params(
                600_000.0,
                geometry__path_zenith_rad=0.4,
                geometry__scene_class="space_to_ground",
            )
        )
        numeric = {
            k: v
            for k, v in without.items()
            if isinstance(v, float) or (isinstance(v, int) and not isinstance(v, bool))
        }
        assert numeric  # the comparison is not vacuous
        for key, value in numeric.items():
            assert with_assert[key] == value, key
