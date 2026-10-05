"""Level-0 tests for the bundled substrate material library (Gap 142)."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.data.substrate import SubstrateError, SubstrateLibrary

_EXPECTED = {
    "zinc_selenide": "A",
    "calcium_fluoride": "A",
    "zinc_sulphide_ms": "A",
    "germanium": "B",
    "silicon": "B",
    "barium_fluoride": "B",
}


class TestTheShippedSet:
    @pytest.mark.level0
    def test_exactly_the_ratified_six_ship(self) -> None:
        """Owner ratified the two-tier set 2026-10-04 (plan §7.1).

        Sapphire and fused silica were deliberately excluded: one published alpha
        anchor each, outside any band where emission matters, and >100x OH-dependent
        spread on the silica. An estimate that wrong is worse than an honest absence.
        """
        assert set(SubstrateLibrary().names()) == set(_EXPECTED)

    @pytest.mark.level0
    @pytest.mark.parametrize(("name", "tier"), sorted(_EXPECTED.items()))
    def test_each_material_declares_its_confidence_tier(self, name: str, tier: str) -> None:
        assert SubstrateLibrary().material(name).tier == tier

    @pytest.mark.level0
    def test_tier_b_materials_state_their_lot_spread(self) -> None:
        """Ge and Si ship on thin data; the spread must be visible, not implied."""
        lib = SubstrateLibrary()
        for name in ("germanium", "silicon"):
            assert lib.material(name).grade_sensitivity.strip()


class TestPublishedAnchors:
    """Spot-check against the vendor values the library was built from."""

    @pytest.mark.level0
    def test_germanium_at_10_6_um(self) -> None:
        ge = SubstrateLibrary().material("germanium")
        n, alpha = ge.resample(np.array([10.6]))
        assert alpha[0] / 100.0 == pytest.approx(0.027, rel=1e-6)  # cm^-1, Crystran
        assert n[0] == pytest.approx(4.0032, abs=5e-3)  # Crystran publishes 4.0032

    @pytest.mark.level0
    def test_zinc_selenide_is_the_co2_laser_material(self) -> None:
        """ZnSe's whole point: alpha ~5e-4 cm^-1 at 10.6 um."""
        _, alpha = SubstrateLibrary().material("zinc_selenide").resample(np.array([10.6]))
        assert alpha[0] / 100.0 == pytest.approx(5e-4, rel=1e-6)

    @pytest.mark.level0
    def test_calcium_fluoride_resolves_its_multiphonon_edge(self) -> None:
        """CaF2's alpha rises ~2370x across its window — structure a user cannot guess.

        2.7 um and 10.0 um, the latter being the window edge; CaF2 is published to
        10.6 um but RADIANT caps it at its useful transmission limit.
        """
        _, alpha = SubstrateLibrary().material("calcium_fluoride").resample(np.array([2.7, 10.0]))
        assert alpha[1] / alpha[0] == pytest.approx(2370.0, rel=0.05)


class TestInterpolation:
    @pytest.mark.level0
    def test_alpha_is_interpolated_in_log_log(self) -> None:
        """A linear interpolant across a 4500x rise is a chord, not a curve.

        Checked at the geometric midpoint of two CaF2 anchors: log-log interpolation
        puts alpha near the geometric mean, linear would put it near the arithmetic
        one, and those differ by ~30x here.
        """
        caf2 = SubstrateLibrary().material("calcium_fluoride")
        _, ends = caf2.resample(np.array([2.7, 10.0]))
        mid_um = float(np.sqrt(2.7 * 10.0))
        _, mid = caf2.resample(np.array([mid_um]))
        geometric = float(np.sqrt(ends[0] * ends[1]))
        arithmetic = float(0.5 * (ends[0] + ends[1]))
        assert abs(np.log(mid[0]) - np.log(geometric)) < abs(np.log(mid[0]) - np.log(arithmetic))


class TestRefusals:
    @pytest.mark.level0
    def test_an_unknown_substrate_names_the_custom_path_first(self) -> None:
        """Plan §7.5: the library is a convenience over the explicit inputs.

        Someone who wants a material we do not carry should be told they can state
        alpha and n themselves, before being told to file a gap.
        """
        with pytest.raises(SubstrateError) as excinfo:
            SubstrateLibrary().material("unobtainium")
        message = str(excinfo.value)
        assert "alpha and n_refr explicitly" in message
        custom_at = message.index("alpha and n_refr explicitly")
        gap_at = message.index("file a gap")
        assert custom_at < gap_at, "the custom path must be offered before filing a gap"

    @pytest.mark.level0
    def test_outside_the_published_window_is_refused_not_extrapolated(self) -> None:
        """Past an absorption edge an extrapolated alpha is a different material."""
        with pytest.raises(SubstrateError, match="no data at"):
            SubstrateLibrary().material("germanium").resample(np.array([0.5]))

    @pytest.mark.level0
    def test_the_refusal_names_the_window(self) -> None:
        with pytest.raises(SubstrateError) as excinfo:
            SubstrateLibrary().material("zinc_selenide").resample(np.array([20.0]))
        assert "0.6-14" in str(excinfo.value)


class TestAliases:
    @pytest.mark.level0
    @pytest.mark.parametrize(
        ("alias", "canonical"),
        [("Ge", "germanium"), ("ZnSe", "zinc_selenide"), ("GERMANIUM", "germanium")],
    )
    def test_common_spellings_resolve(self, alias: str, canonical: str) -> None:
        assert SubstrateLibrary().material(alias).name == canonical


class TestTemperatureWindow:
    @pytest.mark.level0
    def test_germanium_declares_the_ratified_validity_window(self) -> None:
        """Plan §7.2: alpha ships at 293 K; [250, 330] K is where that is defensible.

        Outside it a 293 K alpha is wrong by more than the term it computes — +54 % at
        230 K, -38 % at 350 K — which is why the ruling made it an error rather than a
        caveat. The window is declared here; the consumer enforces it.
        """
        assert SubstrateLibrary().material("germanium").valid_temperature_K == (250.0, 330.0)
