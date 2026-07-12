"""Tests for one-at-a-time sensitivity analysis."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.sensitivity import SensitivityResult, sensitivity
from radiant.core.chain import ChainState
from radiant.core.parameters import (
    ParameterDef,
    ParameterSet,
    Provenance,
    Tolerance,
)
from radiant.io.results import ChainResult

# -- Fixtures ------------------------------------------------------------------


def _make_params() -> ParameterSet:
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
            default=None,
        ),
    ]
    ps = ParameterSet(schema)
    ps.set("optics.aperture", 0.3, Provenance.USER_SET, "test")
    ps.set("optics.focal_length", 1.2, Provenance.USER_SET, "test")
    ps.resolve()
    return ps


def _mock_run(params: ParameterSet) -> ChainResult:
    """SNR = 100 × aperture² / focal_length."""
    a = params.get("optics.aperture")
    f = params.get("optics.focal_length")
    snr = 100.0 * a * a / f
    wl = np.linspace(3.5, 5.0, 10)
    state = ChainState(wavelength_um=wl)
    state = state.with_metric("snr", snr)
    return ChainResult(state)


def _snr_metric(result: ChainResult) -> float:
    return float(result.metrics["snr"])


# -- Tests ---------------------------------------------------------------------


@pytest.mark.level1
class TestSensitivity:
    def test_basic_sensitivity(self) -> None:
        params = _make_params()
        result = sensitivity(
            _mock_run,
            params,
            metric=_snr_metric,
            param_names=["optics.aperture", "optics.focal_length"],
            delta_fraction=0.01,
        )
        assert isinstance(result, SensitivityResult)
        assert len(result.entries) == 2

    def test_aperture_sensitivity_positive(self) -> None:
        """SNR ∝ aperture² → elasticity ≈ +2.0."""
        params = _make_params()
        result = sensitivity(
            _mock_run,
            params,
            metric=_snr_metric,
            param_names=["optics.aperture"],
            delta_fraction=0.01,
        )
        entry = result.entries[0]
        assert entry.param_name == "optics.aperture"
        # d(SNR)/SNR / d(a)/a ≈ 2 (power law exponent)
        assert entry.sensitivity == pytest.approx(2.0, rel=0.01)

    def test_focal_length_sensitivity_negative(self) -> None:
        """SNR ∝ 1/focal_length → elasticity ≈ -1.0."""
        params = _make_params()
        result = sensitivity(
            _mock_run,
            params,
            metric=_snr_metric,
            param_names=["optics.focal_length"],
            delta_fraction=0.01,
        )
        entry = result.entries[0]
        assert entry.param_name == "optics.focal_length"
        assert entry.sensitivity == pytest.approx(-1.0, rel=0.01)

    def test_sorted_by_abs_sensitivity(self) -> None:
        """Entries sorted by |sensitivity| descending."""
        params = _make_params()
        result = sensitivity(
            _mock_run,
            params,
            metric=_snr_metric,
            param_names=["optics.aperture", "optics.focal_length"],
        )
        abs_sens = [abs(e.sensitivity) for e in result.entries]
        assert abs_sens == sorted(abs_sens, reverse=True)

    def test_to_dict(self) -> None:
        params = _make_params()
        result = sensitivity(
            _mock_run,
            params,
            metric=_snr_metric,
            param_names=["optics.aperture"],
        )
        d = result.to_dict()
        assert "optics.aperture" in d
        assert d["optics.aperture"] == pytest.approx(2.0, rel=0.01)

    def test_uses_toleranced_params_by_default(self) -> None:
        params = _make_params()
        params.set_tolerance(
            "optics.aperture",
            Tolerance(distribution="gaussian", params={"std": 0.01}),
        )
        result = sensitivity(_mock_run, params, metric=_snr_metric)
        assert len(result.entries) == 1
        assert result.entries[0].param_name == "optics.aperture"

    def test_different_delta_fractions(self) -> None:
        """Different delta fractions both recover correct sensitivity."""
        params = _make_params()
        r1 = sensitivity(
            _mock_run,
            params,
            metric=_snr_metric,
            param_names=["optics.aperture"],
            delta_fraction=0.1,
        )
        r2 = sensitivity(
            _mock_run,
            params,
            metric=_snr_metric,
            param_names=["optics.aperture"],
            delta_fraction=0.001,
        )
        # For SNR ∝ a², central difference is exact for any delta
        assert r1.entries[0].sensitivity == pytest.approx(2.0, rel=1e-6)
        assert r2.entries[0].sensitivity == pytest.approx(2.0, rel=1e-6)

    def test_metric_plus_minus_stored(self) -> None:
        params = _make_params()
        result = sensitivity(
            _mock_run,
            params,
            metric=_snr_metric,
            param_names=["optics.aperture"],
            delta_fraction=0.01,
        )
        entry = result.entries[0]
        assert entry.metric_plus > entry.metric_nominal
        assert entry.metric_minus < entry.metric_nominal
        assert entry.delta_fraction == 0.01

    def test_sensitivities_property(self) -> None:
        params = _make_params()
        result = sensitivity(
            _mock_run,
            params,
            metric=_snr_metric,
            param_names=["optics.aperture", "optics.focal_length"],
        )
        sens_arr = result.sensitivities
        assert isinstance(sens_arr, np.ndarray)
        assert len(sens_arr) == 2


@pytest.mark.level1
class TestProgressAndCancel:
    """Gap 72: sensitivity progress/cancel hooks."""

    def test_progress_called_per_parameter(self) -> None:
        calls: list[tuple[int, int]] = []
        sensitivity(
            _mock_run,
            _make_params(),
            param_names=["optics.aperture", "optics.focal_length"],
            progress=lambda done, total: calls.append((done, total)),
        )
        assert calls == [(1, 2), (2, 2)]

    def test_cancel_aborts(self) -> None:
        from radiant.api._progress import OperationCancelledError

        with pytest.raises(OperationCancelledError):
            sensitivity(
                _mock_run,
                _make_params(),
                param_names=["optics.aperture"],
                cancel=lambda: True,
            )
