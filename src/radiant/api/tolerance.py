"""Monte Carlo tolerance analysis.

Samples all toleranced parameters from their distributions, re-evaluates
the chain for each trial, and collects metrics into a
:class:`MonteCarloResult` with statistical summaries.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from radiant.core.parameters import ParameterSet
from radiant.io.results import ChainResult

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# MonteCarloResult
# ------------------------------------------------------------------


@dataclass(frozen=True)
class MonteCarloResult:
    """Result of a Monte Carlo tolerance analysis.

    Attributes
    ----------
    n_trials:
        Number of MC trials executed.
    seed:
        RNG seed used (for reproducibility).
    metric_names:
        Ordered tuple of metric keys.
    metric_array:
        2-D array shape ``(n_trials, n_metrics)``, one row per trial.
    sampled_params:
        Dict mapping param name → 1-D array of sampled values per trial.
    results:
        Full ChainResult for each trial (optional).
    """

    n_trials: int
    seed: int
    metric_names: tuple[str, ...]
    metric_array: npt.NDArray[np.float64]
    sampled_params: dict[str, npt.NDArray[np.float64]] = field(default_factory=dict)
    results: tuple[ChainResult, ...] = field(default_factory=tuple)

    # -- Statistical summaries ------------------------------------------

    def _col(self, metric: str) -> npt.NDArray[np.float64]:
        """Get the column for a given metric name."""
        try:
            idx = self.metric_names.index(metric)
        except ValueError:
            raise KeyError(
                f"MonteCarloResult: metric '{metric}' not found. "
                f"Available: {list(self.metric_names)}"
            ) from None
        return self.metric_array[:, idx]

    def mean(self, metric: str) -> float:
        """Mean of a metric across all trials."""
        return float(np.nanmean(self._col(metric)))

    def std(self, metric: str) -> float:
        """Standard deviation of a metric across all trials."""
        return float(np.nanstd(self._col(metric), ddof=1))

    def percentile(self, metric: str, pct: float) -> float:
        """Percentile of a metric (0–100)."""
        return float(np.nanpercentile(self._col(metric), pct))

    def probability_of_exceeding(self, metric: str, threshold: float) -> float:
        """Fraction of trials where metric >= threshold."""
        col = self._col(metric)
        valid = col[~np.isnan(col)]
        if valid.size == 0:
            return 0.0
        return float(np.sum(valid >= threshold) / valid.size)

    def correlation(self, metric: str) -> dict[str, float]:
        """Pearson correlation between each sampled param and a metric.

        Returns dict mapping param_name → correlation coefficient.
        """
        col = self._col(metric)
        corr: dict[str, float] = {}
        for pname, pvals in self.sampled_params.items():
            valid = ~(np.isnan(col) | np.isnan(pvals))
            if valid.sum() < 3:
                corr[pname] = float("nan")
            else:
                r = np.corrcoef(pvals[valid], col[valid])[0, 1]
                corr[pname] = float(r)
        return corr

    def to_dict(self) -> dict[str, npt.NDArray[np.float64]]:
        """Return dict mapping metric name → 1-D array of trial values."""
        return {name: self.metric_array[:, i] for i, name in enumerate(self.metric_names)}


# ------------------------------------------------------------------
# monte_carlo()
# ------------------------------------------------------------------


def monte_carlo(
    run_fn: Callable[[ParameterSet], ChainResult],
    params: ParameterSet,
    n_trials: int = 1000,
    seed: int = 42,
    metric_names: tuple[str, ...] | None = None,
    keep_results: bool = False,
) -> MonteCarloResult:
    """Run Monte Carlo tolerance analysis.

    Parameters
    ----------
    run_fn:
        Callable ``(ParameterSet) -> ChainResult``.
    params:
        Resolved ParameterSet with at least one tolerance set.
    n_trials:
        Number of MC trials.
    seed:
        Random seed for reproducibility.
    metric_names:
        Metric keys to record. If None, auto-detected from first trial.
    keep_results:
        If True, store every ChainResult (memory-heavy).
    """
    if not params._tolerances:
        raise ValueError(
            "monte_carlo: no tolerances set on params. Use "
            "params.set_tolerance(name, tolerance) before calling."
        )

    # Ensure resolved (set_tolerance marks unresolved)
    if not params._resolved_flag:
        params.resolve()

    rng = np.random.default_rng(seed)

    # Pre-allocate sampled param tracking
    tol_names = sorted(params._tolerances.keys())
    sampled_arrays: dict[str, list[float]] = {name: [] for name in tol_names}

    first_result: ChainResult | None = None
    results_list: list[ChainResult] = []
    metric_rows: list[list[float]] = []

    for _trial in range(n_trials):
        ps = params.sample(rng)

        # Record sampled values
        for pname in tol_names:
            sampled_arrays[pname].append(float(ps.get(pname)))

        r = run_fn(ps)

        if first_result is None:
            first_result = r
            if metric_names is None:
                metric_names = tuple(sorted(r.metrics.keys()))

        row = [float(r.metrics.get(m, float("nan"))) for m in metric_names]
        metric_rows.append(row)

        if keep_results:
            results_list.append(r)

    assert metric_names is not None  # guaranteed after first iteration

    metric_array = np.array(metric_rows, dtype=np.float64)
    sampled_param_arrays = {
        name: np.array(vals, dtype=np.float64) for name, vals in sampled_arrays.items()
    }

    return MonteCarloResult(
        n_trials=n_trials,
        seed=seed,
        metric_names=metric_names,
        metric_array=metric_array,
        sampled_params=sampled_param_arrays,
        results=tuple(results_list) if keep_results else (),
    )
