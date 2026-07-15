"""Tests for the plotting module.

Uses the matplotlib Agg backend (non-interactive) so tests run headless.
"""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pytest

from radiant.api.errors import ApiValidationError
from radiant.api.plot import (
    Plottable,
    plot_atmosphere_spectral,
    plot_coating_spectra,
    plot_mtf_terms,
    plot_noise_budget,
    plot_noise_pie,
    plot_optical_throughput,
    plot_psf,
    plot_spectral,
    plot_spectral_multi,
    plot_sweep,
    plot_sweep_2d,
)
from radiant.api.sweep import Sweep2DResult, SweepResult
from radiant.optics.psf.effective import EffectivePSF

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

from matplotlib.figure import Figure  # noqa: E402  # backend must be set first
from matplotlib.layout_engine import ConstrainedLayoutEngine  # noqa: E402

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
class TestPlotNoisePie:
    """PS-3 Part A: the variance-weighted noise pie (result.plot.noise_pie builder)."""

    def test_returns_figure(self) -> None:
        terms = [_FakeNoiseTerm("photon_shot", 111.6), _FakeNoiseTerm("read_noise", 25.0)]
        fig = plot_noise_pie(terms)
        assert isinstance(fig, Figure)
        matplotlib.pyplot.close(fig)

    def test_slices_proportional_to_variance_not_sigma(self) -> None:
        """The wedge spans track σ_i² (noise power), NOT σ_i (RMS values do not add)."""
        terms = [_FakeNoiseTerm("a", 30.0), _FakeNoiseTerm("b", 40.0)]  # var 900 vs 1600
        fig = plot_noise_pie(terms)
        from matplotlib.patches import Wedge

        wedges = [cast(Wedge, p) for p in fig.axes[0].patches]
        spans = [w.theta2 - w.theta1 for w in wedges]  # sorted desc → [b(1600), a(900)]
        total = sum(spans)
        assert spans[0] / total == pytest.approx(1600.0 / 2500.0, abs=1e-6)
        assert spans[1] / total == pytest.approx(900.0 / 2500.0, abs=1e-6)
        matplotlib.pyplot.close(fig)

    def test_labels_carry_e_rms_units(self) -> None:
        """Every wedge label states its σ_i in e- RMS (owner hard rule)."""
        fig = plot_noise_pie([_FakeNoiseTerm("photon_shot", 111.6)])
        labels = [t.get_text() for t in fig.axes[0].texts]
        assert any("e- RMS" in lbl for lbl in labels)
        assert any("photon_shot" in lbl for lbl in labels)
        matplotlib.pyplot.close(fig)

    def test_zero_terms_omitted(self) -> None:
        """A σ = 0 term carries no power and is dropped (no wedge, no label)."""
        terms = [_FakeNoiseTerm("live", 10.0), _FakeNoiseTerm("dead", 0.0)]
        fig = plot_noise_pie(terms)
        assert len(fig.axes[0].patches) == 1  # only the live term
        labels = " ".join(t.get_text() for t in fig.axes[0].texts)
        assert "dead" not in labels
        matplotlib.pyplot.close(fig)

    def test_all_zero_raises_actionable(self) -> None:
        """All-zero σ → nothing to apportion → an actionable ApiValidationError."""
        with pytest.raises(ApiValidationError, match="non-zero noise terms"):
            plot_noise_pie([_FakeNoiseTerm("a", 0.0), _FakeNoiseTerm("b", 0.0)])


@pytest.mark.level1
class TestPlotPsfPixelGrid:
    """PS-3 Part A: plot_psf(pixel_grid=True) overlays the detector pixel grid + crops."""

    @staticmethod
    def _psf() -> EffectivePSF:
        n = 128
        yy, xx = np.mgrid[0:n, 0:n]
        c = (n - 1) / 2.0
        data = np.exp(-((xx - c) ** 2 + (yy - c) ** 2) / (2.0 * 3.0**2))
        return EffectivePSF(
            data=data / data.sum(),
            sample_spacing_m=2.0e-6,
            pixel_pitch_m=1.0e-5,  # 5 samples per detector pixel
            wavelength_um=4.0,
            convolution_history=("diffraction",),
        )

    def test_default_has_no_grid_and_shipped_title(self) -> None:
        """pixel_grid defaults False → the shipped image, uncropped, titled 'Effective PSF'."""
        fig = plot_psf(self._psf())
        ax = fig.axes[0]
        assert ax.get_title() == "Effective PSF"
        assert not ax.get_lines()  # no gridlines
        matplotlib.pyplot.close(fig)

    def test_grid_overlays_lines_and_crops_and_titles_pitch(self) -> None:
        """pixel_grid=True → gridlines drawn, view cropped to the core, pitch (µm) in title."""
        psf = self._psf()
        fig = plot_psf(psf, pixel_grid=True, pixel_grid_span=8)
        ax = fig.axes[0]
        assert ax.get_lines()  # pixel-boundary gridlines present
        assert "µm pitch" in ax.get_title()
        # Cropped to a window narrower than the full 128-sample array.
        lo, hi = ax.get_xlim()
        assert (hi - lo) < psf.data.shape[0]
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

    def test_ylabels_are_shortened_symbol_first(self) -> None:
        # Owner feedback 2026-07-13: the long spelled-out twin-axis y-labels clipped at the
        # figure edges in the narrow embedded pane. The labels are shortened to symbol + unit
        # (unit retained, R-UNITS), dropping the spelled-out "Transmittance"/"Path radiance"
        # prefixes that overflowed.
        wl = np.linspace(3.5, 5.0, 50)
        fig = plot_atmosphere_spectral(wl, 0.8 * np.ones_like(wl), 0.3 * np.ones_like(wl))
        ylabels = {a.get_ylabel() for a in fig.axes}
        assert "τ_atm (dimensionless)" in ylabels
        assert "L_path (W/m²/sr/µm)" in ylabels
        # The over-long spelled-out prefixes are gone.
        assert all("Transmittance" not in y for y in ylabels)
        assert all("Path radiance" not in y for y in ylabels)
        matplotlib.pyplot.close(fig)


@pytest.mark.level1
class TestPlotOpticalThroughput:
    def test_returns_figure_with_units(self) -> None:
        wl = np.linspace(3.5, 5.0, 50)
        tau = 0.7 * np.ones_like(wl)
        fig = plot_optical_throughput(wl, tau)
        assert isinstance(fig, Figure)
        ax = fig.axes[0]
        assert "µm" in ax.get_xlabel()
        assert ax.get_ylabel() == "τ_opt (dimensionless)"
        assert len(ax.lines) == 1
        np.testing.assert_array_equal(ax.lines[0].get_ydata(), tau)
        assert ax.get_ylim() == (0.0, 1.05)
        matplotlib.pyplot.close(fig)


@pytest.mark.level1
class TestPlotCoatingSpectra:
    def test_multi_element_units_and_own_grids(self) -> None:
        wl_a = np.linspace(3.5, 5.0, 30)
        wl_b = np.linspace(3.6, 5.1, 25)  # a distinct per-element grid
        series = {
            "m1 R": (wl_a, 0.95 * np.ones_like(wl_a)),
            "m1 ε": (wl_a, 0.05 * np.ones_like(wl_a)),
            "win T": (wl_b, 0.9 * np.ones_like(wl_b)),
        }
        fig = plot_coating_spectra(series)
        assert isinstance(fig, Figure)
        ax = fig.axes[0]
        assert "µm" in ax.get_xlabel()
        assert "dimensionless" in ax.get_ylabel()
        assert len(ax.lines) == 3
        # Each curve keeps its own wavelength grid (no shared-grid assumption).
        np.testing.assert_array_equal(ax.lines[2].get_xdata(), wl_b)
        matplotlib.pyplot.close(fig)

    def test_empty_series_no_legend_error(self) -> None:
        fig = plot_coating_spectra({})
        assert len(fig.axes[0].lines) == 0
        matplotlib.pyplot.close(fig)


@pytest.mark.level1
class TestConstrainedLayout:
    """Every plot builder must ship a constrained-layout figure so titles / axis labels /
    legends always have reserved margin and re-fit when an embedded canvas is resized
    (the GUI-clipping fix). tight_layout is a one-shot computation that clips on resize;
    constrained_layout re-runs on every draw.
    """

    def _make_figs(self) -> list[Figure]:
        wl = np.linspace(3.5, 5.0, 50)
        rad = np.exp(-wl)
        terms = [_FakeNoiseTerm("photon_shot", 111.6), _FakeNoiseTerm("read_noise", 25.0)]
        mtf_terms = {
            "mtf_optics_x": np.linspace(1.0, 0.0, 20),
            "mtf_optics_y": np.linspace(1.0, 0.1, 20),
        }
        return [
            plot_sweep(_make_sweep_result()),
            plot_sweep_2d(_make_sweep_2d_result()),
            plot_noise_budget(terms),
            plot_mtf_terms(mtf_terms, np.arange(20, dtype=float)),
            plot_spectral(wl, rad, title="t"),
            plot_spectral_multi(wl, {"a": rad, "b": 0.5 * rad}),
            plot_atmosphere_spectral(wl, 0.8 * np.ones_like(wl), 0.3 * np.ones_like(wl)),
            plot_optical_throughput(wl, 0.7 * np.ones_like(wl)),
            plot_coating_spectra({"m1 R": (wl, 0.9 * np.ones_like(wl))}),
        ]

    def test_all_builders_use_constrained_layout(self) -> None:
        figs = self._make_figs()
        try:
            for fig in figs:
                assert isinstance(fig.get_layout_engine(), ConstrainedLayoutEngine), (
                    f"figure with title {fig.axes[0].get_title()!r} is not constrained-layout"
                )
        finally:
            for fig in figs:
                matplotlib.pyplot.close(fig)

    def test_hardcoded_yaxis_labels_are_short_enough_not_to_clip(self) -> None:
        # Owner feedback 2026-07-13: very long rotated y-axis labels overflowed the narrow
        # embedded pane even under constrained_layout. Every builder that hardcodes a
        # descriptive y-axis label keeps it to a symbol + unit form (unit always retained);
        # this guards against a future spelled-out label creeping back in. 32 chars
        # comfortably fits the ~700 px pane. (Sweep plots are excluded — their labels are
        # data-driven parameter dot-paths, not descriptive labels this module controls.)
        wl = np.linspace(3.5, 5.0, 50)
        rad = np.exp(-wl)
        terms = [_FakeNoiseTerm("photon_shot", 111.6), _FakeNoiseTerm("read_noise", 25.0)]
        mtf_terms = {"mtf_optics_x": np.linspace(1.0, 0.0, 20)}
        figs = [
            plot_noise_budget(terms),
            plot_mtf_terms(mtf_terms, np.arange(20, dtype=float)),
            plot_spectral(wl, rad, title="t"),
            plot_spectral_multi(wl, {"a": rad, "b": 0.5 * rad}),
            plot_atmosphere_spectral(wl, 0.8 * np.ones_like(wl), 0.3 * np.ones_like(wl)),
            plot_optical_throughput(wl, 0.7 * np.ones_like(wl)),
            plot_coating_spectra({"m1 R": (wl, 0.9 * np.ones_like(wl))}),
        ]
        try:
            for fig in figs:
                for ax in fig.axes:
                    ylabel = ax.get_ylabel()
                    assert len(ylabel) <= 32, (
                        f"y-axis label {ylabel!r} is too long and may clip in the GUI pane"
                    )
        finally:
            for fig in figs:
                matplotlib.pyplot.close(fig)

    def test_mtf_legend_below_axes_never_covers_curves(self) -> None:
        # CU-117: the legend sits BELOW the axes rectangle, so it never blankets the curves
        # in the GUI's narrow embedded pane (and, being below, never reaches the title band
        # constrained_layout reserves above the axes either).
        mtf_terms = {"mtf_optics_x": np.linspace(1.0, 0.0, 20)}
        fig = plot_mtf_terms(mtf_terms, np.arange(20, dtype=float))
        ax = fig.axes[0]
        legend = ax.get_legend()
        assert legend is not None
        fig.canvas.draw()  # realise the renderer so bbox extents are populated
        axes_bbox = ax.get_window_extent()
        legend_bbox = legend.get_window_extent()
        # Legend top must sit at/below the axes bottom — the plot area is unobstructed.
        assert legend_bbox.ymax <= axes_bbox.ymin + 1.0
        matplotlib.pyplot.close(fig)

    def test_coincident_xy_terms_merge_to_one_legend_entry(self) -> None:
        # CU-117: a contributor whose x/y roll-off coincides shows as ONE legend entry, so a
        # full 16-line overlay (8 contributors × x/y) collapses to ~8 labels. No curve is
        # dropped — identical x/y are represented by a single line.
        roll = np.linspace(1.0, 0.2, 20)
        mtf_terms = {
            f"mtf_{name}_{axis}": roll.copy()
            for name in ("optics", "jitter", "smear", "ipc")
            for axis in ("x", "y")
        }
        fig = plot_mtf_terms(mtf_terms, np.arange(20, dtype=float))
        legend = fig.axes[0].get_legend()
        assert legend is not None
        labels = [t.get_text() for t in legend.get_texts()]
        assert labels == ["mtf_ipc", "mtf_jitter", "mtf_optics", "mtf_smear"]  # 8 keys → 4
        matplotlib.pyplot.close(fig)

    def test_anisotropic_xy_terms_keep_both_labels(self) -> None:
        # Honesty: when x and y visibly differ, both curves and both labels are kept — a real
        # anisotropy is never hidden behind a single merged entry.
        mtf_terms = {
            "mtf_optics_x": np.linspace(1.0, 0.0, 20),
            "mtf_optics_y": np.linspace(1.0, 0.4, 20),
        }
        fig = plot_mtf_terms(mtf_terms, np.arange(20, dtype=float))
        legend = fig.axes[0].get_legend()
        assert legend is not None
        labels = {t.get_text() for t in legend.get_texts()}
        assert labels == {"mtf_optics (x)", "mtf_optics (y)"}
        matplotlib.pyplot.close(fig)
