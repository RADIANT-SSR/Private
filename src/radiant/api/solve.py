"""Inverse solver — find the parameter value that hits a target metric (Gap 10).

Root-finds ``metric(run(params | {param: x})) − target = 0`` over a
user-supplied bracket with Brent's method. This replaces the
sweep-and-interpolate workaround for inverse analyses ("what
nearfield_fraction gives 44,000 e⁻ background?", "what aperture gives
SNR 50?").

The forward model is treated as a black box; each solver iteration is
one full chain evaluation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from scipy.optimize import brentq  # type: ignore[import-untyped]

from radiant.core.exceptions import RadiantError
from radiant.core.parameters import ParameterSet
from radiant.io.results import ChainResult

MetricFn = Callable[[ChainResult], float]


def _is_clipped(result: ChainResult) -> bool:
    """Whether *result*'s well saturated (False for a result with no readout stage)."""
    try:
        return bool(result.well_status().is_saturated)
    except KeyError:
        return False


class SolveBracketError(RadiantError):
    """Raised when the bracket does not straddle the target.

    ``saturated`` (CU-375 F-18) is True when both endpoint evaluations
    hard-clipped the well: the metric is flat because the signal saturates,
    and widening the bracket cannot help — the message says so.
    """

    def __init__(self, message: str, *, saturated: bool = False) -> None:
        super().__init__(message)
        self.saturated = saturated


@dataclass(frozen=True)
class SolveResult:
    """Result of an inverse solve.

    Attributes
    ----------
    param_name:
        Dot-path of the solved parameter.
    metric_name:
        Metric that was targeted.
    target:
        Requested metric value.
    solution:
        Parameter value (input units) achieving the target.
    achieved:
        Metric actually obtained at ``solution``.
    n_evaluations:
        Number of forward-chain evaluations consumed.
    result:
        Full :class:`ChainResult` at the solution.
    """

    param_name: str
    metric_name: str
    target: float
    solution: float
    achieved: float
    n_evaluations: int
    result: ChainResult


def solve_for(
    run_fn: Callable[[ParameterSet], ChainResult],
    params: ParameterSet,
    param_name: str,
    target: float,
    bounds: tuple[float, float],
    metric: MetricFn,
    metric_name: str = "metric",
    *,
    rtol: float = 1e-6,
    max_iter: int = 100,
) -> SolveResult:
    """Find the parameter value in *bounds* where *metric* equals *target*.

    Parameters
    ----------
    run_fn:
        Callable evaluating the chain, typically ``session.run``.
    params:
        Baseline resolved ParameterSet (copied per evaluation).
    param_name:
        Dot-path of the parameter to solve for (input units).
    target:
        Target metric value.
    bounds:
        ``(lo, hi)`` bracket in the parameter's input units. The metric
        must straddle *target* across the bracket.
    metric:
        Metric extractor ``(ChainResult) -> float``.
    metric_name:
        Label for reporting.
    rtol:
        Relative tolerance on the parameter value.
    max_iter:
        Maximum Brent iterations.

    Raises
    ------
    SolveBracketError
        If the metric does not straddle *target* over *bounds* — the
        error reports both endpoint values so the user can move the
        bracket.
    """
    from radiant.api.sweep import _clone_with

    lo, hi = float(bounds[0]), float(bounds[1])
    if not lo < hi:
        raise SolveBracketError(
            f"solve_for('{param_name}'): bounds must satisfy lo < hi, got ({lo}, {hi})."
        )

    n_evals = 0
    last_result: dict[str, ChainResult] = {}

    def f(x: float) -> float:
        nonlocal n_evals
        n_evals += 1
        r = run_fn(_clone_with(params, param_name, float(x)))
        last_result["r"] = r
        value = float(metric(r))
        return value - target

    f_lo = f(lo)
    clipped_lo = _is_clipped(last_result["r"])
    f_hi = f(hi)
    clipped_hi = _is_clipped(last_result["r"])
    if f_lo == 0.0:
        root = lo
    elif f_hi == 0.0:
        root = hi
    elif f_lo * f_hi > 0.0:
        saturated = clipped_lo and clipped_hi
        # CU-375 F-18: over a clipped configuration the metric is flat and
        # 'widen the bounds' cannot help — say what is actually wrong.
        advice = (
            "Both bracket endpoints hard-clip the detector well, so the signal "
            "saturates and the metric is flat here; reduce the signal (integration "
            "time, aperture) or raise the full-well capacity before solving."
            if saturated
            else "Widen or shift the bounds so the target lies between the endpoint metric values."
        )
        raise SolveBracketError(
            f"solve_for('{param_name}'): {metric_name} does not reach the "
            f"target {target:g} inside the bracket [{lo:g}, {hi:g}] — "
            f"{metric_name}({lo:g}) = {f_lo + target:g}, "
            f"{metric_name}({hi:g}) = {f_hi + target:g}. " + advice,
            saturated=saturated,
        )
    else:
        root = float(brentq(f, lo, hi, rtol=rtol, maxiter=max_iter))

    # Final evaluation at the root for the returned result/achieved value.
    final = run_fn(_clone_with(params, param_name, root))
    n_evals += 1
    achieved = float(metric(final))

    return SolveResult(
        param_name=param_name,
        metric_name=metric_name,
        target=target,
        solution=root,
        achieved=achieved,
        n_evaluations=n_evals,
        result=final,
    )
