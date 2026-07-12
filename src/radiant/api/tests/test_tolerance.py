"""Tests for Monte Carlo tolerance analysis."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.tolerance import MonteCarloResult, monte_carlo
from radiant.core.chain import ChainState
from radiant.core.parameters import (
    ParameterDef,
    ParameterSet,
    Provenance,
    Tolerance,
)
from radiant.io.results import ChainResult

# -- Fixtures ------------------------------------------------------------------


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
    """SNR = 100 × aperture, NEDT = 0.01 / aperture."""
    aperture = params.get("optics.aperture")
    wl = np.linspace(3.5, 5.0, 10)
    state = ChainState(wavelength_um=wl)
    state = state.with_metric("snr", 100.0 * aperture)
    state = state.with_metric("nedt", 0.01 / aperture)
    return ChainResult(state)


# -- Tests ---------------------------------------------------------------------


@pytest.mark.level1
class TestMonteCarlo:
    def test_basic_mc(self) -> None:
        params = _make_params(0.3)
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="gaussian", params={"std": 0.01}),
        )
        mc = monte_carlo(_mock_run, params, n_trials=50, seed=42)
        assert isinstance(mc, MonteCarloResult)
        assert mc.n_trials == 50
        assert mc.seed == 42
        assert "snr" in mc.metric_names
        assert mc.metric_array.shape == (50, 2)

    def test_mean_near_nominal(self) -> None:
        params = _make_params(0.3)
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="gaussian", params={"std": 0.005}),
        )
        mc = monte_carlo(_mock_run, params, n_trials=500, seed=123)
        # Mean SNR should be close to 30 (=100×0.3)
        assert mc.mean("snr") == pytest.approx(30.0, rel=0.05)

    def test_std_positive(self) -> None:
        params = _make_params(0.3)
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="gaussian", params={"std": 0.01}),
        )
        mc = monte_carlo(_mock_run, params, n_trials=100, seed=42)
        assert mc.std("snr") > 0.0

    def test_percentile(self) -> None:
        params = _make_params(0.3)
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="gaussian", params={"std": 0.01}),
        )
        mc = monte_carlo(_mock_run, params, n_trials=200, seed=42)
        p5 = mc.percentile("snr", 5)
        p95 = mc.percentile("snr", 95)
        assert p5 < mc.mean("snr") < p95

    def test_probability_of_exceeding(self) -> None:
        params = _make_params(0.3)
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="gaussian", params={"std": 0.01}),
        )
        mc = monte_carlo(_mock_run, params, n_trials=200, seed=42)
        # Prob(SNR >= 0) should be 1.0 (all positive apertures)
        assert mc.probability_of_exceeding("snr", 0.0) == pytest.approx(1.0, abs=1e-10)
        # Prob(SNR >= 1000) should be 0.0
        assert mc.probability_of_exceeding("snr", 1000.0) == pytest.approx(0.0, abs=1e-10)

    def test_correlation(self) -> None:
        params = _make_params(0.3)
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="gaussian", params={"std": 0.01}),
        )
        mc = monte_carlo(_mock_run, params, n_trials=500, seed=42)
        corr = mc.correlation("snr")
        # SNR = 100 × aperture → perfect positive correlation
        assert corr["optics.aperture"] > 0.99

    def test_sampled_params_recorded(self) -> None:
        params = _make_params(0.3)
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="gaussian", params={"std": 0.01}),
        )
        mc = monte_carlo(_mock_run, params, n_trials=50, seed=42)
        assert "optics.aperture" in mc.sampled_params
        assert mc.sampled_params["optics.aperture"].shape == (50,)

    def test_to_dict(self) -> None:
        params = _make_params(0.3)
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="gaussian", params={"std": 0.01}),
        )
        mc = monte_carlo(_mock_run, params, n_trials=10, seed=42)
        d = mc.to_dict()
        assert "snr" in d
        assert len(d["snr"]) == 10

    def test_no_tolerances_raises(self) -> None:
        params = _make_params(0.3)
        with pytest.raises(ValueError, match="no tolerances"):
            monte_carlo(_mock_run, params, n_trials=10)

    def test_reproducible_with_seed(self) -> None:
        params = _make_params(0.3)
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="gaussian", params={"std": 0.01}),
        )
        mc1 = monte_carlo(_mock_run, params, n_trials=20, seed=99)
        mc2 = monte_carlo(_mock_run, params, n_trials=20, seed=99)
        np.testing.assert_array_equal(mc1.metric_array, mc2.metric_array)

    def test_uniform_distribution(self) -> None:
        params = _make_params(0.3)
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="uniform", params={"low": 0.25, "high": 0.35}),
        )
        mc = monte_carlo(_mock_run, params, n_trials=200, seed=42)
        vals = mc.sampled_params["optics.aperture"]
        assert np.all(vals >= 0.25)
        assert np.all(vals <= 0.35)

    def test_keep_results(self) -> None:
        params = _make_params(0.3)
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="gaussian", params={"std": 0.01}),
        )
        mc = monte_carlo(_mock_run, params, n_trials=5, seed=42, keep_results=True)
        assert len(mc.results) == 5

    def test_unknown_metric_raises(self) -> None:
        params = _make_params(0.3)
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="gaussian", params={"std": 0.01}),
        )
        mc = monte_carlo(_mock_run, params, n_trials=5, seed=42)
        with pytest.raises(KeyError, match="not found"):
            mc.mean("nonexistent")


@pytest.mark.level1
class TestProgressAndCancel:
    """Gap 72: monte_carlo progress/cancel hooks."""

    def test_progress_called_per_trial(self) -> None:
        params = _make_params()
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="gaussian", params={"std": 0.01}),
        )
        calls: list[tuple[int, int]] = []
        monte_carlo(
            _mock_run,
            params,
            n_trials=5,
            seed=42,
            progress=lambda done, total: calls.append((done, total)),
        )
        assert calls == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]

    def test_cancel_aborts(self) -> None:
        from radiant.api._progress import OperationCancelledError

        params = _make_params()
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="gaussian", params={"std": 0.01}),
        )
        count = [0]

        def prog(done: int, total: int) -> None:
            count[0] = done

        with pytest.raises(OperationCancelledError):
            monte_carlo(
                _mock_run,
                params,
                n_trials=100,
                seed=42,
                progress=prog,
                cancel=lambda: count[0] >= 3,
            )
        assert count[0] == 3
