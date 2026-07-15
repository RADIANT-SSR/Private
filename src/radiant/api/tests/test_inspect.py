"""Tests for the ChainResult inspector."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.errors import ApiValidationError
from radiant.api.inspect import ResultPlotNamespace, inspect_result
from radiant.core.chain import ChainState
from radiant.core.radiometry import NoiseTerm, RadiometricFrame
from radiant.io.results import ChainResult


def _make_result() -> ChainResult:
    """Build a minimal ChainResult for testing the inspector."""
    wl = np.linspace(3.5, 5.0, 10)
    state = ChainState(wavelength_um=wl)
    state = state.with_metric("snr", 47.3)
    state = state.with_metric("nedt", 0.023)
    state = state.with_stage_output("source", "regime_tentative", "extended")
    state = state.with_stage_output("optics", "regime", "extended")
    state = state.with_stage_output("optics", "ee_box", 0.82)
    state = state.with_noise(
        NoiseTerm(
            name="photon_shot",
            value_e=111.6,
            origin_frame="photoelectrons",
            physical_basis="Poisson",
        )
    )
    state = state.with_noise(
        NoiseTerm(
            name="dark_current_shot",
            value_e=89.2,
            origin_frame="photoelectrons",
            physical_basis="Poisson",
        )
    )
    state = state.with_history("source")
    state = state.with_history("optics")
    return ChainResult(state)


@pytest.mark.level1
class TestInspectFull:
    def test_full_tree_contains_metrics(self) -> None:
        result = _make_result()
        tree = inspect_result(result)
        assert "ChainResult" in tree
        assert "metrics" in tree
        assert "snr" in tree
        assert "47.3" in tree

    def test_full_tree_contains_noise(self) -> None:
        result = _make_result()
        tree = inspect_result(result)
        assert "noise_terms" in tree
        assert "photon_shot" in tree
        assert "111.6" in tree

    def test_full_tree_contains_stages(self) -> None:
        result = _make_result()
        tree = inspect_result(result)
        assert "source" in tree
        assert "optics" in tree

    def test_tree_structure_has_box_drawing(self) -> None:
        result = _make_result()
        tree = inspect_result(result)
        # Box-drawing characters should be present
        assert "\u251c" in tree or "\u2514" in tree


@pytest.mark.level1
class TestInspectStage:
    def test_single_stage(self) -> None:
        result = _make_result()
        text = inspect_result(result, "optics")
        assert "optics" in text
        assert "regime" in text
        assert "ee_box" in text

    def test_unknown_stage(self) -> None:
        result = _make_result()
        text = inspect_result(result, "nonexistent")
        assert "not found" in text
        assert "Available" in text


@pytest.mark.level1
class TestResultPlotNamespace:
    def test_namespace_creation(self) -> None:
        result = _make_result()
        ns = ResultPlotNamespace(result)
        assert hasattr(ns, "psf")
        assert hasattr(ns, "noise_budget")
        assert hasattr(ns, "mtf")

    def test_psf_raises_without_data(self) -> None:
        result = _make_result()
        ns = ResultPlotNamespace(result)
        with pytest.raises(ValueError, match="No effective PSF"):
            ns.psf()


def _make_spectral_result(*, with_background: bool = True) -> ChainResult:
    """Build a ChainResult carrying the real spectral frames/outputs.

    Mirrors what AtmosphereStage/OpticsStage store: at-aperture target
    (and optional background) radiance frames, the post-optics frame, and
    the atmosphere ``tau_atm`` / ``L_path`` spectral arrays.
    """
    wl = np.linspace(3.5, 5.0, 20)
    l_target = np.exp(-((wl - 4.2) ** 2) / 0.2) * 5.0
    l_bg = np.exp(-((wl - 4.4) ** 2) / 0.3) * 3.0
    l_source_target = l_target / 0.8  # pre-atmosphere (L_ap = τ·L_src, τ=0.8)
    l_source_bg = l_bg / 0.8
    l_post = l_target * 0.6
    tau = 0.8 * np.ones_like(wl)
    l_path = 0.5 * np.ones_like(wl)

    state = ChainState(wavelength_um=wl)
    state = state.with_frame(
        RadiometricFrame(name="at_aperture_target", wavelength_um=wl, spectral_radiance=l_target)
    )
    state = state.with_frame(
        RadiometricFrame(name="at_aperture", wavelength_um=wl, spectral_radiance=l_target)
    )
    state = state.with_frame(
        RadiometricFrame(
            name="at_source_target", wavelength_um=wl, spectral_radiance=l_source_target
        )
    )
    if with_background:
        state = state.with_frame(
            RadiometricFrame(
                name="at_aperture_background", wavelength_um=wl, spectral_radiance=l_bg
            )
        )
        state = state.with_frame(
            RadiometricFrame(
                name="at_source_background", wavelength_um=wl, spectral_radiance=l_source_bg
            )
        )
    state = state.with_frame(
        RadiometricFrame(name="post_optics", wavelength_um=wl, spectral_radiance=l_post)
    )
    state = state.with_stage_output("atmosphere", "tau_atm", tau)
    state = state.with_stage_output("atmosphere", "L_path", l_path)
    return ChainResult(state)


@pytest.mark.level1
class TestSpectralAccessors:
    def test_source_returns_figure_with_units(self) -> None:
        ns = ResultPlotNamespace(_make_spectral_result())
        fig = ns.spectral_source()
        ax = fig.axes[0]
        assert "µm" in ax.get_xlabel()
        assert "W/m²/sr/µm" in ax.get_ylabel()

    def test_source_plots_target_and_background(self) -> None:
        result = _make_spectral_result(with_background=True)
        ns = ResultPlotNamespace(result)
        fig = ns.spectral_source()
        ax = fig.axes[0]
        assert len(ax.lines) == 2
        # Data matches the stored frames it plots.
        expected = result.frames["at_aperture_target"].spectral_radiance
        np.testing.assert_array_equal(ax.lines[0].get_ydata(), expected)

    def test_source_target_only(self) -> None:
        ns = ResultPlotNamespace(_make_spectral_result(with_background=False))
        fig = ns.spectral_source()
        assert len(fig.axes[0].lines) == 1

    def test_source_raises_without_frame(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        ns = ResultPlotNamespace(ChainResult(ChainState(wavelength_um=wl)))
        with pytest.raises(ApiValidationError, match="target spectral-radiance frame"):
            ns.spectral_source()

    def test_source_emission_returns_figure_with_units(self) -> None:
        ns = ResultPlotNamespace(_make_spectral_result())
        fig = ns.spectral_source_emission()
        ax = fig.axes[0]
        assert "µm" in ax.get_xlabel()
        assert "W/m²/sr/µm" in ax.get_ylabel()
        assert "before atmosphere" in ax.get_title()

    def test_source_emission_plots_target_and_background(self) -> None:
        result = _make_spectral_result(with_background=True)
        fig = ResultPlotNamespace(result).spectral_source_emission()
        ax = fig.axes[0]
        assert len(ax.lines) == 2
        expected = result.frames["at_source_target"].spectral_radiance
        np.testing.assert_array_equal(ax.lines[0].get_ydata(), expected)

    def test_source_emission_target_only(self) -> None:
        ns = ResultPlotNamespace(_make_spectral_result(with_background=False))
        fig = ns.spectral_source_emission()
        assert len(fig.axes[0].lines) == 1

    def test_source_emission_raises_without_frame(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        ns = ResultPlotNamespace(ChainResult(ChainState(wavelength_um=wl)))
        with pytest.raises(ApiValidationError, match="at_source_target"):
            ns.spectral_source_emission()

    def test_atmosphere_returns_twin_unit_axes(self) -> None:
        ns = ResultPlotNamespace(_make_spectral_result())
        fig = ns.spectral_atmosphere()
        ylabels = [a.get_ylabel() for a in fig.axes]
        assert any("dimensionless" in y for y in ylabels)
        assert any("W/m²/sr/µm" in y for y in ylabels)
        assert "µm" in fig.axes[0].get_xlabel()

    def test_atmosphere_data_matches_outputs(self) -> None:
        result = _make_spectral_result()
        fig = ResultPlotNamespace(result).spectral_atmosphere()
        tau_line = fig.axes[0].lines[0]
        np.testing.assert_array_equal(
            tau_line.get_ydata(), result.stage_outputs["atmosphere"]["tau_atm"]
        )

    def test_atmosphere_raises_without_outputs(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        ns = ResultPlotNamespace(ChainResult(ChainState(wavelength_um=wl)))
        with pytest.raises(ApiValidationError, match="atmospheric spectral arrays"):
            ns.spectral_atmosphere()

    def test_inband_returns_figure_with_units(self) -> None:
        result = _make_spectral_result()
        fig = ResultPlotNamespace(result).spectral_inband()
        ax = fig.axes[0]
        assert "µm" in ax.get_xlabel()
        assert "W/m²/sr/µm" in ax.get_ylabel()
        np.testing.assert_array_equal(
            ax.lines[0].get_ydata(), result.frames["post_optics"].spectral_radiance
        )

    def test_inband_raises_without_frame(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        ns = ResultPlotNamespace(ChainResult(ChainState(wavelength_um=wl)))
        with pytest.raises(ApiValidationError, match="post_optics"):
            ns.spectral_inband()
