"""One-at-a-time sensitivity analysis.

Perturbs each parameter by ``±delta_fraction × value``, evaluates the
chain, and computes the normalized sensitivity ``(dMetric/Metric) /
(dParam/Param)`` — a dimensionless elasticity.

This is cheaper than Monte Carlo for ranking which parameters have
the largest impact on a metric.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.api.sweep import _clone_with
from radiant.core.parameters import ParameterSet
from radiant.io.results import ChainResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SensitivityEntry:
    """Sensitivity of a single parameter.

    Attributes
    ----------
    param_name:
        Dot-path of the perturbed parameter.
    nominal_value:
        Baseline parameter value.
    metric_nominal:
        Metric value at the baseline.
    metric_plus:
        Metric value at +delta.
    metric_minus:
        Metric value at −delta.
    sensitivity:
        Normalized sensitivity: (ΔM/M) / (Δp/p).
    delta_fraction:
        The fractional perturbation applied.
    """

    param_name: str
    nominal_value: float
    metric_nominal: float
    metric_plus: float
    metric_minus: float
    sensitivity: float
    delta_fraction: float


@dataclass(frozen=True)
class SensitivityResult:
    """Result of a one-at-a-time sensitivity analysis.

    Attributes
    ----------
    entries:
        One :class:`SensitivityEntry` per parameter, sorted by
        absolute sensitivity (descending).
    metric_name:
        Human-readable label.
    """

    entries: tuple[SensitivityEntry, ...]
    metric_name: str = "metric"

    @property
    def param_names(self) -> tuple[str, ...]:
        return tuple(e.param_name for e in self.entries)

    @property
    def sensitivities(self) -> npt.NDArray[np.float64]:
        return np.array([e.sensitivity for e in self.entries], dtype=np.float64)

    def to_dict(self) -> dict[str, float]:
        """Return dict mapping param_name → sensitivity."""
        return {e.param_name: e.sensitivity for e in self.entries}


def sensitivity(
    run_fn: Callable[[ParameterSet], ChainResult],
    params: ParameterSet,
    metric: Callable[[ChainResult], float] | None = None,
    metric_name: str = "snr",
    param_names: Sequence[str] | None = None,
    delta_fraction: float = 0.01,
) -> SensitivityResult:
    """Run one-at-a-time sensitivity analysis.

    Parameters
    ----------
    run_fn:
        Callable ``(ParameterSet) -> ChainResult``.
    params:
        Resolved baseline ParameterSet.
    metric:
        Callable ``(ChainResult) -> float``. Defaults to SNR.
    metric_name:
        Label stored in the result.
    param_names:
        Parameters to perturb. If None, uses all toleranced parameters.
        If no tolerances, uses all float parameters.
    delta_fraction:
        Fractional perturbation (0.01 = ±1%).
    """
    if metric is None:
        metric = _default_snr_metric

    # Ensure resolved (set_tolerance marks unresolved)
    if not params._resolved_flag:
        params.resolve()

    # Determine which parameters to perturb
    if param_names is not None:
        names = list(param_names)
    elif params._tolerances:
        names = sorted(params._tolerances.keys())
    else:
        # All float parameters with non-zero values
        names = [
            name
            for name, pdef in params._defs.items()
            if pdef.dtype is float
            and params._resolved.get(name) is not None
            and params._resolved[name].value != 0.0
        ]

    # Baseline evaluation
    baseline = run_fn(params)
    m0 = metric(baseline)

    entries: list[SensitivityEntry] = []
    for name in names:
        rv = params._resolved.get(name)
        if rv is None:
            continue
        nominal = float(rv.value)
        if nominal == 0.0:
            # Cannot compute fractional perturbation at zero
            logger.warning("sensitivity: skipping %s (nominal=0)", name)
            continue

        delta = abs(nominal * delta_fraction)
        v_plus = nominal + delta
        v_minus = nominal - delta

        ps_plus = _clone_with(params, name, v_plus)
        ps_minus = _clone_with(params, name, v_minus)

        r_plus = run_fn(ps_plus)
        r_minus = run_fn(ps_minus)

        m_plus = metric(r_plus)
        m_minus = metric(r_minus)

        # Central-difference normalized sensitivity
        # S = (dM/M) / (dp/p) = (m_plus - m_minus) / (2 * delta) * (nominal / m0)
        if m0 != 0.0:
            dm = m_plus - m_minus
            dp = 2.0 * delta
            sens = (dm / dp) * (nominal / m0)
        else:
            sens = 0.0

        entries.append(
            SensitivityEntry(
                param_name=name,
                nominal_value=nominal,
                metric_nominal=m0,
                metric_plus=m_plus,
                metric_minus=m_minus,
                sensitivity=sens,
                delta_fraction=delta_fraction,
            )
        )

    # Sort by absolute sensitivity, descending
    entries.sort(key=lambda e: abs(e.sensitivity), reverse=True)

    return SensitivityResult(
        entries=tuple(entries),
        metric_name=metric_name,
    )


def _default_snr_metric(result: ChainResult) -> float:
    """Extract SNR from a ChainResult."""
    snr = result.metrics.get("snr")
    if snr is None:
        raise ValueError("sensitivity: default metric is 'snr' but it was not computed.")
    return float(snr)
