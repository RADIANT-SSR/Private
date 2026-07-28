"""Per-contributor MTF sampled at several fractions of Nyquist (Rule 19: one computation).

The MTF-at-Nyquist budget (:mod:`radiant.performance.mtf_budget`) answers "how
much does each contributor cost me *at the sampling limit*". That single column
hides where a contributor does its damage: a term that is 0.95 at Nyquist may
still have taken 20 % out of the mid-band, and two systems with identical
MTF@Nyquist can look very different at half Nyquist. Sampling each contributor
at a **ladder of fractions** of Nyquist — 0.25, 0.5, 0.75, 1.0 by default —
shows the shape of the roll-off in a table, not just its endpoint (owner
walkthrough item 10).

This module only *samples* curves the MTF product path already computed; it
introduces no new MTF physics and no new degradation. Each contributor's curve
and the frequency axis both come from
:class:`~radiant.performance.mtf_budget.MTFBudgetResult`, so a term appears here
iff it appears there.

Interpolation is linear on the frequency axis, matching
:func:`radiant.performance.system_mtf.mtf_at_freq`. A requested fraction that
falls beyond the computed axis yields ``None`` for that cell rather than an
extrapolated number — the table says "not computed here", which is honest, where
an extrapolated MTF would be invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt

from radiant.performance.errors import PerformanceValidationError

#: The fractions of Nyquist the GUI budget table shows by default (owner walkthrough
#: item 10: "evaluate at 0.25, 0.5, 0.75 and 1 Nyquist").
DEFAULT_FRACTIONS: Final[tuple[float, ...]] = (0.25, 0.5, 0.75, 1.0)


@dataclass(frozen=True, slots=True)
class MTFFractionTable:
    """Per-contributor MTF sampled at fractions of Nyquist, for one axis.

    Attributes
    ----------
    axis:
        ``"x"`` or ``"y"`` — which axis' curves were sampled.
    fractions:
        The Nyquist fractions sampled, in the order the columns should appear.
    nyquist_cycles_per_mrad:
        The Nyquist frequency the fractions are taken of.
    per_term:
        Contributor base name → one MTF value per entry in *fractions*
        (``None`` where the fraction lies outside the computed frequency axis).
    system:
        The system MTF (the product of all contributors) at the same fractions.
    """

    axis: str
    fractions: tuple[float, ...]
    nyquist_cycles_per_mrad: float
    per_term: dict[str, tuple[float | None, ...]]
    system: tuple[float | None, ...]

    def term_names(self) -> list[str]:
        """Contributor names in stable (sorted) order."""
        return sorted(self.per_term)


def _sample(
    freq: npt.NDArray[np.float64],
    curve: npt.NDArray[np.float64],
    targets: tuple[float, ...],
) -> tuple[float | None, ...]:
    """Linearly interpolate *curve* at each target frequency; ``None`` when out of range."""
    lo, hi = float(freq[0]), float(freq[-1])
    out: list[float | None] = []
    for target in targets:
        if target < lo or target > hi:
            out.append(None)
        else:
            out.append(float(np.interp(target, freq, curve)))
    return tuple(out)


def compute_mtf_fraction_table(
    budget: object,
    nyquist_cycles_per_mrad: float,
    axis: str = "x",
    fractions: tuple[float, ...] = DEFAULT_FRACTIONS,
) -> MTFFractionTable:
    """Sample every contributor's MTF curve at *fractions* of Nyquist, for one *axis*.

    Parameters
    ----------
    budget:
        An :class:`~radiant.performance.mtf_budget.MTFBudgetResult` — supplies
        ``freq_cycles_per_mrad``, ``per_term`` (name → curve) and
        ``system_mtf_x`` / ``system_mtf_y``.
    nyquist_cycles_per_mrad:
        The detector Nyquist frequency on the same axis as ``freq_cycles_per_mrad``.
        Must be > 0.
    axis:
        ``"x"`` or ``"y"``. Contributors are stored with ``_x`` / ``_y`` suffixes;
        only the matching ones are sampled and the suffix is stripped from the name.
    fractions:
        Fractions of Nyquist to sample, in column order.

    Raises
    ------
    PerformanceValidationError
        When *axis* is not ``"x"``/``"y"``, when *nyquist_cycles_per_mrad* is not
        positive, or when a fraction is not positive.
    """
    if axis not in ("x", "y"):
        raise PerformanceValidationError(
            f"compute_mtf_fraction_table: axis must be 'x' or 'y', got {axis!r}."
        )
    if nyquist_cycles_per_mrad <= 0.0:
        raise PerformanceValidationError(
            "compute_mtf_fraction_table: nyquist_cycles_per_mrad must be > 0, "
            f"got {nyquist_cycles_per_mrad}."
        )
    if any(f <= 0.0 for f in fractions):
        raise PerformanceValidationError(
            f"compute_mtf_fraction_table: every fraction must be > 0, got {fractions}."
        )

    freq = np.asarray(getattr(budget, "freq_cycles_per_mrad", np.empty(0)), dtype=np.float64)
    if freq.size < 2:
        raise PerformanceValidationError(
            "compute_mtf_fraction_table: the budget carries no frequency axis to "
            "interpolate on (freq_cycles_per_mrad has fewer than 2 samples)."
        )

    targets = tuple(f * nyquist_cycles_per_mrad for f in fractions)
    suffix = f"_{axis}"
    per_term_curves: dict[str, npt.NDArray[np.float64]] = getattr(budget, "per_term", {}) or {}

    sampled: dict[str, tuple[float | None, ...]] = {}
    for name, curve in per_term_curves.items():
        if not name.endswith(suffix):
            continue
        arr = np.asarray(curve, dtype=np.float64)
        if arr.shape != freq.shape:
            continue
        sampled[name[: -len(suffix)]] = _sample(freq, arr, targets)

    system_curve = getattr(budget, f"system_mtf_{axis}", None)
    system = (
        _sample(freq, np.asarray(system_curve, dtype=np.float64), targets)
        if system_curve is not None
        else tuple(None for _ in targets)
    )

    return MTFFractionTable(
        axis=axis,
        fractions=tuple(fractions),
        nyquist_cycles_per_mrad=float(nyquist_cycles_per_mrad),
        per_term=sampled,
        system=system,
    )


__all__ = ["DEFAULT_FRACTIONS", "MTFFractionTable", "compute_mtf_fraction_table"]
