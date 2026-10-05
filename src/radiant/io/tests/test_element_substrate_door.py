"""The named-substrate door on a refractive element (Gap 142).

The door is a convenience over the explicit ``alpha`` input, never a
replacement (plan §7.5, owner requirement 2026-10-04). These tests pin that
relationship: both doors must reach the same cavity, naming both must be refused, and
the custom path must keep working untouched.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.data.substrate import SubstrateLibrary
from radiant.io.element_config import (
    ElementConfigError,
    entry_supports_substrate,
    parse_element_entries,
    validate_element_entry,
)

_WL = np.linspace(3.5, 5.0, 8)


def _entry(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "L1",
        "transfer_mode": "REFRACTIVE",
        "thickness_m": 0.008,
        "R1": 0.01,
        "R2": 0.01,
        "temperature_K": 250.0,
    }
    base.update(overrides)
    return base


class TestBothDoorsReachOneCavity:
    @pytest.mark.level1
    def test_identical_inputs_give_bit_identical_emissivity(self) -> None:
        """§7.5's load-bearing claim: there is ONE physics path, not two.

        Resolve the library's germanium onto the grid, then feed that exact array
        through the explicit door. If the named door did anything other than look up
        alpha, this would not be bit-identical.
        """
        _, alpha = SubstrateLibrary().material("germanium").resample(_WL)
        named = parse_element_entries([_entry(substrate="germanium")], wavelength_um=_WL)[0]
        custom = parse_element_entries(
            [
                _entry(
                    alpha={"wavelength_um": _WL.tolist(), "values": alpha.tolist()},
                )
            ],
            wavelength_um=_WL,
        )[0]
        np.testing.assert_array_equal(named.emissivity.values, custom.emissivity.values)

    @pytest.mark.level1
    def test_the_named_door_records_its_provenance(self) -> None:
        element = parse_element_entries([_entry(substrate="germanium")], wavelength_um=_WL)[0]
        assert "substrate library" in element.cavity.alpha.source
        assert "germanium" in element.cavity.alpha.source
        assert "tier B" in element.cavity.alpha.source

    @pytest.mark.level1
    def test_alpha_arrives_in_canonical_units(self) -> None:
        """The library publishes cm^-1; the cavity consumes 1/m (Rule 2 boundary)."""
        element = parse_element_entries([_entry(substrate="germanium")], wavelength_um=_WL)[0]
        assert element.cavity.alpha.unit == "1/m"
        # Ge at ~4.25 um is ~0.0055 cm^-1 => ~0.55 /m, i.e. the x100 happened once.
        assert float(np.interp(4.25, _WL, element.cavity.alpha.values)) == pytest.approx(
            0.55, rel=0.25
        )


class TestTheCustomPathSurvives:
    @pytest.mark.level1
    def test_explicit_alpha_still_works_with_no_substrate(self) -> None:
        """Adding a convenience must not remove the general case."""
        element = parse_element_entries([_entry(alpha=0.552)], wavelength_um=_WL)[0]
        assert np.all(element.emissivity.values > 0.0)
        assert "substrate library" not in element.cavity.alpha.source


class TestOverSpecification:
    @pytest.mark.level1
    @pytest.mark.parametrize("extra", ["alpha"])
    def test_naming_a_substrate_and_setting_its_quantities_is_refused(self, extra: str) -> None:
        """A substrate supplies exactly these; giving both has no resolution rule.

        Same shape as Rule 5's refusal of a mirror carrying both reflectance and
        emissivity — the parser is the single validation authority.
        """
        with pytest.raises(ElementConfigError, match="over-specifies"):
            parse_element_entries(
                [_entry(substrate="germanium", **{extra: 0.5})], wavelength_um=_WL
            )

    @pytest.mark.level1
    def test_the_refusal_says_thickness_stays_either_way(self) -> None:
        """Thickness belongs to the lens, not to the material (§7.5 consequence 3)."""
        with pytest.raises(ElementConfigError) as excinfo:
            parse_element_entries([_entry(substrate="germanium", alpha=0.5)], wavelength_um=_WL)
        assert "thickness_m stays" in str(excinfo.value)


class TestUnknownMaterial:
    @pytest.mark.level1
    def test_an_unknown_substrate_is_refused_with_the_custom_path_offered(self) -> None:
        with pytest.raises(ElementConfigError) as excinfo:
            parse_element_entries([_entry(substrate="unobtainium")], wavelength_um=_WL)
        message = str(excinfo.value)
        assert "unknown substrate" in message
        assert "alpha explicitly" in message

    @pytest.mark.level1
    def test_a_substrate_outside_its_window_is_refused(self) -> None:
        """Germanium starts at 1.9 um; a VIS grid is past its electronic edge."""
        with pytest.raises(ElementConfigError, match="no data at"):
            parse_element_entries(
                [_entry(substrate="germanium")], wavelength_um=np.linspace(0.4, 0.9, 6)
            )


class TestInertSubstrateIsRefused:
    """A substrate that cannot reach the answer must not be quietly accepted.

    The door was built in the parser's **cavity** branch only, so for the first day of
    its life a substrate named on a simple refractive row — or on a mirror — was
    accepted, round-tripped into saved YAML, and ignored, leaving emissivity at 0.0: the
    one quantity the analyst chose the material to obtain. Found while preparing the GUI
    picker's live review, on the first row an operator would have clicked (scenario
    10.1's `cold_window`). Same failure mode as CU-365's silently-ignored keys.
    """

    @pytest.mark.level1
    def test_a_simple_refractive_row_refuses_a_substrate(self) -> None:
        entry = {
            "name": "cold_window",
            "kind": "WINDOW",
            "transfer_mode": "REFRACTIVE",
            "transmittance": 0.8,
            "temperature_K": 293.15,
            "substrate": "germanium",
        }
        with pytest.raises(ElementConfigError) as excinfo:
            parse_element_entries([entry], wavelength_um=_WL)
        message = str(excinfo.value)
        assert "nothing to act on" in message
        # The action line must name both missing pieces, or it is not actionable.
        assert "thickness_m" in message
        assert "R1/T1/R2/T2" in message
        # The physics reason, not merely the structural one: the simple model
        # assigns 1 - T to reflection, so it has no absorption term at all.
        assert "zero by construction" in message

    @pytest.mark.level1
    def test_a_mirror_refuses_a_substrate_and_cites_kirchhoff(self) -> None:
        entry = {
            "name": "m1",
            "kind": "MIRROR",
            "transfer_mode": "REFLECTIVE",
            "reflectance": 0.98,
            "temperature_K": 293.0,
            "substrate": "germanium",
        }
        with pytest.raises(ElementConfigError) as excinfo:
            parse_element_entries([entry], wavelength_um=_WL)
        message = str(excinfo.value)
        assert "nothing to act on" in message
        assert "1 − R" in message

    @pytest.mark.level1
    def test_the_refusal_reaches_structural_validation_too(self) -> None:
        """The GUI commits through ``validate_element_entry``, which must agree.

        A refusal that only fires at evaluation would let the picker's commit succeed
        and the error surface a debounce later, detached from the click that caused it.
        """
        entry = {
            "name": "cold_window",
            "transfer_mode": "REFRACTIVE",
            "transmittance": 0.8,
            "substrate": "germanium",
        }
        with pytest.raises(ElementConfigError, match="nothing to act on"):
            validate_element_entry(entry)

    @pytest.mark.level1
    def test_the_supported_cavity_door_is_untouched(self) -> None:
        """The guard must not have narrowed the door it was added to protect."""
        element = parse_element_entries([_entry(substrate="germanium")], wavelength_um=_WL)[0]
        assert float(np.mean(element.emissivity.values)) > 0.0


class TestSubstrateSupportPredicate:
    """``entry_supports_substrate`` is the rule the parser enforces, made public.

    The GUI reads it to decide whether to *offer* the picker. If it could disagree with
    the parser, the picker would offer a choice the commit refuses — which is the
    drift that produced the defect above, in the other direction.
    """

    @pytest.mark.level1
    @pytest.mark.parametrize(
        ("entry", "expected"),
        [
            ({"transfer_mode": "REFRACTIVE", "R1": 0.01, "thickness_m": 0.008}, True),
            ({"transfer_mode": "REFRACTIVE", "T2": 0.99}, True),
            ({"transfer_mode": "refractive", "R2": 0.01}, True),
            ({"transfer_mode": "REFRACTIVE", "transmittance": 0.8}, False),
            ({"transfer_mode": "REFLECTIVE", "R1": 0.01}, False),
            ({"transfer_mode": "REFLECTIVE", "reflectance": 0.98}, False),
            ({}, False),
        ],
    )
    def test_predicate(self, entry: dict[str, object], expected: bool) -> None:
        assert entry_supports_substrate(entry) is expected

    @pytest.mark.level1
    def test_the_predicate_agrees_with_the_parser_on_every_case(self) -> None:
        """Pin the two together, so neither can be changed alone."""
        cases: list[dict[str, object]] = [
            # A *complete* cavity entry: both surfaces, as the factory requires. The
            # predicate answers "would a substrate act here", not "is this entry valid".
            {
                "name": "a",
                "transfer_mode": "REFRACTIVE",
                "R1": 0.01,
                "R2": 0.01,
                "thickness_m": 0.008,
            },
            {"name": "b", "transfer_mode": "REFRACTIVE", "transmittance": 0.8},
            {"name": "c", "transfer_mode": "REFLECTIVE", "reflectance": 0.98},
        ]
        for case in cases:
            entry = {**case, "substrate": "germanium", "temperature_K": 250.0}
            if entry_supports_substrate(entry):
                parse_element_entries([entry], wavelength_um=_WL)  # must not raise
            else:
                with pytest.raises(ElementConfigError, match="nothing to act on"):
                    parse_element_entries([entry], wavelength_um=_WL)


class TestTheRemovedIndexKey:
    """``n_refr`` is refused with guidance, not ignored (CU-399)."""

    @pytest.mark.level1
    def test_a_legacy_document_is_told_what_happened(self) -> None:
        with pytest.raises(ElementConfigError) as excinfo:
            parse_element_entries([_entry(alpha=0.552, n_refr=4.024)], wavelength_um=_WL)
        message = str(excinfo.value)
        assert "no longer an element field" in message
        # The reassurance that matters to someone editing an old config: deleting the
        # key does not move their answer, because the key never moved it.
        assert "the result does not change" in message


class TestTemperatureWindowReachesTheElement:
    """The library's window is enforced where the element's temperature is known."""

    @pytest.mark.level1
    def test_a_cryogenic_germanium_lens_is_refused(self) -> None:
        with pytest.raises(ElementConfigError) as excinfo:
            parse_element_entries(
                [_entry(substrate="germanium", temperature_K=80.0)], wavelength_um=_WL
            )
        assert "validity window" in str(excinfo.value)

    @pytest.mark.level1
    def test_an_in_window_lens_is_accepted(self) -> None:
        element = parse_element_entries(
            [_entry(substrate="germanium", temperature_K=290.0)], wavelength_um=_WL
        )[0]
        assert float(np.mean(element.emissivity.values)) > 0.0

    @pytest.mark.level1
    def test_an_element_at_zero_kelvin_is_not_refused(self) -> None:
        """0 K is the "emits nothing" convention and the parser's own default."""
        element = parse_element_entries(
            [_entry(substrate="germanium", temperature_K=0.0)], wavelength_um=_WL
        )[0]
        assert element.cavity is not None
