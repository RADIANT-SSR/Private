"""Tests for radiant.api.error_budget (Gaps 23 + 28).

Category B: dimensional behavior (unit-agnostic RSS), failure modes,
serialization round-trip.

Truth anchors:
  1. 3-4-5 triangle: RSS(3, 4) = 5 exactly.
  2. Scenario 5.1 WFE style: RSS(0.05, 0.03, 0.02) waves = 0.061644 waves.
  3. Headroom: allocation 10, contributors (6, 8) -> RSS 10, headroom 0.
"""

from __future__ import annotations

import math

import pytest

from radiant.api.error_budget import (
    BudgetContributor,
    ErrorBudget,
    ErrorBudgetError,
)


def _wfe_budget() -> ErrorBudget:
    return ErrorBudget(
        name="wfe",
        unit="waves",
        allocation=0.08,
        contributors=(
            BudgetContributor("fabrication", 0.05),
            BudgetContributor("alignment", 0.03),
            BudgetContributor("thermal", 0.02, note="worst-case season"),
        ),
    )


class TestRssMath:
    @pytest.mark.level0
    def test_three_four_five(self) -> None:
        b = ErrorBudget(
            name="t",
            unit="urad",
            contributors=(BudgetContributor("a", 3.0), BudgetContributor("b", 4.0)),
        )
        assert b.rss_total == pytest.approx(5.0, rel=1e-15)

    @pytest.mark.level0
    def test_wfe_hand_anchor(self) -> None:
        """sqrt(0.05² + 0.03² + 0.02²) = sqrt(0.0038) = 0.0616441."""
        assert _wfe_budget().rss_total == pytest.approx(0.0616441, rel=1e-5)

    def test_empty_budget_is_zero(self) -> None:
        assert ErrorBudget(name="t", unit="urad").rss_total == 0.0


class TestAllocation:
    def test_margin_and_status(self) -> None:
        b = _wfe_budget()
        assert b.margin == pytest.approx(0.08 - 0.0616441, rel=1e-5)
        assert b.over_budget is False

    @pytest.mark.level0
    def test_headroom_exact_consumption(self) -> None:
        b = ErrorBudget(
            name="t",
            unit="urad",
            allocation=10.0,
            contributors=(BudgetContributor("a", 6.0), BudgetContributor("b", 8.0)),
        )
        assert b.rss_total == pytest.approx(10.0, rel=1e-15)
        assert b.remaining_allocation() == 0.0
        assert b.over_budget is False

    def test_headroom_formula(self) -> None:
        b = _wfe_budget()
        expected = math.sqrt(0.08**2 - b.rss_total**2)
        assert b.remaining_allocation() == pytest.approx(expected, rel=1e-12)

    def test_over_budget(self) -> None:
        b = ErrorBudget(
            name="t",
            unit="urad",
            allocation=4.0,
            contributors=(BudgetContributor("a", 3.0), BudgetContributor("b", 4.0)),
        )
        assert b.over_budget is True
        assert b.remaining_allocation() == 0.0
        assert b.margin == pytest.approx(-1.0, rel=1e-12)

    def test_headroom_without_allocation_raises(self) -> None:
        b = ErrorBudget(name="t", unit="urad")
        with pytest.raises(ErrorBudgetError, match="requires an allocation"):
            b.remaining_allocation()


class TestConstruction:
    def test_with_contributor_immutably_extends(self) -> None:
        b0 = _wfe_budget()
        b1 = b0.with_contributor("gravity_release", 0.01)
        assert len(b0.contributors) == 3
        assert len(b1.contributors) == 4
        assert b1.rss_total > b0.rss_total

    def test_negative_value_rejected(self) -> None:
        with pytest.raises(ErrorBudgetError, match="non-negative"):
            BudgetContributor("bad", -1.0)

    def test_duplicate_names_rejected(self) -> None:
        with pytest.raises(ErrorBudgetError, match="duplicate"):
            ErrorBudget(
                name="t",
                unit="urad",
                contributors=(BudgetContributor("a", 1.0), BudgetContributor("a", 2.0)),
            )

    def test_nonpositive_allocation_rejected(self) -> None:
        with pytest.raises(ErrorBudgetError, match="positive"):
            ErrorBudget(name="t", unit="urad", allocation=0.0)


class TestReporting:
    def test_table_contains_rows_and_total(self) -> None:
        text = _wfe_budget().table()
        assert "fabrication" in text
        assert "RSS total" in text
        assert "within budget" in text
        assert "waves" in text

    def test_share_sums_to_one(self) -> None:
        b = _wfe_budget()
        shares = [c.value**2 / b.rss_total**2 for c in b.contributors]
        assert sum(shares) == pytest.approx(1.0, rel=1e-12)


class TestSerialization:
    def test_round_trip(self) -> None:
        b = _wfe_budget()
        b2 = ErrorBudget.from_dict(b.to_dict())
        assert b2 == b
        assert b2.rss_total == pytest.approx(b.rss_total, rel=1e-15)

    def test_round_trip_no_allocation(self) -> None:
        b = ErrorBudget(name="t", unit="urad", contributors=(BudgetContributor("a", 1.0),))
        assert ErrorBudget.from_dict(b.to_dict()) == b
