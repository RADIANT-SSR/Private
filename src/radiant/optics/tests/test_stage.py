"""Tests for OpticsStage wrapper."""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.core.regime import RadiometricRegime
from radiant.optics.psf.effective import EffectivePSF
from radiant.optics.stage import OpticsStage
from radiant.optics.element import ElementTransferMode
from radiant.optics.wavefront import FieldWfeSample, WavefrontError, WfeMode

from radiant.detector._schema import ALL_PARAMETERS as DET_PARAMS
from radiant.optics._schema import ALL_PARAMETERS as OPT_PARAMS


def _make_state(wl: np.ndarray) -> ChainState:
    state = ChainState(wavelength_um=wl)
    L = np.ones_like(wl) * 2.0  # W/m²/sr/µm
    frame = RadiometricFrame(
        name="at_aperture", wavelength_um=wl, spectral_radiance=L,
    )
    return state.with_frame(frame)


def _make_params(
    D: float = 0.30,
    f: float = 1.20,
    tau: float = 0.70,
    pitch: float = 18.0,
) -> ParameterSet:
    from radiant.api._param_registry import _FNUMBER_GROUP

    schema = list(OPT_PARAMS) + list(DET_PARAMS)
    ps = ParameterSet(schema, [_FNUMBER_GROUP])
    ps.set("optics.aperture_diameter_m", D)
    ps.set("optics.focal_length_m", f)
    ps.set("optics.transmission_scalar", tau)
    ps.set("detector.pixel_pitch_x_um", pitch)
    ps.set("detector.pixel_pitch_y_um", pitch)
    ps.set("detector.qe_value", 0.7)
    ps.resolve()
    return ps


class TestOpticsStage:
    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 50)

    def test_produces_post_optics_frame(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        out = OpticsStage().run(state, _make_params())
        assert "post_optics" in out.frames

    def test_throughput_applied(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        tau = 0.70
        out = OpticsStage().run(state, _make_params(tau=tau))
        L_in = state.frames["at_aperture"].spectral_radiance
        L_out = out.frames["post_optics"].spectral_radiance
        assert L_in is not None and L_out is not None
        np.testing.assert_allclose(L_out, L_in * tau, rtol=1e-12)

    def test_A_collect(self, wl: np.ndarray) -> None:
        D = 0.30
        out = OpticsStage().run(_make_state(wl), _make_params(D=D))
        A = out.stage_outputs["optics"]["A_collect"]
        expected = math.pi / 4.0 * D ** 2
        assert A == pytest.approx(expected, rel=1e-10)

    def test_Omega_pixel(self, wl: np.ndarray) -> None:
        pitch_m = 18e-6  # input is µm, schema converts to m
        f = 1.20
        out = OpticsStage().run(_make_state(wl), _make_params(f=f, pitch=18.0))
        omega = out.stage_outputs["optics"]["Omega_pixel"]
        expected = (pitch_m ** 2) / (f ** 2)
        assert omega == pytest.approx(expected, rel=1e-10)

    def test_EE_box_stubbed(self, wl: np.ndarray) -> None:
        out = OpticsStage().run(_make_state(wl), _make_params())
        assert out.stage_outputs["optics"]["EE_box"] == 1.0

    def test_regime_stubbed_extended(self, wl: np.ndarray) -> None:
        out = OpticsStage().run(_make_state(wl), _make_params())
        assert out.stage_outputs["optics"]["regime"] == RadiometricRegime.EXTENDED

    def test_name(self) -> None:
        assert OpticsStage().name == "optics"

    def test_defocus_zero_no_kernel(self, wl: np.ndarray) -> None:
        """defocus_um=0: no defocus kernel applied."""
        params = _make_params()
        params.set("optics.defocus_um", 0.0)
        params.resolve()
        out = OpticsStage().run(_make_state(wl), params)
        epsf = out.stage_outputs["optics"]["effective_psf"]
        assert "defocus" not in epsf.convolution_history

    def test_defocus_applied_degrades_mtf(self, wl: np.ndarray) -> None:
        """defocus_um=5.0 at f/4: MTF should decrease at low frequencies."""
        params_no = _make_params()
        params_no.set("optics.defocus_um", 0.0)
        params_no.resolve()
        out_no = OpticsStage().run(_make_state(wl), params_no)
        epsf_no = out_no.stage_outputs["optics"]["effective_psf"]

        params_yes = _make_params()
        params_yes.set("optics.defocus_um", 50.0)  # large enough to be measurable
        params_yes.resolve()
        out_yes = OpticsStage().run(_make_state(wl), params_yes)
        epsf_yes = out_yes.stage_outputs["optics"]["effective_psf"]

        # Compare at a low frequency where diffraction MTF is measurable.
        freq_no, mtf_no = epsf_no.mtf_1d("x")
        freq_yes, mtf_yes = epsf_yes.mtf_1d("x")
        # Use ~10% of frequency range to stay well inside the diffraction cutoff.
        idx = max(1, len(freq_no) // 20)
        assert mtf_yes[idx] < mtf_no[idx]

    def test_defocus_negative_same_as_positive(self, wl: np.ndarray) -> None:
        """Negative defocus produces same ePSF as positive (symmetric)."""
        params_pos = _make_params()
        params_pos.set("optics.defocus_um", 5.0)
        params_pos.resolve()
        out_pos = OpticsStage().run(_make_state(wl), params_pos)

        params_neg = _make_params()
        params_neg.set("optics.defocus_um", -5.0)
        params_neg.resolve()
        out_neg = OpticsStage().run(_make_state(wl), params_neg)

        epsf_pos = out_pos.stage_outputs["optics"]["effective_psf"]
        epsf_neg = out_neg.stage_outputs["optics"]["effective_psf"]
        np.testing.assert_allclose(epsf_pos.data, epsf_neg.data, rtol=1e-12)

    def test_defocus_sigma_stored(self, wl: np.ndarray) -> None:
        """defocus_sigma_m stored in stage outputs."""
        params = _make_params()
        params.set("optics.defocus_um", 5.0)
        params.resolve()
        out = OpticsStage().run(_make_state(wl), params)
        sigma = out.stage_outputs["optics"]["defocus_sigma_m"]
        assert sigma > 0.0

    def test_defocus_increases_fwhm(self, wl: np.ndarray) -> None:
        """Large defocus increases FWHM measurably."""
        params_no = _make_params()
        params_no.resolve()
        out_no = OpticsStage().run(_make_state(wl), params_no)
        fwhm_no = out_no.stage_outputs["optics"]["effective_psf"].fwhm("x")

        params_yes = _make_params()
        params_yes.set("optics.defocus_um", 20.0)
        params_yes.resolve()
        out_yes = OpticsStage().run(_make_state(wl), params_yes)
        fwhm_yes = out_yes.stage_outputs["optics"]["effective_psf"].fwhm("x")

        assert fwhm_yes > fwhm_no


class TestOpticsStageWFE:
    """Tests for WavefrontError threading through OpticsStage."""

    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 50)

    def test_scalar_rms_unchanged(self, wl: np.ndarray) -> None:
        """Default scalar_rms mode should work identically to before."""
        params = _make_params()
        params.set("optics.wfe_rms_waves", 0.05)
        params.resolve()
        out = OpticsStage().run(_make_state(wl), params)
        wfe_out = out.stage_outputs["optics"]["wavefront_error"]
        assert wfe_out.mode == WfeMode.SCALAR_RMS
        assert wfe_out.rms_waves == pytest.approx(0.05, rel=1e-10)

    def test_injected_zernike_wfe(self, wl: np.ndarray) -> None:
        """Injected Zernike WavefrontError should produce a valid ePSF."""
        wfe = WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={4: 0.1, 7: 0.05},
            reference_wavelength_um=0.633,
        )
        state = _make_state(wl)
        state = state.with_stage_output("optics_config", "wavefront_error", wfe)

        out = OpticsStage().run(state, _make_params())

        wfe_stored = out.stage_outputs["optics"]["wavefront_error"]
        assert wfe_stored.mode == WfeMode.ZERNIKE
        epsf = out.stage_outputs["optics"]["effective_psf"]
        assert epsf is not None
        assert float(epsf.data.sum()) == pytest.approx(1.0, rel=1e-6)

    def test_zernike_differs_from_zero_wfe(self, wl: np.ndarray) -> None:
        """Zernike WFE should produce a different PSF than zero WFE."""
        params = _make_params()
        out_zero = OpticsStage().run(_make_state(wl), params)
        epsf_zero = out_zero.stage_outputs["optics"]["effective_psf"]

        wfe = WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={4: 0.2},
            reference_wavelength_um=0.633,
        )
        state = _make_state(wl)
        state = state.with_stage_output("optics_config", "wavefront_error", wfe)
        out_z = OpticsStage().run(state, params)
        epsf_z = out_z.stage_outputs["optics"]["effective_psf"]

        assert not np.allclose(epsf_zero.data, epsf_z.data, atol=1e-10)

    def test_unsupported_wfe_mode_from_params_raises(self, wl: np.ndarray) -> None:
        """Setting wfe_mode='zernike' without injection should raise."""
        params = _make_params()
        params.set("optics.wfe_mode", "zernike")
        params.resolve()
        with pytest.raises(ValueError, match="requires a WavefrontError"):
            OpticsStage().run(_make_state(wl), params)


class TestOpticsStagePerWavelengthPSF:
    """Tests for per-wavelength PSF storage (Gap 16)."""

    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 50)

    def test_per_wavelength_stored(self, wl: np.ndarray) -> None:
        """When psf_n_wavelengths > 1, per_wavelength_psfs should be stored."""
        params = _make_params()
        params.set("optics.psf_n_wavelengths", 3)
        params.resolve()
        out = OpticsStage().run(_make_state(wl), params)

        per_wl = out.stage_outputs["optics"].get("per_wavelength_psfs")
        assert per_wl is not None
        assert len(per_wl) == 3
        for wl_key, epsf_mono in per_wl.items():
            assert isinstance(epsf_mono, EffectivePSF)
            assert float(epsf_mono.data.sum()) == pytest.approx(1.0, rel=1e-4)

    def test_per_wavelength_not_stored_mono(self, wl: np.ndarray) -> None:
        """When psf_n_wavelengths <= 1, per_wavelength_psfs should NOT be stored."""
        params = _make_params()
        out = OpticsStage().run(_make_state(wl), params)
        assert "per_wavelength_psfs" not in out.stage_outputs.get("optics", {})


class TestOpticsStageFieldDependent:
    """Tests for field-dependent WFE (Gap 25)."""

    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 50)

    def _inject_field_wfe(
        self,
        state: ChainState,
        field_table: tuple[FieldWfeSample, ...],
        optical_type: ElementTransferMode = ElementTransferMode.REFLECTIVE,
        ref_wl_um: float = 0.633,
    ) -> ChainState:
        """Inject a field-dependent WavefrontError into optics_config."""
        wfe = WavefrontError(
            mode=WfeMode.FIELD_DEPENDENT,
            field_table=field_table,
            optical_type=optical_type,
            reference_wavelength_um=ref_wl_um,
        )
        return state.with_stage_output("optics_config", "wavefront_error", wfe)

    def test_reflective_on_axis(self, wl: np.ndarray) -> None:
        """Reflective field-dependent, on-axis evaluation."""
        table = (
            FieldWfeSample(0.0, 0.0, zernike_coeffs={4: 0.05}),
            FieldWfeSample(0.5, 0.0, zernike_coeffs={4: 0.15}),
        )
        state = self._inject_field_wfe(_make_state(wl), table)
        params = _make_params()
        params.set("optics.wfe_mode", "field_dependent")
        params.resolve()

        out = OpticsStage().run(state, params)

        # Verify field sample stored.
        assert out.stage_outputs["optics"]["field_position_deg"] == (0.0, 0.0)
        sample = out.stage_outputs["optics"]["field_sample"]
        assert sample.zernike_coeffs == {4: 0.05}

        # PSF should be valid.
        epsf = out.stage_outputs["optics"]["effective_psf"]
        assert epsf is not None
        assert float(epsf.data.sum()) == pytest.approx(1.0, rel=1e-4)

    def test_reflective_off_axis_worse_strehl(self, wl: np.ndarray) -> None:
        """Off-axis (larger WFE) produces worse Strehl than on-axis."""
        table = (
            FieldWfeSample(0.0, 0.0, zernike_coeffs={4: 0.02}),
            FieldWfeSample(0.5, 0.0, zernike_coeffs={4: 0.15, 7: 0.10}),
        )

        # On-axis
        state_on = self._inject_field_wfe(_make_state(wl), table)
        params_on = _make_params()
        params_on.set("optics.wfe_mode", "field_dependent")
        params_on.resolve()
        out_on = OpticsStage().run(state_on, params_on)
        peak_on = out_on.stage_outputs["optics"]["effective_psf"].data.max()

        # Off-axis
        state_off = self._inject_field_wfe(_make_state(wl), table)
        params_off = _make_params()
        params_off.set("optics.wfe_mode", "field_dependent")
        params_off.set("optics.field_position_x", 0.5)
        params_off.resolve()
        out_off = OpticsStage().run(state_off, params_off)
        peak_off = out_off.stage_outputs["optics"]["effective_psf"].data.max()

        # Off-axis with larger WFE → lower peak (worse Strehl).
        assert peak_off < peak_on

    def test_default_field_position_is_on_axis(self, wl: np.ndarray) -> None:
        """Default field_position = (0,0)."""
        table = (
            FieldWfeSample(0.0, 0.0, zernike_coeffs={4: 0.05}),
        )
        state = self._inject_field_wfe(_make_state(wl), table)
        params = _make_params()
        params.set("optics.wfe_mode", "field_dependent")
        params.resolve()

        out = OpticsStage().run(state, params)
        assert out.stage_outputs["optics"]["field_position_deg"] == (0.0, 0.0)

    def test_field_position_not_found_raises(self, wl: np.ndarray) -> None:
        """Requesting non-tabulated field position raises ValueError."""
        table = (
            FieldWfeSample(0.0, 0.0, zernike_coeffs={4: 0.05}),
        )
        state = self._inject_field_wfe(_make_state(wl), table)
        params = _make_params()
        params.set("optics.wfe_mode", "field_dependent")
        params.set("optics.field_position_x", 0.3)
        params.resolve()

        with pytest.raises(ValueError, match="No field sample"):
            OpticsStage().run(state, params)

    def test_refractive_chromatic_psf(self, wl: np.ndarray) -> None:
        """Refractive system with chromatic Zernikes produces valid PSF."""
        table = (
            FieldWfeSample(
                0.0, 0.0,
                zernike_coeffs={4: 0.10},
                chromatic_zernikes={
                    3.5: {4: 0.15},
                    4.25: {4: 0.10},
                    5.0: {4: 0.06},
                },
            ),
        )
        state = self._inject_field_wfe(
            _make_state(wl), table,
            optical_type=ElementTransferMode.REFRACTIVE,
        )
        params = _make_params()
        params.set("optics.wfe_mode", "field_dependent")
        params.set("optics.psf_n_wavelengths", 3)
        params.resolve()

        out = OpticsStage().run(state, params)
        epsf = out.stage_outputs["optics"]["effective_psf"]
        assert epsf is not None
        assert float(epsf.data.sum()) == pytest.approx(1.0, rel=1e-4)

    def test_refractive_chromatic_differs_from_reflective(self, wl: np.ndarray) -> None:
        """Refractive (varying Zernikes per λ) differs from reflective (same)."""
        # Reflective: same Z4=0.10 at all wavelengths.
        table_refl = (
            FieldWfeSample(0.0, 0.0, zernike_coeffs={4: 0.10}),
        )
        state_refl = self._inject_field_wfe(_make_state(wl), table_refl)
        params_refl = _make_params()
        params_refl.set("optics.wfe_mode", "field_dependent")
        params_refl.set("optics.psf_n_wavelengths", 3)
        params_refl.resolve()
        out_refl = OpticsStage().run(state_refl, params_refl)
        epsf_refl = out_refl.stage_outputs["optics"]["effective_psf"]

        # Refractive: defocus varies strongly with λ (chromatic aberration).
        table_refr = (
            FieldWfeSample(
                0.0, 0.0,
                zernike_coeffs={4: 0.10},
                chromatic_zernikes={
                    3.5: {4: 0.20},
                    4.25: {4: 0.10},
                    5.0: {4: 0.02},
                },
            ),
        )
        state_refr = self._inject_field_wfe(
            _make_state(wl), table_refr,
            optical_type=ElementTransferMode.REFRACTIVE,
        )
        params_refr = _make_params()
        params_refr.set("optics.wfe_mode", "field_dependent")
        params_refr.set("optics.psf_n_wavelengths", 3)
        params_refr.resolve()
        out_refr = OpticsStage().run(state_refr, params_refr)
        epsf_refr = out_refr.stage_outputs["optics"]["effective_psf"]

        # PSFs should differ since chromatic vs achromatic WFE.
        assert not np.allclose(epsf_refl.data, epsf_refr.data, atol=1e-6)
