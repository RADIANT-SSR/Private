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
    plot_pupil_phase,
    plot_spectral,
    plot_spectral_multi,
    plot_sweep,
    plot_sweep_2d,
    plot_theme,
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
class TestPlotNoisePieLabelCollision:
    """Sub-percent wedges must not stack their labels on each other (walkthrough item 18).

    The real shape of a shot-noise-limited budget: one term at ~100 % of the
    variance and a handful rounding to 0.0 %. Every one of those tiny wedges
    used to draw a two-line label at nearly the same angle, producing the
    overstruck block of text in the walkthrough screenshot.
    """

    @staticmethod
    def _dominated_terms() -> list[_FakeNoiseTerm]:
        """σ values reproducing the reported case: shot noise ≫ everything else."""
        return [
            _FakeNoiseTerm("signal_shot", 916.0),
            _FakeNoiseTerm("dark_shot", 0.202),
            _FakeNoiseTerm("read_noise", 0.202),
            _FakeNoiseTerm("quantization", 0.202),
            _FakeNoiseTerm("pattern_noise", 0.202),
        ]

    def test_tiny_wedges_carry_no_on_wedge_label(self) -> None:
        fig = plot_noise_pie(self._dominated_terms())
        drawn = [t.get_text() for t in fig.axes[0].texts if t.get_text()]
        # Only the dominant term is labelled on the wedge; the 0.0 % terms are not.
        assert len(drawn) == 1
        assert "signal_shot" in drawn[0]
        matplotlib.pyplot.close(fig)

    def test_every_term_still_appears_in_the_legend(self) -> None:
        """Suppressing a wedge label must not lose the term — the legend keeps it."""
        fig = plot_noise_pie(self._dominated_terms())
        legend = fig.axes[0].get_legend()
        assert legend is not None
        entries = " ".join(t.get_text() for t in legend.get_texts())
        for name in ("signal_shot", "dark_shot", "read_noise", "quantization", "pattern_noise"):
            assert name in entries
        matplotlib.pyplot.close(fig)

    def test_legend_entries_carry_e_rms_units(self) -> None:
        """Units on every value (owner hard rule) survives the move to the legend."""
        fig = plot_noise_pie(self._dominated_terms())
        legend = fig.axes[0].get_legend()
        assert legend is not None
        for text in legend.get_texts():
            assert "e- RMS" in text.get_text()
        matplotlib.pyplot.close(fig)

    def test_comparable_terms_keep_their_wedge_labels(self) -> None:
        """The suppression is threshold-based, not blanket: even splits stay labelled."""
        terms = [_FakeNoiseTerm("a", 100.0), _FakeNoiseTerm("b", 100.0)]
        fig = plot_noise_pie(terms)
        drawn = [t.get_text() for t in fig.axes[0].texts if t.get_text()]
        assert len(drawn) == 2
        matplotlib.pyplot.close(fig)


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
        """pixel_grid defaults False → no grid mesh, but the single pixel is outlined.

        Walkthrough items 14 and 20 changed this default: the plain PSF plot is
        now cropped to a few detector pixels and outlines the pixel the core lands
        in, so the title names the pitch and a Rectangle patch is present. The
        distinguishing feature of ``pixel_grid=True`` is the *mesh* of Line2D
        gridlines, which must still be absent here.
        """
        from matplotlib.patches import Rectangle

        psf = self._psf()
        fig = plot_psf(psf)
        ax = fig.axes[0]
        # Newlines normalised: CU-241 soft-wraps long titles so they cannot clip at a
        # narrow card's edges. The wrap is a line-break policy, not a content change —
        # this asserts the content, and TestCardReadableGeometry asserts the wrapping.
        assert ax.get_title().replace("\n", " ") == "Effective PSF (10.0 µm pixel outlined)"
        assert not ax.get_lines()  # no pixel-boundary grid mesh
        # Exactly one pixel outlined, not a grid of them.
        assert len([p for p in ax.patches if isinstance(p, Rectangle)]) == 1
        # Cropped to the core rather than the full array (item 14).
        lo, hi = ax.get_xlim()
        assert (hi - lo) < psf.data.shape[0]
        matplotlib.pyplot.close(fig)

    def test_pixel_outline_can_be_suppressed(self) -> None:
        """``pixel_outline=False`` drops the rectangle for callers that want a bare map."""
        from matplotlib.patches import Rectangle

        fig = plot_psf(self._psf(), pixel_outline=False)
        ax = fig.axes[0]
        assert not [p for p in ax.patches if isinstance(p, Rectangle)]
        matplotlib.pyplot.close(fig)

    def test_span_pixels_controls_the_crop_width(self) -> None:
        """A wider span shows more of the array (item 14's zoom is a parameter, not fixed)."""
        psf = self._psf()
        narrow = plot_psf(psf, span_pixels=4)
        wide = plot_psf(psf, span_pixels=12)
        nlo, nhi = narrow.axes[0].get_xlim()
        wlo, whi = wide.axes[0].get_xlim()
        assert (whi - wlo) > (nhi - nlo)
        matplotlib.pyplot.close(narrow)
        matplotlib.pyplot.close(wide)

    def test_deprecated_pixel_grid_span_still_works(self) -> None:
        """The old kwarg keeps working, with a DeprecationWarning."""
        with pytest.warns(DeprecationWarning, match="pixel_grid_span"):
            fig = plot_psf(self._psf(), pixel_grid=True, pixel_grid_span=8)
        matplotlib.pyplot.close(fig)

    def test_default_axes_are_focal_plane_microns(self) -> None:
        """CU-241 supersedes CU-136: physical axes, not sample indices.

        CU-136's point was that the axes must not be *mislabelled* as detector
        pixels when they were really the sample grid, and it fixed that by naming
        the sample grid. CU-241 goes the rest of the way: the reader wants the size
        of the blur, and the title already quotes the detector pitch in µm, so the
        axes are now µm on the focal plane. The CU-136 hazard — axes claiming units
        they do not have — is still guarded, by the degenerate-grid case below.
        """
        fig = plot_psf(self._psf())
        ax = fig.axes[0]
        assert ax.get_xlabel() == "x on focal plane (µm)"
        assert ax.get_ylabel() == "y on focal plane (µm)"
        matplotlib.pyplot.close(fig)

    def test_grid_overlays_lines_and_crops_and_titles_pitch(self) -> None:
        """pixel_grid=True → gridlines drawn, view cropped to the core, pitch (µm) in title."""
        psf = self._psf()
        fig = plot_psf(psf, pixel_grid=True, span_pixels=8)
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


@pytest.mark.level1
class TestPlotTheme:
    """CU-139: the plot_theme(dark=…) public rcParams seam."""

    def test_dark_context_applies_dark_facecolor(self) -> None:
        import matplotlib.pyplot as plt

        with plot_theme(dark=True):
            fig, ax = plt.subplots()
            # Within the context, the figure inherits the dark chrome rcParams.
            assert fig.get_facecolor()[:3] != (1.0, 1.0, 1.0)  # not white
            assert plt.rcParams["text.color"] == "#e0e0e0"
            plt.close(fig)

    def test_light_context_is_a_noop(self) -> None:
        import matplotlib.pyplot as plt

        before = plt.rcParams["figure.facecolor"]
        with plot_theme(dark=False):
            assert plt.rcParams["figure.facecolor"] == before  # unchanged
        assert plt.rcParams["figure.facecolor"] == before

    def test_dark_context_restores_rcparams_on_exit(self) -> None:
        import matplotlib.pyplot as plt

        before = plt.rcParams["text.color"]
        with plot_theme(dark=True):
            assert plt.rcParams["text.color"] == "#e0e0e0"
        assert plt.rcParams["text.color"] == before  # restored


class TestKernelStageAttribution:
    """CU-243 — a kernel card must name the stage that applied it."""

    def test_owner_map_covers_every_kernel_the_chain_builds(self) -> None:
        """The attribution is a fact about the chain, so it must be complete.

        An unmapped kernel would render "added by ?" — worse than no label,
        because it looks like a bug rather than a gap in this table.
        """
        from radiant.api.plot import _KERNEL_OWNER_STAGE

        # The kernels the chain can apply, per the signal-chain docs.
        for name in (
            "optical",
            "pixel_aperture",
            "charge_diffusion",
            "jitter",
            "smear",
            "turbulence",
            "ipc",
        ):
            assert name in _KERNEL_OWNER_STAGE, f"kernel {name!r} has no owning stage"

    def test_upstream_kernels_are_attributed_not_anonymous(self) -> None:
        """The exact defect: pixel_aperture shown on Platform with no owner."""
        from radiant.api.plot import kernel_owner_stage

        assert kernel_owner_stage("pixel_aperture") == "Optics"
        assert kernel_owner_stage("jitter") == "Platform"
        assert kernel_owner_stage("ipc") == "Performance"
        assert kernel_owner_stage("not_a_kernel") == "?"

    def test_titles_carry_the_owning_stage(self) -> None:
        """Rendered titles, not just the map — the label has to reach the card."""
        import numpy as np

        from radiant.api.plot import plot_psf_kernels
        from radiant.optics.psf.effective import EffectivePSF

        n = 64
        yy, xx = np.mgrid[0:n, 0:n]
        c = (n - 1) / 2.0
        core = np.exp(-((xx - c) ** 2 + (yy - c) ** 2) / (2.0 * 2.0**2))
        kern = np.zeros((n, n))
        kern[c1 := int(c), c1] = 1.0
        psf = EffectivePSF(
            data=core / core.sum(),
            sample_spacing_m=2.0e-6,
            pixel_pitch_m=18.0e-6,
            wavelength_um=4.0,
            convolution_history=("pixel_aperture",),
            kernels=(("pixel_aperture", kern),),
        )
        fig = plot_psf_kernels(psf)
        title = fig.axes[0].get_title()
        assert "pixel_aperture" in title
        assert "added by Optics" in title
        matplotlib.pyplot.close(fig)


@pytest.mark.level1
class TestFiguresArePyplotFree:
    """CU-116: ``result.plot.*`` figures are not registered with pyplot's ``Gcf``.

    The figures are owned by whoever asked for them — the GUI embeds them in its own
    ``FigureCanvasQTAgg``, a script saves them — so pyplot's process-global registry
    only kept them alive past their use (the GUI held 22 figures once the operator had
    visited all nine stages, over matplotlib's 20-figure ``max_open_warning``) and made
    releasing them a ``plt.close()`` that deadlocks inside a Qt signal handler.
    """

    def test_plot_functions_open_no_pyplot_figures(self) -> None:
        import matplotlib.pyplot as plt

        plt.close("all")
        figures = [
            plot_sweep(_make_sweep_result()),
            plot_sweep_2d(_make_sweep_2d_result()),
            plot_noise_budget([_FakeNoiseTerm("shot", 30.0), _FakeNoiseTerm("read", 10.0)]),
            plot_noise_pie([_FakeNoiseTerm("shot", 30.0), _FakeNoiseTerm("read", 10.0)]),
            plot_spectral(np.array([3.0, 4.0, 5.0]), np.array([1.0, 2.0, 3.0])),
        ]
        assert all(isinstance(fig, Figure) for fig in figures)
        assert plt.get_fignums() == [], (
            f"{len(plt.get_fignums())} figures registered with pyplot; "
            "result.plot.* must build unregistered Figures (CU-116)"
        )

    def test_unregistered_figure_still_saves_and_lays_out(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """The two properties a pyplot-free figure must keep: constrained layout and savefig."""
        fig = plot_sweep(_make_sweep_result())
        assert isinstance(fig.get_layout_engine(), ConstrainedLayoutEngine)
        out = tmp_path / "sweep.png"
        fig.savefig(out)
        assert out.stat().st_size > 0

    def test_dark_theme_still_reaches_an_unregistered_figure(self) -> None:
        """CU-139's rcParams seam works on ``Figure`` construction, not via pyplot."""
        with plot_theme(dark=True):
            fig = plot_sweep(_make_sweep_result())
        assert fig.get_facecolor()[:3] != (1.0, 1.0, 1.0)  # dark chrome applied
        assert fig.axes[0].title.get_color() == "#e0e0e0"


class TestBackendIsNotHijacked:
    """CU-287: a plot call must not reconfigure an embedder's matplotlib backend.

    ``_require_matplotlib`` used to call ``matplotlib.use("Agg")`` unconditionally, so
    the first ``result.plot.*`` call switched the backend out from under a Jupyter
    session running ``%matplotlib qt`` or any other embedder. The headless guarantee
    it existed for is kept — with *nothing* selected, Agg is still forced — so both
    halves are pinned here: one in-process, one in a fresh interpreter (the only place
    "no backend selected yet" can be observed, since this module selects Agg at import).
    """

    def test_an_already_selected_backend_survives_a_plot_call(self) -> None:
        from radiant.api.plot import _require_matplotlib

        previous = matplotlib.get_backend()
        matplotlib.use("svg")  # stand-in for an embedder's interactive selection
        try:
            _require_matplotlib()
            assert matplotlib.get_backend().lower() == "svg", (
                f"backend became {matplotlib.get_backend()!r}; a library call must not "
                "reconfigure the host process (CU-287)"
            )
        finally:
            matplotlib.use(previous)

    def test_agg_is_still_forced_when_no_backend_has_been_selected(self) -> None:
        """The headless half: a bare interpreter (no ``MPLBACKEND``) still lands on Agg.

        Run out-of-process because the check is only meaningful before *anything* has
        touched the backend, which is untrue inside this test session.
        """
        import os
        import subprocess
        import sys

        env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
        env.pop("MPLBACKEND", None)
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import matplotlib\n"
                "from radiant.api.plot import _require_matplotlib\n"
                "_require_matplotlib()\n"
                "print(matplotlib.get_backend())\n",
            ],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        assert proc.stdout.strip().lower() == "agg", (
            f"headless default backend is {proc.stdout.strip()!r}, expected Agg (CU-287)"
        )


@pytest.mark.level1
class TestCardReadableGeometry:
    """CU-241: the figure-side half of the unreadable-plot-card fix.

    These pin the three properties that made the pupil/PSF/pie cards unreadable at the
    sizes the GUI actually renders them (a 200-500 px wide plot column), each measured
    at that size rather than at matplotlib's 640x480 default: no text runs off the
    canvas, the colorbar does not eat the map, and the pie's own labels stay inside it.
    """

    _CARD_PX: tuple[int, int] = (420, 300)

    def _drawn(self, fig: Figure) -> Figure:
        """Render *fig* at a realistic card size so text extents are measurable."""
        fig.set_dpi(100)
        fig.set_size_inches(self._CARD_PX[0] / 100.0, self._CARD_PX[1] / 100.0)
        fig.canvas.draw()
        return fig

    def _overflow_px(self, fig: Figure) -> float:
        """Total horizontal overflow of the title + every axes text past the canvas."""
        ax = fig.axes[0]
        width = float(self._CARD_PX[0])
        boxes = [ax.title.get_window_extent()]
        boxes += [t.get_window_extent() for t in ax.texts if t.get_text()]
        return sum(max(0.0, -bb.x0) + max(0.0, bb.x1 - width) for bb in boxes)

    def test_long_psf_title_wraps_instead_of_clipping(self) -> None:
        """The pixel-grid title is longer than a 420 px card: it must wrap, not clip."""
        psf = TestPlotPsfPixelGrid._psf()
        fig = self._drawn(plot_psf(psf, pixel_grid=True))
        title = fig.axes[0].get_title()
        assert "\n" in title, f"long title did not wrap: {title!r}"
        assert max(len(line) for line in title.split("\n")) <= 34
        assert self._overflow_px(fig) == 0.0
        matplotlib.pyplot.close(fig)

    def test_pupil_colorbar_is_a_slim_fraction_of_the_map(self) -> None:
        """The colorbar must not take a third of the axes width (CU-241 defect 3)."""
        fig = self._drawn(plot_pupil_phase(np.zeros((32, 32)), 0.3))
        image_ax, cbar_ax = fig.axes[0], fig.axes[1]
        image_w = image_ax.get_position().width
        assert cbar_ax.get_position().width < 0.15 * image_w
        # ... and it spans the aspect-locked image, not the whole figure height.
        assert cbar_ax.get_position().height == pytest.approx(
            image_ax.get_position().height, rel=0.12
        )
        matplotlib.pyplot.close(fig)

    def test_pie_labels_and_title_stay_inside_the_card(self) -> None:
        """On-wedge labels sit inside the pie, so neither edge clips them."""
        terms = [
            _FakeNoiseTerm("signal_shot", 100.0),
            _FakeNoiseTerm("dark_shot", 60.0),
            _FakeNoiseTerm("read_noise", 5.0),
        ]
        fig = self._drawn(plot_noise_pie(terms))
        assert self._overflow_px(fig) == 0.0
        matplotlib.pyplot.close(fig)

    def test_pie_legend_sits_below_the_pie_not_beside_it(self) -> None:
        """A right-hand legend competes with the aspect-locked pie for card width."""
        fig = plot_noise_pie([_FakeNoiseTerm("a", 10.0), _FakeNoiseTerm("b", 5.0)])
        legend = fig.axes[0].get_legend()
        assert legend is not None
        anchor = legend.get_bbox_to_anchor()
        assert anchor is not None
        # Anchored on the axes' bottom edge (y ≈ 0), horizontally centred.
        assert legend.get_window_extent().y0 <= fig.axes[0].get_window_extent().y0 + 1.0
        matplotlib.pyplot.close(fig)
