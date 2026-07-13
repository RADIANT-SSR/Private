"""Tests for the plotting module.

Uses the matplotlib Agg backend (non-interactive) so tests run headless.
"""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pytest

from radiant.api.plot import (
    Plottable,
    plot_atmosphere_spectral,
    plot_noise_budget,
    plot_spectral,
    plot_spectral_multi,
    plot_sweep,
    plot_sweep_2d,
)
from radiant.api.sweep import Sweep2DResult, SweepResult

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

from matplotlib.figure import Figure  # noqa: E402  # backend must be set first

# -- Fixtures --------------------------------------------------------------


def _make_sweep_result() -> SweepResult:
    return SweepResult(
        param_name="optics.aperture_diameter_m",
        values=np.array([0.1, 0.2, 0.3, 0.4, 0.5]),
        metric_values=np.array([10.0, 20.0, 30.0, 40.0, 50.0]),
        metric_name="snr",
    )


def _make_sweep_2d_result() -> Sweep2DResult:
    return Sweep2DResult(
        param1_name="optics.aperture_diameter_m",
        param2_name="spectral_integration.integration_time_s",
        values1=np.array([0.2, 0.3, 0.4]),
        values2=np.array([0.003, 0.005]),
        grid=np.array([[15.0, 25.0], [20.0, 35.0], [30.0, 45.0]]),
        metric_name="snr",
    )


class _FakeNoiseTerm:
    """Minimal noise term for testing plot_noise_budget."""

    def __init__(self, name: str, value_e: float) -> None:
        self.name = name
        self.value_e = value_e


# -- Plottable protocol ---------------------------------------------------


@pytest.mark.level1
class TestPlottableProtocol:
    def test_plottable_is_runtime_checkable(self) -> None:
        class MyPlottable:
            def plot(self, **kwargs: Any) -> Figure:
                fig, _ = matplotlib.pyplot.subplots()
                return cast(Figure, fig)

        obj = MyPlottable()
        assert isinstance(obj, Plottable)

    def test_non_plottable(self) -> None:
        class NotPlottable:
            pass

        obj = NotPlottable()
        assert not isinstance(obj, Plottable)


# -- Plot functions --------------------------------------------------------


@pytest.mark.level1
class TestPlotSweep:
    def test_returns_figure(self) -> None:
        result = _make_sweep_result()
        fig = plot_sweep(result)
        assert isinstance(fig, Figure)
        matplotlib.pyplot.close(fig)

    def test_axes_labels(self) -> None:
        result = _make_sweep_result()
        fig = plot_sweep(result)
        ax = fig.axes[0]
        assert "aperture" in ax.get_xlabel()
        assert "snr" in ax.get_ylabel()
        matplotlib.pyplot.close(fig)


@pytest.mark.level1
class TestPlotSweep2D:
    def test_returns_figure(self) -> None:
        result = _make_sweep_2d_result()
        fig = plot_sweep_2d(result)
        assert isinstance(fig, Figure)
        matplotlib.pyplot.close(fig)


@pytest.mark.level1
class TestPlotNoiseBudget:
    def test_returns_figure(self) -> None:
        terms = [
            _FakeNoiseTerm("photon_shot", 111.6),
            _FakeNoiseTerm("dark_current", 89.2),
            _FakeNoiseTerm("read_noise", 25.0),
        ]
        fig = plot_noise_budget(terms)
        assert isinstance(fig, Figure)
        matplotlib.pyplot.close(fig)


@pytest.mark.level1
class TestPlotSpectral:
    def test_returns_figure(self) -> None:
        wl = np.linspace(3.5, 5.0, 100)
        rad = np.exp(-((wl - 4.2) ** 2) / 0.2)
        fig = plot_spectral(wl, rad, title="Test Spectral")
        assert isinstance(fig, Figure)
        ax = fig.axes[0]
        assert "Test Spectral" in ax.get_title()
        matplotlib.pyplot.close(fig)


@pytest.mark.level1
class TestPlotSpectralMulti:
    def test_returns_figure_with_unit_labels(self) -> None:
        wl = np.linspace(3.5, 5.0, 50)
        series = {"target": np.exp(-wl), "background": 0.5 * np.exp(-wl)}
        fig = plot_spectral_multi(wl, series)
        assert isinstance(fig, Figure)
        ax = fig.axes[0]
        assert "µm" in ax.get_xlabel()
        assert "W/m²/sr/µm" in ax.get_ylabel()
        assert len(ax.lines) == 2
        matplotlib.pyplot.close(fig)

    def test_single_series_no_legend_error(self) -> None:
        wl = np.linspace(3.5, 5.0, 50)
        fig = plot_spectral_multi(wl, {"target": np.exp(-wl)})
        assert len(fig.axes[0].lines) == 1
        matplotlib.pyplot.close(fig)


@pytest.mark.level1
class TestPlotAtmosphereSpectral:
    def test_returns_twin_unit_axes(self) -> None:
        wl = np.linspace(3.5, 5.0, 50)
        tau = 0.8 * np.ones_like(wl)
        l_path = 0.3 * np.ones_like(wl)
        fig = plot_atmosphere_spectral(wl, tau, l_path)
        assert isinstance(fig, Figure)
        ylabels = [a.get_ylabel() for a in fig.axes]
        assert any("dimensionless" in y for y in ylabels)
        assert any("W/m²/sr/µm" in y for y in ylabels)
        assert "µm" in fig.axes[0].get_xlabel()
        matplotlib.pyplot.close(fig)
