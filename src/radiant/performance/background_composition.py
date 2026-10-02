"""Background composition — which term owns the no-target pedestal (Gap 132).

The external review of 2026-09-30 ranked this the single highest-value
informational addition RADIANT could make, above the warning it filed as its
top defect. The reasoning is worth keeping: CU-380 — warm-optics emission
evaluating to *identically zero* while the term appeared to be switched on —
cost two releases and an outside reconciliation to find, and one proportioned
line of output would have made it obvious in seconds. The breakdown generalises
where a warning does not: it surfaces the next silently-zero dominant term too,
whatever that turns out to be.

So this module answers one question: **of the charge in a pixel that is not the
target, what fraction is each contributor?**

    nearfield  warm-optics self-emission        [e-]
    scene      the scene/background pedestal    [e-]
    dark       dark current                     [e-]
    stray      stray light                      [e-]
    glow       detector / ROIC glow             [e-]

Three deliberate choices
------------------------
**Shares are of the pedestal, not of the signal.** A share of signal would move
when the target changes, which makes it useless for the question "where is my
background coming from". The pedestal total is published alongside so a reader
can form any other ratio they want.

**A zero total yields zero shares, not NaN.** A photon-starved or fully
cold-shielded configuration has no pedestal, and "0 % of nothing" is the honest
reading. Returning NaN here would propagate into a reporting surface for a
configuration that is perfectly well-defined — and the metric layer's
result-typed-failure carve-out (Rule 17, ADR-B) exists for undefined physics,
which this is not.

**``dominant`` is ``None`` when the total is zero.** Naming a dominant
contributor among five zeros would be arbitrary; saying "there isn't one" is
not.

This is a pure view over values other stages already published — it computes no
new physics, and deliberately so: anything it had to derive itself would be a
second opinion on a number the chain already owns.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from radiant.performance.errors import PerformanceValidationError

__all__ = ["BACKGROUND_TERMS", "BackgroundComposition", "compute_background_composition"]

#: The pedestal contributors, in the order a report should read them: the two
#: that dominate a thermal design first, then the detector-intrinsic terms.
BACKGROUND_TERMS: Final[tuple[str, ...]] = ("nearfield", "scene", "dark", "stray", "glow")


@dataclass(frozen=True, slots=True)
class BackgroundComposition:
    """The no-target pedestal, decomposed.

    Attributes
    ----------
    terms:
        Term name -> accumulated charge [e-]. Always carries every member of
        :data:`BACKGROUND_TERMS`, including the zeros — an absent key would
        hide exactly the silently-zero case this exists to expose.
    total_e:
        Sum of ``terms`` [e-].
    shares:
        Term name -> fraction of ``total_e`` in [0, 1]. All zeros when
        ``total_e`` is zero.
    dominant:
        The largest contributor, or ``None`` when ``total_e`` is zero.
    """

    terms: dict[str, float]
    total_e: float
    shares: dict[str, float]
    dominant: str | None

    def share_pct(self, term: str) -> float:
        """``term``'s share as a percentage, for display."""
        if term not in self.shares:
            raise PerformanceValidationError(
                f"BackgroundComposition.share_pct: '{term}' is not a background "
                f"term. Known terms: {', '.join(BACKGROUND_TERMS)}."
            )
        return 100.0 * self.shares[term]

    def zero_terms(self) -> tuple[str, ...]:
        """Terms that are exactly zero, in :data:`BACKGROUND_TERMS` order.

        The CU-380 reading: a thermal-band run reporting ``nearfield`` here is
        reporting that its warm optics contributes nothing at all.
        """
        return tuple(t for t in BACKGROUND_TERMS if self.terms[t] == 0.0)


def compute_background_composition(
    *,
    nearfield_e: float,
    scene_e: float,
    dark_e: float,
    stray_e: float,
    glow_e: float,
) -> BackgroundComposition:
    """Decompose the no-target pedestal into its contributors.

    Every argument is an accumulated charge in electrons, as the detector stage
    publishes it. Negative or non-finite input is an error rather than a
    clamped value: a negative charge is not a small background, it is a broken
    one (Rule 16).
    """
    raw = {
        "nearfield": nearfield_e,
        "scene": scene_e,
        "dark": dark_e,
        "stray": stray_e,
        "glow": glow_e,
    }
    for name, value in raw.items():
        if not math.isfinite(value):
            raise PerformanceValidationError(
                f"compute_background_composition: {name}_e = {value} is not "
                f"finite. A background contributor must be a finite charge in "
                f"electrons; a non-finite value means an upstream stage "
                f"produced one."
            )
        if value < 0.0:
            raise PerformanceValidationError(
                f"compute_background_composition: {name}_e = {value} is "
                f"negative. Accumulated charge cannot be negative — this is an "
                f"upstream defect, not a small background."
            )

    total = math.fsum(raw.values())
    if total == 0.0:
        return BackgroundComposition(
            terms=raw,
            total_e=0.0,
            shares=dict.fromkeys(BACKGROUND_TERMS, 0.0),
            dominant=None,
        )
    shares = {name: raw[name] / total for name in BACKGROUND_TERMS}
    dominant = max(BACKGROUND_TERMS, key=lambda name: raw[name])
    return BackgroundComposition(terms=raw, total_e=total, shares=shares, dominant=dominant)
