"""Tests for the ChainResult inspector."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.errors import ApiValidationError
from radiant.api.inspect import ResultPlotNamespace, inspect_result
from radiant.core.chain import ChainState
from radiant.core.radiometry import NoiseTerm, RadiometricFrame
from radiant.core.spectral import SpectralData
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

    def test_nested_large_array_is_summarised_not_dumped(self) -> None:
        """CU-113: a big array nested inside a container/object repr collapses.

        A *direct* array stage output is already collapsed by ``_fmt`` to
        ``ndarray(shape=…)``; the regression is an array reached only via a
        surrounding object's ``repr`` (a tuple/list/dataclass), which the
        printoptions context now summarises too.
        """
        wl = np.linspace(3.5, 5.0, 10)
        big = np.arange(5000.0)
        state = ChainState(wavelength_um=wl)
        state = state.with_stage_output("optics", "regime", "extended")
        state = state.with_stage_output("detector", "wrapped", (big,))  # nested in a tuple repr
        text = inspect_result(ChainResult(state))
        assert "..." in text  # NumPy summarised form
        assert text.count("\n") < 200  # would be thousands without the fix


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


class TestNoisePieAccessor:
    """PS-3 Part A: result.plot.noise_pie() — variance-share pie over result.noise_terms."""

    def test_returns_figure_from_result_terms(self) -> None:
        ns = ResultPlotNamespace(_make_result())
        fig = ns.noise_pie()
        assert fig.axes  # a drawn pie

    def test_wedges_match_result_noise_terms_variance(self) -> None:
        """Data fidelity: each wedge span is the term's σ² fraction of result.noise_terms."""
        result = _make_result()
        fig = ResultPlotNamespace(result).noise_pie()
        spans = [w.theta2 - w.theta1 for w in fig.axes[0].patches]
        variances = sorted((nt.value_e**2 for nt in result.noise_terms), reverse=True)
        total = sum(variances)
        for span, var in zip(spans, variances, strict=True):
            assert span / sum(spans) == pytest.approx(var / total, abs=1e-6)

    def test_raises_when_noise_terms_absent(self) -> None:
        state = ChainState(wavelength_um=np.linspace(3.5, 5.0, 6))
        ns = ResultPlotNamespace(ChainResult(state))
        with pytest.raises(ApiValidationError, match="No noise terms"):
            ns.noise_pie()


class TestPsfPixelGridAccessor:
    """PS-3 Part A: result.plot.psf_pixel_grid() — psf() with the detector pixel grid."""

    def test_returns_figure_with_grid(self) -> None:
        from radiant.optics.psf.effective import EffectivePSF

        n = 96
        yy, xx = np.mgrid[0:n, 0:n]
        c = (n - 1) / 2.0
        data = np.exp(-((xx - c) ** 2 + (yy - c) ** 2) / (2.0 * 2.0**2))
        psf = EffectivePSF(
            data=data / data.sum(),
            sample_spacing_m=2.0e-6,
            pixel_pitch_m=1.0e-5,
            wavelength_um=4.0,
            convolution_history=("diffraction",),
        )
        state = ChainState(wavelength_um=np.linspace(3.5, 5.0, 6))
        state = state.with_stage_output("optics", "effective_psf", psf)
        fig = ResultPlotNamespace(ChainResult(state)).psf_pixel_grid()
        assert fig.axes[0].get_lines()  # pixel-grid lines present
        assert "µm pitch" in fig.axes[0].get_title()

    def test_raises_without_psf(self) -> None:
        state = ChainState(wavelength_um=np.linspace(3.5, 5.0, 6))
        ns = ResultPlotNamespace(ChainResult(state))
        with pytest.raises(ApiValidationError, match="No effective PSF"):
            ns.psf_pixel_grid()


def _make_pupil_result(*, with_phase: bool = True, extent_m: float = 0.30) -> ChainResult:
    """Build a ChainResult carrying persisted complex-pupil diagnostic maps."""
    wl = np.linspace(3.5, 5.0, 10)
    state = ChainState(wavelength_um=wl)
    npix = 16
    amp = np.zeros((npix, npix), dtype=np.float64)
    yy, xx = np.mgrid[0:npix, 0:npix]
    r = np.sqrt((xx - npix / 2 + 0.5) ** 2 + (yy - npix / 2 + 0.5) ** 2)
    amp[r <= npix / 2] = 1.0
    amp[r <= npix / 6] = 0.0  # central obscuration
    state = state.with_stage_output("optics", "pupil_amplitude", amp)
    state = state.with_stage_output("optics", "pupil_plane_extent_m", extent_m)
    if with_phase:
        phase = np.where(amp > 0.0, 0.15 * (xx - npix / 2), 0.0).astype(np.float64)
        state = state.with_stage_output("optics", "pupil_phase_waves", phase)
        state = state.with_stage_output("optics", "pupil_wavelength_um", 4.25)
    return ChainResult(state)


class TestPupilAccessors:
    def test_amplitude_returns_figure_with_units(self) -> None:
        ns = ResultPlotNamespace(_make_pupil_result())
        fig = ns.pupil_amplitude()
        ax = fig.axes[0]
        # Colorbar label carries the dimensionless-transmission unit.
        cbar_labels = [a.get_ylabel() for a in fig.axes]
        assert any("transmission" in lbl for lbl in cbar_labels)
        assert "m)" in ax.get_xlabel()  # pupil x (m) — extent supplied
        assert "apodization" in ax.get_title()

    def test_amplitude_data_matches_output(self) -> None:
        result = _make_pupil_result()
        fig = ResultPlotNamespace(result).pupil_amplitude()
        shown = fig.axes[0].images[0].get_array()
        np.testing.assert_array_equal(shown, result.stage_outputs["optics"]["pupil_amplitude"])

    def test_phase_returns_figure_with_waves_colorbar(self) -> None:
        ns = ResultPlotNamespace(_make_pupil_result())
        fig = ns.pupil_phase()
        cbar_labels = [a.get_ylabel() for a in fig.axes]
        assert any("waves" in lbl for lbl in cbar_labels)
        assert "wavefront error" in fig.axes[0].get_title()

    def test_axes_fall_back_to_samples_without_extent(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        state = ChainState(wavelength_um=wl)
        amp = np.ones((8, 8), dtype=np.float64)
        state = state.with_stage_output("optics", "pupil_amplitude", amp)
        fig = ResultPlotNamespace(ChainResult(state)).pupil_amplitude()
        assert "samples" in fig.axes[0].get_xlabel()

    def test_amplitude_raises_without_map(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        ns = ResultPlotNamespace(ChainResult(ChainState(wavelength_um=wl)))
        with pytest.raises(ApiValidationError, match="pupil amplitude map"):
            ns.pupil_amplitude()

    def test_phase_raises_without_map(self) -> None:
        # Amplitude present but phase absent (unsupported WFE mode).
        ns = ResultPlotNamespace(_make_pupil_result(with_phase=False))
        with pytest.raises(ApiValidationError, match="pupil phase"):
            ns.pupil_phase()


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


def _make_reflective_result() -> ChainResult:
    """A result carrying the two reflective-view products (owner item 6).

    ρ(λ) is a ramp so a flat-vs-spectral mix-up would show, and the reflected
    radiance is a distinct curve so the two accessors cannot pass by plotting
    each other's data.
    """
    wl = np.linspace(0.4, 0.9, 20)
    rho = 0.2 + 0.4 * (wl - 0.4) / 0.5
    l_reflected = rho * 1200.0 / np.pi

    state = ChainState(wavelength_um=wl)
    state = state.with_stage_output(
        "source",
        "reflectance",
        SpectralData(
            name="target_reflectance",
            wavelength_um=wl,
            values=rho,
            unit="dimensionless",
            source="test",
        ),
    )
    state = state.with_frame(
        RadiometricFrame(
            name="at_source_target_reflected",
            wavelength_um=wl,
            spectral_radiance=l_reflected,
        )
    )
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

    def test_reflectance_returns_dimensionless_figure(self) -> None:
        """Owner item 6: the reflective view's lead figure is ρ(λ), not a radiance."""
        result = _make_reflective_result()
        fig = ResultPlotNamespace(result).target_reflectance()
        ax = fig.axes[0]
        assert "µm" in ax.get_xlabel()
        assert "dimensionless" in ax.get_ylabel()
        assert "W/m²/sr/µm" not in ax.get_ylabel()
        np.testing.assert_array_equal(
            ax.lines[0].get_ydata(),
            result.stage_outputs["source"]["reflectance"].values,
        )

    def test_reflectance_raises_for_a_target_that_has_none(self) -> None:
        """A pure-thermal scene gets the actionable message, never a zero curve."""
        ns = ResultPlotNamespace(_make_spectral_result())
        with pytest.raises(ApiValidationError, match="carries none"):
            ns.target_reflectance()

    def test_reflected_radiance_returns_figure_with_units(self) -> None:
        result = _make_reflective_result()
        fig = ResultPlotNamespace(result).spectral_reflected_radiance()
        ax = fig.axes[0]
        assert "µm" in ax.get_xlabel()
        assert "W/m²/sr/µm" in ax.get_ylabel()
        np.testing.assert_array_equal(
            ax.lines[0].get_ydata(),
            result.frames["at_source_target_reflected"].spectral_radiance,
        )

    def test_reflected_radiance_raises_without_frame(self) -> None:
        ns = ResultPlotNamespace(_make_spectral_result())
        with pytest.raises(ApiValidationError, match="at_source_target_reflected"):
            ns.spectral_reflected_radiance()

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


def _make_optics_result() -> ChainResult:
    """Build a ChainResult carrying the real optics coating outputs.

    Mirrors what OpticsStage stores: the ``tau_opt_spectral`` system-throughput
    ``SpectralData`` plus an ``elements`` tuple of ``OpticalElement`` — here a
    mirror (T ≡ 0, R + ε=1-R) and a transmissive window (T + R), so both the
    reflective-only and transmissive presentations are exercised.
    """
    from radiant.core.spectral import SpectralData
    from radiant.optics.element import ElementKind, OpticalElement

    wl = np.linspace(3.5, 5.0, 20)
    mirror = OpticalElement(
        name="primary_mirror",
        kind=ElementKind.MIRROR,
        temperature_K=250.0,
        transmittance=SpectralData("T", wl, np.zeros_like(wl), "", "test"),
        reflectance=SpectralData("R", wl, 0.96 * np.ones_like(wl), "", "test"),
        diameter_m=0.3,
        distance_to_fpa_m=0.5,
    )
    window = OpticalElement(
        name="dewar_window",
        kind=ElementKind.WINDOW,
        temperature_K=200.0,
        transmittance=SpectralData("T", wl, 0.90 * np.ones_like(wl), "", "test"),
        reflectance=SpectralData("R", wl, 0.05 * np.ones_like(wl), "", "test"),
        diameter_m=0.05,
        distance_to_fpa_m=0.1,
    )
    tau = SpectralData("tau_opt", wl, 0.86 * np.ones_like(wl), "", "test")
    state = ChainState(wavelength_um=wl)
    state = state.with_stage_output("optics", "tau_opt_spectral", tau)
    state = state.with_stage_output("optics", "elements", (mirror, window))
    return ChainResult(state)


@pytest.mark.level1
class TestOpticsCoatingAccessors:
    def test_throughput_returns_figure_with_units(self) -> None:
        result = _make_optics_result()
        fig = ResultPlotNamespace(result).optical_throughput()
        ax = fig.axes[0]
        assert "µm" in ax.get_xlabel()
        assert "dimensionless" in ax.get_ylabel()
        # Plotted data is the stored SpectralData, untransformed.
        stored = result.stage_outputs["optics"]["tau_opt_spectral"]
        np.testing.assert_array_equal(ax.lines[0].get_ydata(), stored.values)
        np.testing.assert_array_equal(ax.lines[0].get_xdata(), stored.wavelength_um)

    def test_throughput_raises_without_output(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        ns = ResultPlotNamespace(ChainResult(ChainState(wavelength_um=wl)))
        with pytest.raises(ApiValidationError, match="tau_opt_spectral"):
            ns.optical_throughput()

    def test_coating_returns_figure_with_units(self) -> None:
        fig = ResultPlotNamespace(_make_optics_result()).coating_spectra()
        ax = fig.axes[0]
        assert "µm" in ax.get_xlabel()
        assert "dimensionless" in ax.get_ylabel()

    def test_coating_mirror_omits_zero_transmission(self) -> None:
        # Mirror: T ≡ 0 (omitted) → contributes R and ε=1-R only.
        # Window (simple refractive): T + R (both non-zero); ε ≡ 0 (omitted).
        result = _make_optics_result()
        fig = ResultPlotNamespace(result).coating_spectra()
        labels = {line.get_label() for line in fig.axes[0].lines}
        assert "primary_mirror R" in labels
        assert "primary_mirror ε" in labels
        assert "primary_mirror T" not in labels  # T ≡ 0 omitted
        assert "dewar_window T" in labels
        assert "dewar_window R" in labels

    def test_coating_data_matches_stored_elements(self) -> None:
        result = _make_optics_result()
        mirror = result.stage_outputs["optics"]["elements"][0]
        fig = ResultPlotNamespace(result).coating_spectra()
        by_label = {line.get_label(): line for line in fig.axes[0].lines}
        # R is the raw stored reflectance; ε is the element's Kirchhoff property.
        np.testing.assert_array_equal(
            by_label["primary_mirror R"].get_ydata(), mirror.reflectance.values
        )
        np.testing.assert_array_equal(
            by_label["primary_mirror ε"].get_ydata(), mirror.emissivity.values
        )

    def test_coating_raises_without_elements(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        ns = ResultPlotNamespace(ChainResult(ChainState(wavelength_um=wl)))
        with pytest.raises(ApiValidationError, match="optical elements"):
            ns.coating_spectra()
