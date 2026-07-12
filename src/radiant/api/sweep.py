"""Parameter sweeps — 1-D and 2-D.

Sweeps re-evaluate the signal chain at each point in a parameter grid
and collect the results. The heavy lifting is done by
:class:`~radiant.api.session.RadiantSession`; this module adds the
bookkeeping for iterating over parameter values, optional
parallelization, and result containers.
"""

from __future__ import annotations

import logging
import pickle
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from radiant.api._progress import CancelFn, ProgressFn, check_cancel
from radiant.api.errors import ApiValidationError
from radiant.core.parameters import ParameterSet
from radiant.io.results import ChainResult

logger = logging.getLogger(__name__)

# Type alias for the metric extractor.
MetricFn = Callable[[ChainResult], float]


class _PickleFallback(Exception):
    """Internal: signals that pool.submit failed due to pickling."""


def _default_metric(result: ChainResult) -> float:
    """Extract SNR from a ChainResult."""
    snr = result.metrics.get("snr")
    if snr is None:
        raise ApiValidationError(
            "sweep: default metric is 'snr' but it was not computed. "
            "Pass a custom metric function or ensure PerformanceStage runs."
        )
    return float(snr)


# ------------------------------------------------------------------
# SweepResult
# ------------------------------------------------------------------


@dataclass(frozen=True)
class SweepResult:
    """Result of a 1-D parameter sweep.

    Attributes
    ----------
    param_name:
        Dot-path of the swept parameter.
    values:
        Swept parameter values (1-D array).
    metric_values:
        Metric value at each sweep point (1-D array, same length).
    results:
        Full :class:`ChainResult` at each point (optional; empty if
        ``keep_results=False``).
    metric_name:
        Human-readable label for the metric.
    """

    param_name: str
    values: npt.NDArray[np.float64]
    metric_values: npt.NDArray[np.float64]
    results: tuple[ChainResult, ...] = field(default_factory=tuple)
    metric_name: str = "metric"

    def __getitem__(self, metric_key: str) -> npt.NDArray[np.float64]:
        """Look up any metric across all stored results.

        Raises ``KeyError`` if results were not kept or metric is missing.
        """
        if not self.results:
            raise KeyError(
                f"SweepResult['{metric_key}']: full results were not kept. "
                "Re-run the sweep with keep_results=True."
            )
        return np.array(
            [r.metrics.get(metric_key, float("nan")) for r in self.results],
            dtype=np.float64,
        )

    def at_metric_threshold(
        self,
        threshold: float,
    ) -> tuple[float, float] | None:
        """Find the first sweep point where metric >= threshold.

        Returns ``(param_value, metric_value)`` or ``None`` if never exceeded.
        """
        for i, mv in enumerate(self.metric_values):
            if mv >= threshold:
                return float(self.values[i]), float(mv)
        return None


# ------------------------------------------------------------------
# Sweep2DResult
# ------------------------------------------------------------------


@dataclass(frozen=True)
class Sweep2DResult:
    """Result of a 2-D parameter sweep.

    Attributes
    ----------
    param1_name, param2_name:
        Dot-paths of the two swept parameters.
    values1, values2:
        1-D arrays of the two sweep axes.
    grid:
        2-D metric array, shape ``(len(values1), len(values2))``.
    metric_name:
        Human-readable label for the metric.
    """

    param1_name: str
    param2_name: str
    values1: npt.NDArray[np.float64]
    values2: npt.NDArray[np.float64]
    grid: npt.NDArray[np.float64]
    metric_name: str = "metric"


# ------------------------------------------------------------------
# sweep()
# ------------------------------------------------------------------


def sweep(
    run_fn: Callable[[ParameterSet], ChainResult],
    params: ParameterSet,
    param_name: str,
    values: Sequence[float] | npt.NDArray[np.float64],
    metric: MetricFn | None = None,
    metric_name: str = "snr",
    keep_results: bool = True,
    n_workers: int = 1,
    progress: ProgressFn | None = None,
    cancel: CancelFn | None = None,
) -> SweepResult:
    """Run a 1-D parameter sweep.

    Parameters
    ----------
    run_fn:
        Callable that takes a :class:`ParameterSet` and returns a
        :class:`ChainResult`.  Typically ``session.run``.
    params:
        Baseline resolved ParameterSet. A copy is made for each point.
    param_name:
        Dot-path of the parameter to sweep.
    values:
        Array of values to sweep over.
    metric:
        Callable ``(ChainResult) -> float``. Defaults to ``snr``.
    metric_name:
        Label stored in the result.
    keep_results:
        If True, store every ChainResult (memory-heavy for large sweeps).
    n_workers:
        Number of parallel workers. 1 = sequential (default).
    progress:
        Optional ``progress(done, total)`` callback, called after each
        completed point (Gap 72).
    cancel:
        Optional ``cancel() -> bool`` poll; True aborts with
        :class:`~radiant.api._progress.OperationCancelledError`.
    """
    if metric is None:
        metric = _default_metric

    vals = np.asarray(values, dtype=np.float64)

    if n_workers > 1:
        metric_vals, results_list = _sweep_parallel(
            run_fn,
            params,
            param_name,
            vals,
            metric,
            keep_results,
            n_workers,
            progress,
            cancel,
        )
    else:
        metric_vals, results_list = _sweep_sequential(
            run_fn,
            params,
            param_name,
            vals,
            metric,
            keep_results,
            progress,
            cancel,
        )

    return SweepResult(
        param_name=param_name,
        values=vals,
        metric_values=metric_vals,
        results=tuple(results_list) if keep_results else (),
        metric_name=metric_name,
    )


def _sweep_sequential(
    run_fn: Callable[[ParameterSet], ChainResult],
    params: ParameterSet,
    param_name: str,
    vals: npt.NDArray[np.float64],
    metric: MetricFn,
    keep_results: bool,
    progress: ProgressFn | None,
    cancel: CancelFn | None,
) -> tuple[npt.NDArray[np.float64], list[ChainResult]]:
    """Execute sweep points one at a time on the calling thread."""
    n = len(vals)
    metric_vals = np.empty(n, dtype=np.float64)
    results_list: list[ChainResult] = []
    for i, v in enumerate(vals):
        check_cancel(cancel, f"sweep({param_name})", i, n)
        ps = _clone_with(params, param_name, float(v))
        r = run_fn(ps)
        metric_vals[i] = metric(r)
        if keep_results:
            results_list.append(r)
        if progress is not None:
            progress(i + 1, n)
    return metric_vals, results_list


def _sweep_parallel(
    run_fn: Callable[[ParameterSet], ChainResult],
    params: ParameterSet,
    param_name: str,
    vals: npt.NDArray[np.float64],
    metric: MetricFn,
    keep_results: bool,
    n_workers: int,
    progress: ProgressFn | None,
    cancel: CancelFn | None,
) -> tuple[npt.NDArray[np.float64], list[ChainResult]]:
    """Execute sweep points in parallel using ProcessPoolExecutor.

    ProcessPoolExecutor requires the callable, each ParameterSet, and
    each returned ChainResult to pickle. Pickling is asynchronous —
    submit-time succeeds and the failure surfaces at ``fut.result()``
    as ``pickle.PicklingError`` (or the pool dies with
    ``BrokenProcessPool``), so the fallback catches at both points
    (CU-072). On any pickling failure the whole sweep re-runs
    sequentially — futures that did complete are discarded rather than
    mixed with re-runs.
    """
    metric_vals = np.empty(len(vals), dtype=np.float64)
    results_list: list[ChainResult] = []
    try:
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            param_sets = [_clone_with(params, param_name, float(v)) for v in vals]
            try:
                futures = [pool.submit(run_fn, ps) for ps in param_sets]
            except (TypeError, AttributeError, pickle.PicklingError) as exc:
                raise _PickleFallback(exc) from exc
            n = len(futures)
            for i, fut in enumerate(futures):
                check_cancel(cancel, f"sweep({param_name})", i, n)
                try:
                    r = fut.result()
                except (pickle.PicklingError, BrokenProcessPool, TypeError, AttributeError) as exc:
                    # Async pickling failure (CU-072): the documented
                    # sequential fallback, previously unreachable.
                    raise _PickleFallback(exc) from exc
                metric_vals[i] = metric(r)
                if keep_results:
                    results_list.append(r)
                if progress is not None:
                    progress(i + 1, n)
    except _PickleFallback as exc:
        logger.warning(
            "Parallel sweep failed (%s); falling back to sequential.",
            exc.__cause__,
        )
        return _sweep_sequential(
            run_fn, params, param_name, vals, metric, keep_results, progress, cancel
        )
    return metric_vals, results_list


# ------------------------------------------------------------------
# sweep_2d()
# ------------------------------------------------------------------


def sweep_2d(
    run_fn: Callable[[ParameterSet], ChainResult],
    params: ParameterSet,
    param1_name: str,
    values1: Sequence[float] | npt.NDArray[np.float64],
    param2_name: str,
    values2: Sequence[float] | npt.NDArray[np.float64],
    metric: MetricFn | None = None,
    metric_name: str = "snr",
    progress: ProgressFn | None = None,
    cancel: CancelFn | None = None,
) -> Sweep2DResult:
    """Run a 2-D parameter sweep.

    Parameters
    ----------
    run_fn:
        Callable ``(ParameterSet) -> ChainResult``.
    params:
        Baseline resolved ParameterSet.
    param1_name, param2_name:
        Dot-paths of the two swept parameters.
    values1, values2:
        Arrays of values for each axis.
    metric:
        Callable ``(ChainResult) -> float``. Defaults to ``snr``.
    metric_name:
        Label stored in the result.
    progress:
        Optional ``progress(done, total)`` callback, called after each
        grid cell (Gap 72). ``total`` is ``len(values1) * len(values2)``.
    cancel:
        Optional ``cancel() -> bool`` poll; True aborts with
        :class:`~radiant.api._progress.OperationCancelledError`.
    """
    if metric is None:
        metric = _default_metric

    v1 = np.asarray(values1, dtype=np.float64)
    v2 = np.asarray(values2, dtype=np.float64)
    grid = np.empty((v1.size, v2.size), dtype=np.float64)

    total = v1.size * v2.size
    done = 0
    op = f"sweep_2d({param1_name}, {param2_name})"
    for i, a in enumerate(v1):
        for j, b in enumerate(v2):
            check_cancel(cancel, op, done, total)
            ps = _clone_with(params, param1_name, float(a))
            ps = _clone_with(ps, param2_name, float(b))
            r = run_fn(ps)
            grid[i, j] = metric(r)
            done += 1
            if progress is not None:
                progress(done, total)

    return Sweep2DResult(
        param1_name=param1_name,
        param2_name=param2_name,
        values1=v1,
        values2=v2,
        grid=grid,
        metric_name=metric_name,
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _clone_with(
    params: ParameterSet,
    param_name: str,
    value: float,
) -> ParameterSet:
    """Clone a ParameterSet with one parameter overridden.

    Creates a fresh ParameterSet, copies all inputs from *params*,
    overrides *param_name*, and resolves.
    """
    from radiant.core.parameters import Provenance

    new = params.copy()
    new.set(param_name, value, Provenance.USER_SET, "sweep")
    new.resolve()
    return new
