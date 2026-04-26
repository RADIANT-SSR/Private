"""Performance tests for sweep operations."""

from __future__ import annotations

import time

import numpy as np
import pytest

from radiant.api.sweep import sweep
from radiant.api.tolerance import monte_carlo
from radiant.core.chain import ChainState
from radiant.core.parameters import (
    ParameterDef,
    ParameterSet,
    Provenance,
    Tolerance,
)
from radiant.io.results import ChainResult


def _make_params(aperture: float = 0.3) -> ParameterSet:
    schema = [
        ParameterDef(
            name="optics.aperture",
            description="Aperture diameter",
            dtype=float,
            canonical_unit="m",
            input_unit="m",
            default=None,
        ),
    ]
    ps = ParameterSet(schema)
    ps.set("optics.aperture", aperture, Provenance.USER_SET, "test")
    ps.resolve()
    return ps


def _mock_run(params: ParameterSet) -> ChainResult:
    aperture = params.get("optics.aperture")
    wl = np.linspace(3.5, 5.0, 10)
    state = ChainState(wavelength_um=wl)
    state = state.with_metric("snr", 100.0 * aperture)
    return ChainResult(state)


def _snr_metric(result: ChainResult) -> float:
    return float(result.metrics["snr"])


@pytest.mark.level1
class TestPerformance:
    def test_1000_point_sweep_under_60s(self) -> None:
        """1000-point sweep must complete in < 60 seconds."""
        params = _make_params()
        values = np.linspace(0.05, 1.0, 1000)
        t0 = time.perf_counter()
        result = sweep(
            _mock_run,
            params,
            "optics.aperture",
            values,
            metric=_snr_metric,
            keep_results=False,
        )
        elapsed = time.perf_counter() - t0
        assert result.metric_values.shape == (1000,)
        assert elapsed < 60.0, f"1000-point sweep took {elapsed:.1f}s (> 60s limit)"

    def test_1000_trial_mc_under_60s(self) -> None:
        """1000-trial Monte Carlo must complete in < 60 seconds."""
        params = _make_params()
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="gaussian", params={"std": 0.01}),
        )
        t0 = time.perf_counter()
        mc = monte_carlo(_mock_run, params, n_trials=1000, seed=42)
        elapsed = time.perf_counter() - t0
        assert mc.n_trials == 1000
        assert elapsed < 60.0, f"1000-trial MC took {elapsed:.1f}s (> 60s limit)"
