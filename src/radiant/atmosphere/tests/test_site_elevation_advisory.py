"""Level-0 tests for the CU-393 defaulted-site-elevation advisory.

The predicate's whole difficulty is that altitude alone cannot separate the two
cases: a mountaintop telescope that forgot to declare its terrain and an aircraft
over the sea satisfy "lower endpoint high, site elevation 0" identically, and the
second one is correct. The observer class is what separates them, which is why
these tests sweep it explicitly.
"""

from __future__ import annotations

import warnings

import pytest

from radiant.atmosphere.site_elevation_advisory import (
    GROUND_OBSERVER_CLASS,
    SITE_ELEVATION_FLOOR_M,
    warn_if_site_elevation_defaulted,
)

_TRAP = {
    "profile_name": "hufnagel_valley",
    "observer_class": "ground",
    "site_elevation_m": 0.0,
    "site_elevation_is_default": True,
    "h_site_m": 900.0,
}


def _warns(**overrides: object) -> bool:
    kwargs = {**_TRAP, **overrides}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warn_if_site_elevation_defaulted(**kwargs)  # type: ignore[arg-type]
    return any(issubclass(w.category, UserWarning) for w in caught)


class TestTheTrap:
    @pytest.mark.level0
    def test_the_defect_as_found_warns(self) -> None:
        """Scenario 10.3 exactly: a 900 m ground site with the elevation defaulted."""
        assert _warns()

    @pytest.mark.level0
    def test_the_message_names_the_parameter_and_the_cost(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            warn_if_site_elevation_defaulted(**_TRAP)  # type: ignore[arg-type]
        message = str(caught[0].message)
        assert "geometry.site_elevation_m" in message
        assert "900" in message
        assert "optimistic" in message


class TestTheObserverClassGate:
    """The ruling's substance: altitude alone is not a sufficient predicate."""

    @pytest.mark.level0
    @pytest.mark.parametrize("observer_class", ["air", "space"])
    def test_a_non_ground_observer_is_silent(self, observer_class: str) -> None:
        """An airborne sensor over sea-level terrain is the SAME predicate, and correct."""
        assert not _warns(observer_class=observer_class)

    @pytest.mark.level0
    def test_only_ground_trips_it(self) -> None:
        assert GROUND_OBSERVER_CLASS == "ground"
        assert _warns(observer_class=GROUND_OBSERVER_CLASS)


class TestProvenanceNotValue:
    @pytest.mark.level0
    def test_an_explicit_zero_is_silent(self) -> None:
        """Typing 0 for a sea-level site answers the question; it is not the trap.

        Provenance decides, not value — the same distinction CU-392's `is_in_play`
        draws. A user who stated 0 has been asked and answered.
        """
        assert not _warns(site_elevation_is_default=False)

    @pytest.mark.level0
    def test_a_declared_elevation_is_silent(self) -> None:
        assert not _warns(site_elevation_m=900.0, site_elevation_is_default=False)


class TestTheProfileGate:
    @pytest.mark.level0
    @pytest.mark.parametrize("profile", ["direct", "tabulated"])
    def test_only_hufnagel_valley_consumes_the_elevation(self, profile: str) -> None:
        """'direct' has no profile and 'tabulated' carries its own site."""
        assert not _warns(profile_name=profile)


class TestTheAltitudeFloor:
    @pytest.mark.level0
    def test_a_sea_level_site_is_silent(self) -> None:
        assert not _warns(h_site_m=0.0)

    @pytest.mark.level0
    def test_just_below_the_floor_is_silent(self) -> None:
        assert not _warns(h_site_m=SITE_ELEVATION_FLOOR_M)

    @pytest.mark.level0
    def test_just_above_the_floor_warns(self) -> None:
        assert _warns(h_site_m=SITE_ELEVATION_FLOOR_M + 1.0)

    @pytest.mark.level0
    def test_the_floor_is_two_surface_scale_heights(self) -> None:
        """200 m is ~2 e-foldings of the HV surface term's 100 m scale height.

        Below that the omission sits inside the model's own uncertainty, so the
        advisory would be noise rather than signal.
        """
        import math

        remaining = math.exp(-SITE_ELEVATION_FLOOR_M / 100.0)
        assert remaining == pytest.approx(0.1353, rel=1e-3)
