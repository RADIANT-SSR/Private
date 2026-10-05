"""The substrate display seam the GUI reads (Gap 142, plan §9.1).

``radiant.gui`` may import ``radiant.api`` and ``radiant.core`` only, so this module
is the GUI's only window onto the material library and onto the io parser's rule for
where a substrate may be named. It ships ahead of its GUI consumer — the picker lands
with the element detail editor — so these tests are what keep it honest in the interim.
"""

from __future__ import annotations

import pytest

from radiant.api.substrate import SubstrateInfo, available_substrates, entry_supports_substrate


class TestAvailableSubstrates:
    @pytest.mark.level1
    def test_every_bundled_material_is_projected(self) -> None:
        infos = available_substrates()
        assert len(infos) >= 6
        assert all(isinstance(i, SubstrateInfo) for i in infos)
        assert {"germanium", "silicon", "calcium_fluoride"} <= {i.name for i in infos}

    @pytest.mark.level1
    def test_measured_materials_sort_above_flagged_ones(self) -> None:
        """A picker built by iterating this gets the tier split without a roster of its own."""
        tiers = [i.tier.upper() for i in available_substrates()]
        assert tiers == sorted(tiers), tiers
        assert "A" in tiers and "B" in tiers

    @pytest.mark.level1
    def test_the_flag_is_derived_from_the_tier_not_restated(self) -> None:
        for info in available_substrates():
            assert info.is_flagged is (info.tier.upper() == "B")

    @pytest.mark.level1
    def test_germanium_carries_the_facts_a_picker_must_show(self) -> None:
        ge = next(i for i in available_substrates() if i.name == "germanium")
        assert ge.label == "Germanium (Ge)"
        assert ge.is_flagged  # tier B — class-typical alpha
        assert ge.valid_temperature_K == (250.0, 330.0)
        assert ge.window_um[0] < 4.0 < ge.window_um[1]
        assert ge.grade_sensitivity  # non-empty: the lot-to-lot spread is the point

    @pytest.mark.level1
    def test_the_label_never_falls_back_to_title_casing_a_grade_name(self) -> None:
        """``zinc_sulphide_ms`` is the multispectral grade, which title-casing mangles."""
        zns = next(i for i in available_substrates() if i.name == "zinc_sulphide_ms")
        assert "_" not in zns.label
        assert "Ms" not in zns.label


class TestEntrySupportsSubstrate:
    """Re-exported from the io parser deliberately — see the module docstring there."""

    @pytest.mark.level1
    @pytest.mark.parametrize(
        ("entry", "expected"),
        [
            ({"transfer_mode": "REFRACTIVE", "R1": 0.01, "R2": 0.01}, True),
            ({"transfer_mode": "REFRACTIVE", "transmittance": 0.9}, False),
            ({"transfer_mode": "REFLECTIVE", "reflectance": 0.97}, False),
        ],
    )
    def test_predicate_is_reachable_through_the_api(
        self, entry: dict[str, object], expected: bool
    ) -> None:
        assert entry_supports_substrate(entry) is expected
