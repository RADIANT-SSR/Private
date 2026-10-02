"""Level 0: the background-composition breakdown (Gap 132).

The external review ranked this above its own top defect finding, because
CU-380 — warm optics evaluating to identically zero while the term looked
enabled — would have been obvious in seconds from one proportioned line. These
tests pin the arithmetic and, more importantly, the edge behaviours that decide
whether the breakdown is trustworthy: a zero total, a single dominant term, and
the zero-term report that is the CU-380 reading.
"""

from __future__ import annotations

import pytest

from radiant.performance.background_composition import (
    BACKGROUND_TERMS,
    compute_background_composition,
)
from radiant.performance.errors import PerformanceValidationError


def _compose(**kw: float):  # type: ignore[no-untyped-def]
    args = {"nearfield_e": 0.0, "scene_e": 0.0, "dark_e": 0.0, "stray_e": 0.0, "glow_e": 0.0}
    args.update(kw)
    return compute_background_composition(**args)  # type: ignore[arg-type]


class TestArithmetic:
    @pytest.mark.level0
    def test_shares_are_the_hand_computed_fractions(self) -> None:
        c = _compose(nearfield_e=60.0, scene_e=20.0, dark_e=10.0, stray_e=8.0, glow_e=2.0)
        assert c.total_e == pytest.approx(100.0, rel=1e-12)
        assert c.shares["nearfield"] == pytest.approx(0.60, rel=1e-12)
        assert c.shares["scene"] == pytest.approx(0.20, rel=1e-12)
        assert c.shares["dark"] == pytest.approx(0.10, rel=1e-12)
        assert c.shares["stray"] == pytest.approx(0.08, rel=1e-12)
        assert c.shares["glow"] == pytest.approx(0.02, rel=1e-12)

    @pytest.mark.level0
    def test_shares_sum_to_one(self) -> None:
        c = _compose(nearfield_e=7.3, scene_e=0.004, dark_e=112.0, stray_e=1e-6, glow_e=55.5)
        assert sum(c.shares.values()) == pytest.approx(1.0, rel=1e-12)

    @pytest.mark.level0
    def test_total_uses_fsum_so_a_tiny_term_is_not_lost(self) -> None:
        """A 1e-12 term beside a 1e12 term must still be counted."""
        c = _compose(nearfield_e=1e12, glow_e=1e-12)
        assert c.total_e >= 1e12

    @pytest.mark.level0
    def test_share_pct_is_the_display_form(self) -> None:
        c = _compose(nearfield_e=3.0, scene_e=1.0)
        assert c.share_pct("nearfield") == pytest.approx(75.0, rel=1e-12)

    @pytest.mark.level0
    def test_share_pct_rejects_an_unknown_term(self) -> None:
        c = _compose(dark_e=1.0)
        with pytest.raises(PerformanceValidationError, match="not a background term"):
            c.share_pct("signal")


class TestDominantTerm:
    @pytest.mark.level0
    def test_dominant_is_the_largest(self) -> None:
        assert _compose(nearfield_e=1.0, dark_e=99.0).dominant == "dark"

    @pytest.mark.level0
    def test_dominant_is_none_when_there_is_no_pedestal(self) -> None:
        """Naming a winner among five zeros would be arbitrary."""
        assert _compose().dominant is None

    @pytest.mark.level0
    def test_a_tie_resolves_in_declared_order(self) -> None:
        """Deterministic, so a report never flickers between equal terms."""
        c = _compose(nearfield_e=5.0, scene_e=5.0)
        assert c.dominant == "nearfield"
        assert BACKGROUND_TERMS.index("nearfield") < BACKGROUND_TERMS.index("scene")


class TestTheZeroPedestal:
    @pytest.mark.level0
    def test_zero_total_gives_zero_shares_not_nan(self) -> None:
        """A cold-shielded configuration is well-defined, not undefined."""
        c = _compose()
        assert c.total_e == 0.0
        assert all(v == 0.0 for v in c.shares.values())

    @pytest.mark.level0
    def test_every_term_is_always_present(self) -> None:
        """An absent key would hide the silently-zero case this exists to expose."""
        c = _compose(dark_e=1.0)
        assert set(c.terms) == set(BACKGROUND_TERMS)
        assert set(c.shares) == set(BACKGROUND_TERMS)


class TestZeroTermReport:
    @pytest.mark.level0
    def test_zero_terms_names_the_cu380_case(self) -> None:
        """A thermal run with no warm-optics contribution reports it."""
        c = _compose(scene_e=100.0, dark_e=5.0)
        assert "nearfield" in c.zero_terms()
        assert "scene" not in c.zero_terms()

    @pytest.mark.level0
    def test_zero_terms_is_in_declared_order(self) -> None:
        c = _compose(scene_e=1.0)
        assert c.zero_terms() == ("nearfield", "dark", "stray", "glow")

    @pytest.mark.level0
    def test_no_zero_terms_when_all_contribute(self) -> None:
        c = _compose(nearfield_e=1.0, scene_e=1.0, dark_e=1.0, stray_e=1.0, glow_e=1.0)
        assert c.zero_terms() == ()


class TestInvalidInput:
    @pytest.mark.level0
    @pytest.mark.parametrize("term", BACKGROUND_TERMS)
    def test_negative_charge_is_an_error_not_a_clamp(self, term: str) -> None:
        with pytest.raises(PerformanceValidationError, match="negative"):
            _compose(**{f"{term}_e": -1.0})

    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_charge_is_an_error(self, bad: float) -> None:
        with pytest.raises(PerformanceValidationError, match="not finite"):
            _compose(nearfield_e=bad)
