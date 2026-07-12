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


# -- Progress / cancel / parallel fallback (Gap 72, CU-072) --------------------


@pytest.mark.level1
class TestProgressAndCancel:
    def test_sweep_progress_called_per_point(self) -> None:
        calls: list[tuple[int, int]] = []
        sweep(
            _mock_run,
            _make_params(),
            "optics.aperture",
            [0.1, 0.2, 0.3],
            metric=_mock_metric,
            progress=lambda done, total: calls.append((done, total)),
        )
        assert calls == [(1, 3), (2, 3), (3, 3)]

    def test_sweep_cancel_aborts(self) -> None:
        from radiant.api._progress import OperationCancelledError
        from radiant.core.exceptions import RadiantError

        seen: list[int] = []

        def run(ps: ParameterSet) -> ChainResult:
            seen.append(1)
            return _mock_run(ps)

        with pytest.raises(OperationCancelledError) as excinfo:
            sweep(
                run,
                _make_params(),
                "optics.aperture",
                [0.1, 0.2, 0.3, 0.4],
                metric=_mock_metric,
                cancel=lambda: len(seen) >= 2,
            )
        assert isinstance(excinfo.value, RadiantError)
        assert excinfo.value.done == 2
        assert excinfo.value.total == 4
        assert len(seen) == 2  # no further evaluations after cancel

    def test_sweep_2d_progress_and_cancel(self) -> None:
        from radiant.api._progress import OperationCancelledError

        calls: list[tuple[int, int]] = []
        sweep_2d(
            _mock_run,
            _make_params(),
            "optics.aperture",
            [0.1, 0.2],
            "optics.focal_length",
            [1.0, 2.0],
            metric=_mock_metric,
            progress=lambda done, total: calls.append((done, total)),
        )
        assert calls == [(1, 4), (2, 4), (3, 4), (4, 4)]

        with pytest.raises(OperationCancelledError):
            sweep_2d(
                _mock_run,
                _make_params(),
                "optics.aperture",
                [0.1, 0.2],
                "optics.focal_length",
                [1.0, 2.0],
                metric=_mock_metric,
                cancel=lambda: True,
            )

    def test_parallel_unpicklable_falls_back_sequential(self) -> None:
        """CU-072: a closure run_fn cannot pickle; the sweep must fall
        back to sequential instead of crashing with PicklingError."""
        offset = 1.0  # captured by the closure -> unpicklable local fn

        def run(ps: ParameterSet) -> ChainResult:
            r = _mock_run(ps)
            _ = offset
            return r

        result = sweep(
            run,
            _make_params(),
            "optics.aperture",
            [0.1, 0.2, 0.3],
            metric=_mock_metric,
            n_workers=2,
        )
        np.testing.assert_allclose(result.metric_values, [10.0, 20.0, 30.0], rtol=1e-12)

    def test_parallel_fallback_reports_progress(self) -> None:
        calls: list[tuple[int, int]] = []

        def run(ps: ParameterSet) -> ChainResult:
            return _mock_run(ps)

        sweep(
            run,
            _make_params(),
            "optics.aperture",
            [0.1, 0.2],
            metric=_mock_metric,
            n_workers=2,
            progress=lambda done, total: calls.append((done, total)),
        )
        assert calls[-1] == (2, 2)

    def test_parallel_unpicklable_result_falls_back(self) -> None:
        """CU-072 exact scenario: the callable pickles fine but the
        returned ChainResult (MappingProxyType fields) does not — the
        failure surfaces at fut.result() and must trigger the
        sequential fallback, not crash."""
        result = sweep(
            _mock_run,  # module-level: picklable; its return is not
            _make_params(),
            "optics.aperture",
            [0.1, 0.2, 0.3],
            metric=_mock_metric,
            n_workers=2,
        )
        np.testing.assert_allclose(result.metric_values, [10.0, 20.0, 30.0], rtol=1e-12)
