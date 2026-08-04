"""Integration: switching a shipped GUI scenario to the interpolated model (CU-322).

The acceptance test the CU-322 entry names: **open any of the 38 shipped GUI
scenarios, switch ``atmosphere.model`` to ``interpolated``, and either it works
first try or it produces exactly one advisory naming the specific missing
coverage.**  Nothing in between — no sequence of refusals collected one gate at
a time, and never a recommendation the chain then refuses.

Each scenario is driven the way an operator drives the GUI, through the public
API only:

1. ``Sensor.atmosphere_family_suggestion()`` — the pre-validated recommendation;
2. if it names a family, write that family's ``interpolation_axes`` (and, for an
   ``explicit_dir_only`` row, its ``bundled_dir``) and **evaluate the chain**;
3. if it names none, assert the result carries one structured gap.

The split is pinned by scenario id, not by count alone.  A new MODTRAN family, a
scenario whose geometry moves, or a change to the suitability rules all shift
which list a scenario belongs to — and each of those is a decision, not a
detail, so the pin has to be updated deliberately.

**Why 27/11, and the two moves that got here.**  The CU-322 entry measured 25/13
on `main` *before* the fix, using the pre-CU-322 recommendation.  Two scenarios
have moved across since, each for a named reason:

* **10.1**, at CU-322 closure (26/12): it was in the advisory group only because
  it was recommended the vertical-only up-looking ladder at ζ = 29.9°; the
  zenith fan covers it, which is the mis-suggestion the entry names as defect
  (1).
* **10.3**, on 2026-08-03 (27/11): the entry's own worked example, and the last
  clause of its acceptance criterion — *"10.3 joins the first group when the
  M9–M13 site-elevation rungs are run."*  Those decks were delivered and
  ingested as ``midlat_summer_sst_column_fan_site900m``, so the 900 m
  mountaintop site the 0 m SST fan could not represent is now a rendered lower
  endpoint.  Nothing about the selector changed; the data did.

The remaining 11 are the scenes the entry calls "genuinely uncovered": 10 ground
or low sensors below the 3 km sensor-ladder floor, plus the level-LOS scene no
family is rendered for.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from radiant.api import Sensor

_SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "scenarios"

#: Scenarios whose pre-validated suggestion evaluates on the first try, with the
#: family each one lands on.  Measured 2026-08-02 against the shipped library.
FIRST_TRY: dict[str, str] = {
    "1.1": "us_standard_zenith_fan",
    "1.2": "midlat_summer_sensor_ladder",
    "1.3": "midlat_summer_sensor_ladder",
    "1.4": "midlat_summer_sensor_ladder",
    "1.5": "midlat_summer_sensor_ladder",
    "2.3": "midlat_summer_sensor_ladder",
    "3.1": "us_standard_zenith_fan",
    "3.2": "midlat_summer_sensor_ladder",
    "3.3": "midlat_summer_sensor_ladder",
    "3.4": "midlat_summer_sensor_ladder",
    "3.5": "midlat_summer_sensor_ladder",
    "4.1": "midlat_summer_sensor_ladder",
    "4.3": "midlat_summer_sensor_ladder",
    "4.4": "midlat_summer_sensor_ladder",
    "5.1": "midlat_summer_sensor_ladder",
    "5.2": "midlat_summer_sensor_ladder",
    "5.3": "midlat_summer_sensor_ladder",
    "5.4": "midlat_summer_sensor_ladder",
    "5.5": "midlat_summer_sensor_ladder",
    "6.2": "midlat_summer_sensor_ladder",
    "6.3": "midlat_summer_sensor_ladder",
    "6.4": "midlat_summer_sensor_ladder",
    "8.1": "us_standard_zenith_fan",
    "8.2": "midlat_summer_sensor_ladder",
    # The two direction-general scenes the bundled library does serve.
    # 10.1 is the entry's defect (1): the vertical-only ladder was recommended
    # at zeta = 29.9 degrees; the zenith fan is what covers it.
    "10.1": "midlat_summer_uplooking_zenith_fan",
    # 10.3 is the entry's worked example, served since the M9-M13 decks landed
    # (2026-08-03): the SST full column from its own 900 m site.
    "10.3": "midlat_summer_sst_column_fan_site900m",
    # 10.4 is a wholly-vacuum LEO->GEO path: both endpoints sit above
    # h_atm_top, so no backend is consulted at all.
    "10.4": "midlat_summer_uplooking_ladder",
}

#: Scenarios no bundled family serves, with the ``FamilyGap.kind`` each one's
#: single advisory carries.  Ten ground/low sensors below the 3 km floor of the
#: sensor ladder, plus one level line of sight.
SINGLE_ADVISORY: dict[str, str] = {
    "2.1": "sensor_altitude",
    "2.2": "sensor_altitude",
    "2.5": "sensor_altitude",
    "4.5": "sensor_altitude",
    "6.1": "sensor_altitude",
    "7.1": "sensor_altitude",
    "7.2": "sensor_altitude",
    "7.3": "sensor_altitude",
    "7.4": "sensor_altitude",
    "7.5": "sensor_altitude",
    "10.2": "direction",
}


def _gui_yamls() -> list[Path]:
    return sorted(_SCENARIOS_DIR.rglob("*.gui.yaml"), key=lambda p: p.name)


def _scenario_id(path: Path) -> str:
    return path.name.split("_")[0]


_YAML_BY_ID: dict[str, Path] = {_scenario_id(p): p for p in _gui_yamls()}


def test_every_shipped_gui_scenario_is_classified() -> None:
    """The pin covers all 38 shipped GUI YAMLs, each exactly once."""
    ids = set(_YAML_BY_ID)
    assert len(_YAML_BY_ID) == len(_gui_yamls()), "duplicate scenario ids under scenarios/"
    assert ids == set(FIRST_TRY) | set(SINGLE_ADVISORY)
    assert not set(FIRST_TRY) & set(SINGLE_ADVISORY)
    assert len(FIRST_TRY) == 27
    assert len(SINGLE_ADVISORY) == 11


@pytest.mark.golden
@pytest.mark.parametrize("scenario_id", sorted(FIRST_TRY), ids=sorted(FIRST_TRY))
def test_suggested_family_evaluates_first_try(scenario_id: str) -> None:
    """The recommendation names a family, and setting it evaluates the chain.

    The whole point of pre-validation: a family the API names is one the chain
    accepts.  Before CU-322 this failed for 10.1 — the axes-string reasoning
    recommended ``midlat_summer_uplooking_ladder``, whose ``uplooking_column_product``
    then refused the 29.9 degree query because that family is rendered vertical.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sensor = Sensor.load(_YAML_BY_ID[scenario_id])
        suggestion = sensor.atmosphere_family_suggestion()

        assert suggestion.serves, f"{scenario_id}: no family suggested ({suggestion.gap})"
        family = suggestion.family
        assert family is not None
        assert family.name == FIRST_TRY[scenario_id]
        assert suggestion.gap is None

        run = Sensor.load(_YAML_BY_ID[scenario_id])
        run.set("atmosphere.model", "interpolated")
        run.set("atmosphere.interpolation_axes", family.interpolation_axes)
        if family.explicit_dir_only:
            run.set("atmosphere.interpolated_data_dir", family.bundled_dir)
        result = run.evaluate()

    assert result.metrics, f"{scenario_id}: evaluated but produced no metrics"


@pytest.mark.parametrize("scenario_id", sorted(SINGLE_ADVISORY), ids=sorted(SINGLE_ADVISORY))
def test_uncovered_scene_gets_one_structured_advisory(scenario_id: str) -> None:
    """No family, exactly one gap, and it names the missing coverage with units."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sensor = Sensor.load(_YAML_BY_ID[scenario_id])
        suggestion = sensor.atmosphere_family_suggestion()

    assert not suggestion.serves
    assert suggestion.family is None
    gap = suggestion.gap
    assert gap is not None, f"{scenario_id}: no-family result carried no reason"
    assert gap.kind == SINGLE_ADVISORY[scenario_id]

    text = suggestion.advisory_text
    assert text is not None
    # Units always explicit (the operator-facing contract), and one sentence.
    assert text.count(".") <= 2, f"{scenario_id}: advisory is not a single statement: {text}"
    if gap.kind != "direction":
        assert (" m" in text) or (" km" in text) or ("degrees" in text), text

    # The same content, in the actionable shape a message surface renders.
    error = suggestion.advisory_error()
    assert error is not None
    assert error.what == text
    assert error.action and "simple" in error.action


@pytest.mark.golden
def test_scenario_10_3_is_served_from_its_own_900_m_site_fan() -> None:
    """The CU-322 acceptance criterion's last clause, completing.

    The entry's worked example.  Until 2026-08-03 three families refused this
    scene and the advisory named the closest miss — the SST column fan, which
    served the geometry in every respect but was rendered from a 0 m site while
    this scene's telescope sits at 900 m — together with the authored M9-M13
    rows, so a scheduled gap did not read as an absent one.  Those rows were
    run and ingested as ``midlat_summer_sst_column_fan_site900m``, so the scene
    is now served first-try: no advisory, and the chain evaluates.

    The provenance is asserted, not just the metric, because *how* it is served
    is the physics claim: the 900 m lower endpoint is a rendered node, and the
    700 km target is reached by the exo vacuum-clamp identity off the family's
    100 km column top rather than by extrapolating past it.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sensor = Sensor.load(_YAML_BY_ID["10.3"])
        suggestion = sensor.atmosphere_family_suggestion()

        assert suggestion.serves
        assert suggestion.advisory_text is None
        assert suggestion.gap is None
        family = suggestion.family
        assert family is not None
        assert family.name == "midlat_summer_sst_column_fan_site900m"
        assert family.explicit_dir_only

        run = Sensor.load(_YAML_BY_ID["10.3"])
        run.set("atmosphere.model", "interpolated")
        run.set("atmosphere.interpolation_axes", family.interpolation_axes)
        run.set("atmosphere.interpolated_data_dir", family.bundled_dir)
        result = run.evaluate()

    assert result.metrics["snr"] == pytest.approx(218.0267, rel=1e-4)

    provenance = result.stage_outputs["atmosphere"]["topology_provenance"]
    segment = provenance["observer_segment_provenance"]
    assert segment["model"] == "interpolated"
    assert segment["h_low_m"] == pytest.approx(900.0, abs=1e-9)
    assert segment["n_points"] == 5
    assert segment["target_ceiling_m"] == pytest.approx(100_000.0, abs=1e-9)
    assert segment["target_altitude_served_m"] == pytest.approx(100_000.0, abs=1e-9)
    assert "exact identity, not extrapolation" in segment["exo_target_vacuum_clamp"]
    # CU-226: the observer leg is measured, the illumination legs are not, and
    # the result says so rather than presenting one self-consistent model.
    assert "InterpolatedAtmosphere up-looking run family" in provenance["backend_split"]
    assert "SimpleAtmosphere companion" in provenance["backend_split"]


def test_scenario_10_1_is_the_zenith_fan_not_the_vertical_ladder() -> None:
    """Defect (1), pinned: the off-vertical up-looking scene gets the fan.

    Fails on pre-CU-322 code, which recommended ``midlat_summer_uplooking_ladder``
    from the axes string alone and never checked whether that family could
    represent a 29.9 degree lower-endpoint zenith.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sensor = Sensor.load(_YAML_BY_ID["10.1"])
        suggestion = sensor.atmosphere_family_suggestion()
        assert suggestion.family is not None
        assert suggestion.family.name == "midlat_summer_uplooking_zenith_fan"
        assert "midlat_summer_uplooking_ladder" in suggestion.considered


def test_scenario_10_1_vertical_ladder_is_refused_by_name() -> None:
    """The family 10.1 used to be handed reports its own single-zenith gap."""
    from radiant.api import shipped_atmosphere_families

    ladder = next(
        f for f in shipped_atmosphere_families() if f.name == "midlat_summer_uplooking_ladder"
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gap = Sensor.load(_YAML_BY_ID["10.1"]).atmosphere_family_gap(ladder)

    assert gap is not None
    assert "single LOS zenith" in gap
    assert "degrees" in gap
