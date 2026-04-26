"""Tests for 1-D and 2-D parameter sweeps."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.sweep import Sweep2DResult, SweepResult, sweep, sweep_2d
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterDef, ParameterSet, Provenance
from radiant.io.results import ChainResult

# -- Fixtures ------------------------------------------------------------------


def _make_params(aperture: float = 0.3) -> ParameterSet:
    """Build a minimal ParameterSet with one sweepable parameter."""
    schema = [
        ParameterDef(
            name="optics.aperture",
            description="Aperture diameter",
            dtype=float,
            canonical_unit="m",
            input_unit="m",
            default=None,
        ),
        ParameterDef(
            name="optics.focal_length",
            description="Focal length",
            dtype=float,
            canonical_unit="m",
            input_unit="m",
            default=1.0,
        ),
    ]
    ps = ParameterSet(schema)
    ps.set("optics.aperture", aperture, Provenance.USER_SET, "test")
    ps.resolve()
    return ps


def _mock_run(params: ParameterSet) -> ChainResult:
    """Mock chain: SNR = 100 × aperture."""
    aperture = params.get("optics.aperture")
    wl = np.linspace(3.5, 5.0, 10)
    state = ChainState(wavelength_um=wl)
    state = state.with_metric("snr", 100.0 * aperture)
    state = state.with_metric("nedt", 0.01 / aperture)
    return ChainResult(state)


def _mock_metric(result: ChainResult) -> float:
    return float(result.metrics["snr"])


# -- 1-D Sweep ----------------------------------------------------------------


@pytest.mark.level1
class TestSweep:
    def test_basic_sweep(self) -> None:
        params = _make_params(aperture=0.3)
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = sweep(
            _mock_run,
            params,
            "optics.aperture",
            values,
            metric=_mock_metric,
            metric_name="snr",
        )
        assert isinstance(result, SweepResult)
        assert result.param_name == "optics.aperture"
        assert len(result.values) == 5
        assert len(result.metric_values) == 5
        np.testing.assert_allclose(
            result.metric_values,
            [10.0, 20.0, 30.0, 40.0, 50.0],
            rtol=1e-10,
        )

    def test_sweep_monotonic(self) -> None:
        params = _make_params()
        values = np.linspace(0.1, 1.0, 20)
        result = sweep(
            _mock_run,
            params,
            "optics.aperture",
            values,
            metric=_mock_metric,
        )
        # SNR = 100 × aperture → monotonically increasing
        diffs = np.diff(result.metric_values)
        assert np.all(diffs > 0)

    def test_keep_results_false(self) -> None:
        params = _make_params()
        result = sweep(
            _mock_run,
            params,
            "optics.aperture",
            [0.1, 0.2],
            metric=_mock_metric,
            keep_results=False,
        )
        assert len(result.results) == 0

    def test_keep_results_true(self) -> None:
        params = _make_params()
        result = sweep(
            _mock_run,
            params,
            "optics.aperture",
            [0.1, 0.2],
            metric=_mock_metric,
            keep_results=True,
        )
        assert len(result.results) == 2

    def test_getitem_metric(self) -> None:
        params = _make_params()
        result = sweep(
            _mock_run,
            params,
            "optics.aperture",
            [0.1, 0.2, 0.3],
            metric=_mock_metric,
            keep_results=True,
        )
        nedt_vals = result["nedt"]
        np.testing.assert_allclose(
            nedt_vals,
            [0.1, 0.05, 0.01 / 0.3],
            rtol=1e-10,
        )

    def test_getitem_no_results_raises(self) -> None:
        params = _make_params()
        result = sweep(
            _mock_run,
            params,
            "optics.aperture",
            [0.1],
            metric=_mock_metric,
            keep_results=False,
        )
        with pytest.raises(KeyError, match="not kept"):
            result["snr"]

    def test_at_metric_threshold(self) -> None:
        params = _make_params()
        result = sweep(
            _mock_run,
            params,
            "optics.aperture",
            [0.1, 0.2, 0.3, 0.4, 0.5],
            metric=_mock_metric,
        )
        hit = result.at_metric_threshold(25.0)
        assert hit is not None
        assert hit[0] == pytest.approx(0.3, rel=1e-10)
        assert hit[1] == pytest.approx(30.0, rel=1e-10)

    def test_at_metric_threshold_not_reached(self) -> None:
        params = _make_params()
        result = sweep(
            _mock_run,
            params,
            "optics.aperture",
            [0.1, 0.2],
            metric=_mock_metric,
        )
        assert result.at_metric_threshold(999.0) is None


# -- 2-D Sweep ----------------------------------------------------------------


@pytest.mark.level1
class TestSweep2D:
    def test_basic_2d(self) -> None:
        params = _make_params()
        v1 = [0.1, 0.2, 0.3]
        v2 = [0.4, 0.5]
        result = sweep_2d(
            _mock_run,
            params,
            "optics.aperture",
            v1,
            "optics.focal_length",
            v2,
            metric=_mock_metric,
        )
        assert isinstance(result, Sweep2DResult)
        assert result.grid.shape == (3, 2)
        # focal_length doesn't affect our mock metric, only aperture does
        np.testing.assert_allclose(result.grid[:, 0], [10.0, 20.0, 30.0], rtol=1e-10)
        np.testing.assert_allclose(result.grid[:, 1], [10.0, 20.0, 30.0], rtol=1e-10)

    def test_2d_shape(self) -> None:
        params = _make_params()
        result = sweep_2d(
            _mock_run,
            params,
            "optics.aperture",
            np.linspace(0.1, 0.5, 5),
            "optics.focal_length",
            np.linspace(0.5, 2.0, 4),
            metric=_mock_metric,
        )
        assert result.grid.shape == (5, 4)
