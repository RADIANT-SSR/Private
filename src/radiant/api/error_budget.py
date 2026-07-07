"""Error budget — RSS combination and allocation tracking (Gaps 23 + 28).

One generic model for quadrature (root-sum-square) error budgets:
jitter budgets (reaction wheels, cryocoolers, structural modes, ACS
residual — RMS in µrad) and WFE budgets (fabrication, alignment,
thermal, gravity release — RMS in waves) share the same math:

    total = sqrt( Σ_i v_i² )

An optional *allocation* (the requirement) enables margin tracking and
"how much is left for a new contributor" queries:

    remaining = sqrt( allocation² − total² )

The unit field is display metadata only — all contributors in one
budget must share it; the math is unit-agnostic RSS.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from radiant.core.exceptions import RadiantError


class ErrorBudgetError(RadiantError):
    """Raised for invalid budget construction or queries."""


@dataclass(frozen=True)
class BudgetContributor:
    """One RSS contributor: a named RMS value with an optional note."""

    name: str
    value: float
    note: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ErrorBudgetError("BudgetContributor: name must be non-empty.")
        if self.value < 0.0:
            raise ErrorBudgetError(
                f"BudgetContributor '{self.name}': RMS value must be "
                f"non-negative, got {self.value}. RSS contributors are "
                "magnitudes; encode direction elsewhere."
            )


@dataclass(frozen=True)
class ErrorBudget:
    """Quadrature error budget with optional allocation tracking.

    Parameters
    ----------
    name:
        Budget label (e.g. ``"jitter"``, ``"wfe"``).
    unit:
        Display unit shared by every contributor (e.g. ``"urad"``,
        ``"waves"``). Metadata only.
    contributors:
        RSS contributors.
    allocation:
        Optional total allocation (the requirement) in the same unit.
    """

    name: str
    unit: str
    contributors: tuple[BudgetContributor, ...] = field(default_factory=tuple)
    allocation: float | None = None

    def __post_init__(self) -> None:
        if self.allocation is not None and self.allocation <= 0.0:
            raise ErrorBudgetError(
                f"ErrorBudget '{self.name}': allocation must be positive, "
                f"got {self.allocation}."
            )
        names = [c.name for c in self.contributors]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ErrorBudgetError(
                f"ErrorBudget '{self.name}': duplicate contributor name(s) "
                f"{sorted(dupes)}. Each contributor appears once; combine "
                "sub-sources before adding or use distinct names."
            )

    # -- Math ---------------------------------------------------------------

    @property
    def rss_total(self) -> float:
        """Root-sum-square of all contributors."""
        return math.sqrt(sum(c.value**2 for c in self.contributors))

    @property
    def over_budget(self) -> bool:
        """True when the RSS total exceeds the allocation."""
        return self.allocation is not None and self.rss_total > self.allocation

    @property
    def margin(self) -> float | None:
        """Linear margin ``allocation − rss_total`` (None without allocation)."""
        if self.allocation is None:
            return None
        return self.allocation - self.rss_total

    def remaining_allocation(self) -> float:
        """RSS headroom for a new contributor: ``sqrt(alloc² − total²)``.

        Returns 0.0 when the budget is exactly consumed or over budget
        (an over-budget state is visible via :attr:`over_budget`).
        """
        if self.allocation is None:
            raise ErrorBudgetError(
                f"ErrorBudget '{self.name}': remaining_allocation() requires "
                "an allocation. Construct the budget with allocation=<requirement>."
            )
        head = self.allocation**2 - self.rss_total**2
        return math.sqrt(head) if head > 0.0 else 0.0

    # -- Construction -------------------------------------------------------

    def with_contributor(self, name: str, value: float, note: str = "") -> ErrorBudget:
        """Return a new budget with one more contributor."""
        return ErrorBudget(
            name=self.name,
            unit=self.unit,
            contributors=(*self.contributors, BudgetContributor(name, value, note)),
            allocation=self.allocation,
        )

    # -- Reporting ----------------------------------------------------------

    def table(self) -> str:
        """Formatted budget table with per-contributor variance share."""
        total = self.rss_total
        lines = [
            f"Error budget: {self.name} [{self.unit}]",
            f"{'Contributor':<28s} {'RMS':>12s} {'Share':>8s}",
        ]
        for c in sorted(self.contributors, key=lambda c: -c.value):
            share = (c.value**2 / total**2) if total > 0.0 else 0.0
            note = f"  ({c.note})" if c.note else ""
            lines.append(f"{c.name:<28s} {c.value:>12.4g} {share:>7.1%}{note}")
        lines.append(f"{'RSS total':<28s} {total:>12.4g}")
        if self.allocation is not None:
            margin = self.margin
            assert margin is not None
            status = "OVER BUDGET" if self.over_budget else "within budget"
            lines.append(f"{'Allocation':<28s} {self.allocation:>12.4g}")
            lines.append(f"{'Margin (linear)':<28s} {margin:>12.4g}  {status}")
            lines.append(f"{'RSS headroom':<28s} {self.remaining_allocation():>12.4g}")
        return "\n".join(lines)

    # -- Serialization (Category B round-trip) --------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "allocation": self.allocation,
            "contributors": [
                {"name": c.name, "value": c.value, "note": c.note} for c in self.contributors
            ],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ErrorBudget:
        return cls(
            name=d["name"],
            unit=d["unit"],
            allocation=d.get("allocation"),
            contributors=tuple(
                BudgetContributor(c["name"], c["value"], c.get("note", ""))
                for c in d.get("contributors", ())
            ),
        )
