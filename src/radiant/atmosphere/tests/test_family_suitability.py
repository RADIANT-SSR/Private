"""Unit: the pre-validated bundled-family selector (CU-322).

Level 0 for this module is not an equation but a **correspondence**: every gap
asserted here must be a refusal the chain actually raises for the same query.
Where that is cheap to demonstrate the test does both sides — it asks
:func:`family_suitability` for the gap and then drives the real backend entry
point with the same line of sight and asserts it refuses.  That is what stops
this module drifting into a second, independent opinion about coverage.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere.errors import AtmosphereValidationError
from radiant.atmosphere.family_suitability import (
    family_node_geometry,
    family_suitability,
    select_atmosphere_family,
)
from radiant.atmosphere.interpolated import (
    AtmosphericGeometry,
    GeometryPoint,
    InterpolatedAtmosphere,
)
from radiant.atmosphere.interpolation_coverage import (
    BUNDLED_ATMOSPHERES_DIR,
    BUNDLED_FAMILIES,
    EXPLICIT_DIR_FAMILIES,
    SHIPPED_FAMILIES,
)
from radiant.atmosphere.tabulated import TabulatedAtmosphere
from radiant.core.los_geometry import LineOfSightGeometry


def _family(name: str):  # noqa: ANN202 - ShippedFamily, kept short for readability
    return next(f for f in BUNDLED_FAMILIES if f.name == name)


def _down(h_sensor_m: float, h_tgt_m: float = 0.0, theta_o_rad: float = 0.0):  # noqa: ANN202
    return LineOfSightGeometry(h_tgt=h_tgt_m, h_sensor=h_sensor_m, theta_o=theta_o_rad)


def _up(h_sensor_m: float, h_tgt_m: float, zeta_low_rad: float = 0.0):  # noqa: ANN202
    """Up-looking LOS at lower-endpoint zenith ``zeta_low`` (theta_o = pi - zeta).

    ``zeta_low`` is the zenith of the up-going ray **at the sensor** — exactly
    the coordinate ``uplooking_column_product`` keys a family on. On a spherical
    Earth the two endpoints see different zeniths, so a large ``zeta_low`` with a
    distant target is not a constructible triangle; the scenes here stay inside
    the band the shipped scenarios occupy.
    """
    return LineOfSightGeometry(h_tgt=h_tgt_m, h_sensor=h_sensor_m, theta_o=math.pi - zeta_low_rad)


def _load_shipped_down_family(name: str, axes: list[str]) -> InterpolatedAtmosphere:
    """Build a bundled down-looking family straight from its committed NPZs."""
    points: list[GeometryPoint] = []
    for npz_file in sorted((BUNDLED_ATMOSPHERES_DIR / name).glob("*.npz")):
        with np.load(npz_file, allow_pickle=True) as data:
            coords = dict(data["geometry"].item())
        tab = TabulatedAtmosphere.from_npz(npz_file)
        points.append(
            GeometryPoint(
                coordinates=coords,
                transmittance=tab.transmittance_data,
                path_radiance=tab.path_radiance_data,
                atm_emission_down=tab.atm_emission_down_data,
            )
        )
    return InterpolatedAtmosphere(points, axes, "linear", family_direction="down")


class TestNodeGeometry:
    """The hull and rendered geometry are read off the shipped NPZs, not prose."""

    def test_every_bundled_family_reports_its_nodes(self) -> None:
        for family in BUNDLED_FAMILIES:
            nodes = family_node_geometry(family.name)
            assert nodes is not None, family.name
            assert nodes.n_nodes >= 2
            assert set(nodes.axes) == set(family.interpolation_axes.split(","))

    def test_sensor_ladder_floor_is_three_km(self) -> None:
        nodes = family_node_geometry("midlat_summer_sensor_ladder")
        assert nodes is not None
        assert nodes.bounds["sensor_altitude_m"] == (3000.0, 40_000_000.0)
        assert nodes.fixed["target_altitude_m"] == pytest.approx(0.0, abs=1e-12)
        assert nodes.fixed["path_zenith_rad"] == pytest.approx(0.0, abs=1e-12)

    def test_full_column_families_declare_a_100_km_ceiling(self) -> None:
        """The exo guard's admit arm keys on this, so it must read off the data."""
        for name in (
            "midlat_summer_sst_column_fan",
            "midlat_summer_sst_column_fan_site900m",
            "midlat_summer_uplooking_sensor_ladder",
        ):
            nodes = family_node_geometry(name)
            assert nodes is not None
            assert nodes.target_ceiling_m == pytest.approx(100_000.0, rel=1e-12)

    def test_partial_column_ladders_declare_a_20_km_ceiling(self) -> None:
        for name in ("midlat_summer_uplooking_ladder", "midlat_summer_uplooking_zenith_fan"):
            nodes = family_node_geometry(name)
            assert nodes is not None
            assert nodes.target_ceiling_m == pytest.approx(20_000.0, rel=1e-12)

    def test_unknown_family_reports_nothing(self) -> None:
        assert family_node_geometry("not_a_shipped_family") is None


class TestDirectionGate:
    def test_up_family_never_serves_a_down_scene(self) -> None:
        result = family_suitability(_family("midlat_summer_uplooking_ladder"), _down(500_000.0))
        assert not result.serves
        assert result.gap is not None
        assert result.gap.kind == "direction"

    def test_down_family_never_serves_an_up_scene(self) -> None:
        result = family_suitability(_family("midlat_summer_sensor_ladder"), _up(0.0, 10_000.0))
        assert not result.serves
        assert result.gap is not None
        assert result.gap.kind == "direction"

    def test_a_level_line_of_sight_has_no_candidates(self) -> None:
        suggestion = select_atmosphere_family(
            LineOfSightGeometry(h_tgt=10_000.0, h_sensor=10_000.0, theta_o=math.pi / 2)
        )
        assert suggestion.family is None
        assert suggestion.gap is not None
        assert suggestion.gap.kind == "direction"
        assert suggestion.considered == ()


class TestSensorFloor:
    """The ladder floor is the gap 10 of the 11 uncovered scenarios hit."""

    def test_below_the_floor_is_refused_with_units(self) -> None:
        result = family_suitability(_family("midlat_summer_sensor_ladder"), _down(1.0))
        assert result.gap is not None
        assert result.gap.kind == "sensor_altitude"
        assert "3 km" in result.gap.text
        assert "1 m" in result.gap.text

    def test_at_the_floor_is_served(self) -> None:
        assert family_suitability(_family("midlat_summer_sensor_ladder"), _down(3000.0)).serves

    def test_the_gap_matches_what_the_backend_refuses(self) -> None:
        """Correspondence: the pre-check and the real hull check agree.

        The pre-check says a 1 m sensor is below the ladder; the loaded family
        itself refuses the same coordinate with its no-extrapolation error. If
        these two ever disagree, this module has become a second opinion.
        """
        model = _load_shipped_down_family("midlat_summer_sensor_ladder", ["sensor_altitude_m"])
        geometry = AtmosphericGeometry(
            sensor_altitude_m=1.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.0,
            solar_zenith_rad=math.radians(30.0),
            solar_azimuth_rad=0.0,
        )
        with pytest.raises(AtmosphereValidationError, match="outside the available range"):
            model.build_state(model.wavelength_um, geometry)


class TestUpLookingGates:
    def test_vertical_ladder_refuses_an_off_vertical_zenith(self) -> None:
        """Scenario 10.1's defect, at the unit level."""
        result = family_suitability(
            _family("midlat_summer_uplooking_ladder"), _up(0.0, 10_000.0, math.radians(29.95))
        )
        assert result.gap is not None
        assert result.gap.kind == "path_zenith"
        assert "single LOS zenith" in result.gap.text

    def test_zenith_fan_serves_the_same_query(self) -> None:
        assert family_suitability(
            _family("midlat_summer_uplooking_zenith_fan"),
            _up(0.0, 10_000.0, math.radians(29.95)),
        ).serves

    def test_partial_column_family_refuses_an_exo_target(self) -> None:
        result = family_suitability(
            _family("midlat_summer_uplooking_zenith_fan"), _up(0.0, 700_000.0, math.radians(18.0))
        )
        assert result.gap is not None
        assert result.gap.kind == "exo_ceiling"
        assert "20 km" in result.gap.text

    def test_full_column_family_serves_an_exo_target_from_the_ground(self) -> None:
        """The vacuum-equivalence identity: the ceiling node IS the answer."""
        assert family_suitability(
            _family("midlat_summer_sst_column_fan"), _up(0.0, 700_000.0, math.radians(18.0))
        ).serves

    def test_full_column_family_refuses_an_elevated_site(self) -> None:
        """Scenario 10.3: the gap, and the tolerance it is decided by.

        Still the right answer for the **0 m** fan — it is rendered from sea
        level and cannot represent a mountaintop column. What changed on
        2026-08-03 is that a sibling family now covers the scene; see
        :meth:`TestSelection.test_the_900_m_site_is_served_by_its_own_fan`.
        """
        result = family_suitability(
            _family("midlat_summer_sst_column_fan"), _up(900.0, 700_000.0, math.radians(18.0))
        )
        assert result.gap is not None
        assert result.gap.kind == "sensor_altitude"
        assert result.gap.context["tolerance"] == pytest.approx(1.0, rel=1e-12)

    def test_the_900_m_fan_serves_the_site_the_0_m_fan_refuses(self) -> None:
        """The M9–M13 ingestion, at the gate level: same scene, the other fan."""
        assert family_suitability(
            _family("midlat_summer_sst_column_fan_site900m"),
            _up(900.0, 700_000.0, math.radians(18.0)),
        ).serves

    def test_the_900_m_fan_refuses_a_sea_level_site(self) -> None:
        """The two fans are not interchangeable — the exchange runs both ways."""
        result = family_suitability(
            _family("midlat_summer_sst_column_fan_site900m"),
            _up(0.0, 700_000.0, math.radians(18.0)),
        )
        assert result.gap is not None
        assert result.gap.kind == "sensor_altitude"
        assert "900 m" in result.gap.text

    def test_one_metre_of_site_elevation_is_inside_the_tolerance(self) -> None:
        assert family_suitability(
            _family("midlat_summer_sst_column_fan"), _up(1.0, 700_000.0, math.radians(18.0))
        ).serves


class TestSelection:
    def test_a_wholly_vacuum_path_is_served_without_gate_checks(self) -> None:
        """LEO->GEO: both endpoints above h_atm_top, so no backend is consulted."""
        suggestion = select_atmosphere_family(_up(500_000.0, 35_786_000.0))
        assert suggestion.family is not None
        assert suggestion.family.name == "midlat_summer_uplooking_ladder"
        # Flagged, because the family's own coverage says nothing about this scene.
        assert suggestion.vacuum_path is True

    def test_an_endo_scene_is_not_flagged_as_a_vacuum_path(self) -> None:
        assert select_atmosphere_family(_down(500_000.0)).vacuum_path is False
        assert select_atmosphere_family(_up(0.0, 5_000.0)).vacuum_path is False

    def test_explicit_dir_families_are_candidates(self) -> None:
        """A row no axes string can reach is still recommendable, by name."""
        suggestion = select_atmosphere_family(_up(0.0, 700_000.0, math.radians(18.0)))
        assert suggestion.family is not None
        assert suggestion.family.name == "midlat_summer_sst_column_fan"
        assert suggestion.family.explicit_dir_only

    def test_the_reported_gap_is_the_closest_miss(self) -> None:
        """Not the first refusal an operator trips over — the furthest one.

        A 4200 m site (Mauna Kea) is outside **both** SST fans' rendered lower
        endpoints, so the library still cannot serve it — but the ladders fail
        earlier, on their 20 km target ceiling, and it is the fans' site
        elevation that is worth telling the operator about.
        """
        suggestion = select_atmosphere_family(_up(4200.0, 700_000.0, math.radians(18.0)))
        assert suggestion.family is None
        assert suggestion.gap is not None
        assert suggestion.gap.kind == "sensor_altitude"
        assert suggestion.gap.context["family"].startswith("midlat_summer_sst_column_fan")
        # The ladders fail earlier (their ceiling), and are not what is reported.
        assert "midlat_summer_uplooking_ladder" in suggestion.considered

    def test_the_900_m_site_is_served_by_its_own_fan(self) -> None:
        """Scenario 10.3, end of the CU-322 acceptance criterion.

        Until the M9–M13 decks landed this scene produced the single advisory
        naming the SST fan's 0 m lower endpoint (and the pending decks). It is
        now served — by the sibling family, which the selector reaches because
        ``EXPLICIT_DIR_FAMILIES`` rows are candidates by name.
        """
        suggestion = select_atmosphere_family(_up(900.0, 700_000.0, math.radians(18.0)))
        assert suggestion.family is not None
        assert suggestion.family.name == "midlat_summer_sst_column_fan_site900m"
        assert suggestion.family.explicit_dir_only
        assert suggestion.gap is None
        assert suggestion.advisory_text is None
        # The 0 m fan was tried first and did not win by accident.
        assert suggestion.considered.index(
            "midlat_summer_sst_column_fan"
        ) < suggestion.considered.index("midlat_summer_sst_column_fan_site900m")

    def test_precedence_keeps_the_family_the_axes_reasoning_already_chose(self) -> None:
        """Down-looking nadir ground scene: still the sensor ladder, not a wider fan."""
        suggestion = select_atmosphere_family(_down(500_000.0))
        assert suggestion.family is not None
        assert suggestion.family.name == "midlat_summer_sensor_ladder"

    def test_a_recommended_family_is_never_one_that_would_refuse(self) -> None:
        """The invariant the whole module exists for, over a spread of scenes."""
        scenes = [
            _down(1.0),
            _down(2000.0),
            _down(500_000.0),
            _down(500_000.0, theta_o_rad=math.radians(20.0)),
            _down(500_000.0, h_tgt_m=10_000.0),
            _up(0.0, 5_000.0),
            _up(0.0, 5_000.0, math.radians(45.0)),
            _up(0.0, 700_000.0, math.radians(18.0)),
            _up(900.0, 700_000.0),
            _up(50_000.0, 700_000.0, math.radians(10.0)),
        ]
        for los in scenes:
            suggestion = select_atmosphere_family(los)
            if suggestion.family is None:
                assert suggestion.gap is not None
                continue
            assert family_suitability(suggestion.family, los).serves


class TestCatalogueInvariants:
    def test_explicit_dir_rows_stay_out_of_the_dispatch_table(self) -> None:
        """CU-322 recommends them; it must not publish them into axes dispatch."""
        shipped = {f.name for f in SHIPPED_FAMILIES}
        for family in EXPLICIT_DIR_FAMILIES:
            assert family.name not in shipped
            assert family.explicit_dir_only

    def test_no_bundled_family_advertises_pending_runs(self) -> None:
        """The one row that did — the SST fan's M9–M13 line — was retired.

        ``pending_runs`` says "this gap is already scheduled". M9–M13 were
        delivered and ingested on 2026-08-03 as
        ``midlat_summer_sst_column_fan_site900m``, so the line stopped being
        true the moment the family shipped; leaving it would have told an
        operator that a shipped capability was still waiting on a MODTRAN run.
        The mechanism stays for the next authored-but-unrun block; the
        delivered-decks staleness guard lives in
        ``tests/integration/test_batch2_atmosphere_families.py``.
        """
        named = {f.name for f in BUNDLED_FAMILIES if f.pending_runs is not None}
        assert named == set()

    def test_both_sst_fans_are_explicit_dir_and_share_the_default_axes(self) -> None:
        """Why the 900 m block became a sibling rather than a dispatch row.

        Both fans key on ``path_zenith_rad`` — the schema **default** — so
        neither may join ``SHIPPED_FAMILIES``: an up-looking scene that never
        touched the axes parameter would silently land on one of them, and
        which lower endpoint it needs is a physical fact about the site, not
        something dispatch can guess.
        """
        fans = [f for f in BUNDLED_FAMILIES if f.name.startswith("midlat_summer_sst_column_fan")]
        assert len(fans) == 2
        for fan in fans:
            assert fan.explicit_dir_only
            assert fan.interpolation_axes == "path_zenith_rad"
            assert fan.los_direction == "up"
            assert fan.name not in {f.name for f in SHIPPED_FAMILIES}
