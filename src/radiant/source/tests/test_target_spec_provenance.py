"""Provenance semantics of the target-spec over-specification seam (CU-300).

The CU-244 guards in :mod:`radiant.source.target_spec` are pure provenance
reads: every one of them asks "did the *user* choose this value?" before
refusing a pair of surfaces as over-specified.  These tests pin the answer to
that question, because the failure mode it guards against is silent and
user-hostile — a config refused over a value RADIANT itself computed, with an
error blaming the analyst for an input they never made.

Level 0: no physics, no chain, one helper under test.
"""

from __future__ import annotations

import pytest

from radiant.core.parameters import ParameterSet, Provenance
from radiant.geometry._schema import ALL_PARAMETERS as GEOMETRY_PARAMETERS
from radiant.source._schema import ALL_PARAMETERS as SOURCE_PARAMETERS
from radiant.source.target_spec import _is_user_set

#: One surface from each guard family, so the pin is not specific to one door.
_GUARD_SURFACES: tuple[str, ...] = (
    "source.target.emissivity",
    "source.target.temperature",
    "source.target.brightness_temperature_K",
    "source.target.radiance_temperature_K",
    "source.target.reflectance",
    "geometry.target.projected_area_m2",
)


def _params() -> ParameterSet:
    ps = ParameterSet([*SOURCE_PARAMETERS, *GEOMETRY_PARAMETERS], [])
    ps.set("geometry.sensor_altitude_m", 500.0e3)  # m — required, unused here
    return ps


class TestIsUserSetProvenance:
    @pytest.mark.level0
    @pytest.mark.parametrize("name", _GUARD_SURFACES)
    def test_default_is_not_user_set(self, name: str) -> None:
        ps = _params()
        ps.resolve()
        assert _is_user_set(ps, name) is False

    @pytest.mark.level0
    @pytest.mark.parametrize(
        "provenance", [Provenance.USER_SET, Provenance.CONFIG_FILE, Provenance.SAMPLED]
    )
    def test_user_driven_provenances_count_as_user_set(self, provenance: Provenance) -> None:
        """USER_SET, CONFIG_FILE and SAMPLED are all "the analyst chose this".

        SAMPLED is a sweep axis — user intent expressed once per point — so an
        over-specified sweep must still be refused.
        """
        ps = _params()
        ps.set("source.target.emissivity", 0.9, provenance, "test")
        assert _is_user_set(ps, "source.target.emissivity") is True  # unresolved view
        ps.resolve()
        assert _is_user_set(ps, "source.target.emissivity") is True  # resolved view

    @pytest.mark.level0
    @pytest.mark.parametrize("name", _GUARD_SURFACES)
    def test_derived_is_not_user_set(self, name: str) -> None:
        """CU-300: a value RADIANT computed is not an over-specification.

        Before CU-300 the resolved branch answered ``True`` here (anything
        that was not ``DEFAULT`` counted), so the first guard placed over a
        derived surface would have refused a config the user never
        over-specified.
        """
        ps = _params()
        value: object = "" if isinstance(ps.parameter_def(name).default, str) else 0.5
        ps.set(name, value, Provenance.DERIVED, "derived: test")
        assert _is_user_set(ps, name) is False  # unresolved view
        ps.resolve()
        assert ps.get_resolved(name).provenance is Provenance.DERIVED
        assert _is_user_set(ps, name) is False  # resolved view

    @pytest.mark.level0
    def test_no_guard_surface_is_derived_on_a_plain_resolve(self) -> None:
        """The claim that makes CU-300 latent rather than live, pinned.

        No surface any current guard inspects participates in a consistency
        group, so none of them resolves to ``DERIVED`` without a caller
        explicitly writing that provenance.  If a future consistency group or
        API-side derivation ever covers one of these, this test fails and the
        guard's behaviour must be re-reasoned rather than silently changing.
        """
        ps = _params()
        ps.resolve()
        derived = [
            n for n in _GUARD_SURFACES if ps.get_resolved(n).provenance is Provenance.DERIVED
        ]
        assert derived == []
