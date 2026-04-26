"""Tests for OpticsStage MTF product path — mtf_optics_x/y terms.

Validates that OpticsStage computes optical MTF via pupil autocorrelation
and stores both x and y terms in ChainState.mtf_terms, along with the
shared spatial frequency grid.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.detector._schema import ALL_PARAMETERS as DET_PARAMS
from radiant.optics._schema import ALL_PARAMETERS as OPT_PARAMS
from radiant.optics.psf.effective import EffectivePSF
from radiant.optics.stage import OpticsStage
from radiant.optics.wavefront import WavefrontError, WfeMode


def _make_state(wl: np.ndarray) -> ChainState:
    state = ChainState(wavelength_um=wl)
    L = np.ones_like(wl) * 2.0  # W/m²/sr/µm
    frame = RadiometricFrame(
        name="at_aperture",
        wavelength_um=wl,
        spectral_radiance=L,
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


@pytest.fixture()
def wl() -> np.ndarray:
    return np.linspace(3.5, 5.0, 50)


class TestOpticsStageProducesMTFTerms:
    """Verify OpticsStage populates mtf_optics_x/y and spatial_freq."""

    @pytest.mark.level1
    def test_mtf_optics_x_exists(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        out = OpticsStage().run(state, _make_params())
        assert "mtf_optics_x" in out.mtf_terms

    @pytest.mark.level1
    def test_mtf_optics_y_exists(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        out = OpticsStage().run(state, _make_params())
        assert "mtf_optics_y" in out.mtf_terms

    @pytest.mark.level1
    def test_spatial_freq_populated(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        out = OpticsStage().run(state, _make_params())
        assert out.spatial_freq_cycles_per_mrad is not None
        assert len(out.spatial_freq_cycles_per_mrad) > 0

    @pytest.mark.level1
    def test_mtf_and_freq_same_length(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        out = OpticsStage().run(state, _make_params())
        n_freq = len(out.spatial_freq_cycles_per_mrad)
        assert len(out.mtf_terms["mtf_optics_x"]) == n_freq
        assert len(out.mtf_terms["mtf_optics_y"]) == n_freq

    @pytest.mark.level1
    def test_dc_is_unity(self, wl: np.ndarray) -> None:
        """MTF(0) = 1.0 for both axes."""
        state = _make_state(wl)
        out = OpticsStage().run(state, _make_params())
        assert out.mtf_terms["mtf_optics_x"][0] == pytest.approx(1.0, abs=1e-6)
        assert out.mtf_terms["mtf_optics_y"][0] == pytest.approx(1.0, abs=1e-6)

    @pytest.mark.level1
    def test_mtf_non_negative(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        out = OpticsStage().run(state, _make_params())
        assert np.all(out.mtf_terms["mtf_optics_x"] >= 0.0)
        assert np.all(out.mtf_terms["mtf_optics_y"] >= 0.0)

    @pytest.mark.level1
    def test_freq_monotonically_increasing(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        out = OpticsStage().run(state, _make_params())
        freq = out.spatial_freq_cycles_per_mrad
        assert np.all(np.diff(freq) > 0)


class TestCrossPathConsistency:
    """Verify mtf_optics × pixel_aperture_sinc ≈ FFT(ePSF).

    The ePSF now includes the pixel aperture kernel (§6 step 1), so the
    comparison must multiply mtf_optics by the analytic pixel aperture
    sinc to match the ePSF FFT.  The pixel aperture MTF term itself is
    stored later by DetectorStage (not duplicated here to avoid
    double-counting in the system MTF product).
    """

    @staticmethod
    def _pixel_sinc_mtf(
        freq_m: np.ndarray,
        pixel_pitch_m: float,
    ) -> np.ndarray:
        """Pixel aperture MTF = |sinc(f * pitch)|."""
        return np.abs(np.sinc(freq_m * pixel_pitch_m))

    @pytest.mark.level1
    def test_mono_cross_check_x(self, wl: np.ndarray) -> None:
        """mtf_optics_x × pixel_sinc vs ePSF FFT, x axis."""
        state = _make_state(wl)
        params = _make_params()
        out = OpticsStage().run(state, params)

        epsf: EffectivePSF = out.stage_outputs["optics"]["effective_psf"]
        focal_length_m: float = params.get("optics.focal_length_m")
        pixel_pitch_m: float = params.get("detector.pixel_pitch_x_um")

        freq_psf_m, mtf_psf_x = epsf.mtf_1d("x")
        freq_psf_mrad = freq_psf_m * focal_length_m * 1e3

        freq_prod = out.spatial_freq_cycles_per_mrad
        mtf_prod_x = out.mtf_terms["mtf_optics_x"]
        mtf_prod_interp = np.interp(freq_psf_mrad, freq_prod, mtf_prod_x, right=0.0)

        # Include pixel aperture sinc (convolved into ePSF but not in mtf_optics).
        mtf_pixel = self._pixel_sinc_mtf(freq_psf_m, pixel_pitch_m)
        mtf_combined = mtf_prod_interp * mtf_pixel

        # Tolerance is 2e-2 because the spatial rect kernel on a discrete grid
        # does not exactly reproduce the analytic sinc MTF.
        n_compare = len(freq_psf_mrad) // 2
        np.testing.assert_allclose(
            mtf_combined[:n_compare],
            mtf_psf_x[:n_compare],
            atol=2e-2,
        )

    @pytest.mark.level1
    def test_mono_cross_check_y(self, wl: np.ndarray) -> None:
        """mtf_optics_y × pixel_sinc vs ePSF FFT, y axis."""
        state = _make_state(wl)
        params = _make_params()
        out = OpticsStage().run(state, params)

        epsf: EffectivePSF = out.stage_outputs["optics"]["effective_psf"]
        focal_length_m: float = params.get("optics.focal_length_m")
        pixel_pitch_m: float = params.get("detector.pixel_pitch_y_um")

        freq_psf_m, mtf_psf_y = epsf.mtf_1d("y")
        freq_psf_mrad = freq_psf_m * focal_length_m * 1e3

        freq_prod = out.spatial_freq_cycles_per_mrad
        mtf_prod_y = out.mtf_terms["mtf_optics_y"]
        mtf_prod_interp = np.interp(freq_psf_mrad, freq_prod, mtf_prod_y, right=0.0)

        mtf_pixel = self._pixel_sinc_mtf(freq_psf_m, pixel_pitch_m)
        mtf_combined = mtf_prod_interp * mtf_pixel

        n_compare = len(freq_psf_mrad) // 2
        np.testing.assert_allclose(
            mtf_combined[:n_compare],
            mtf_psf_y[:n_compare],
            atol=2e-2,
        )


class TestAsymmetricWFE:
    """With coma (asymmetric WFE), mtf_optics_x ≠ mtf_optics_y."""

    @pytest.mark.level1
    def test_coma_breaks_symmetry(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        params = _make_params()

        # Inject Zernike WFE: coma Z7 = 0.2 waves (asymmetric).
        wfe = WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={7: 0.2},
            reference_wavelength_um=4.0,
        )
        # Inject via optics_config.
        state = state.with_stage_output("optics_config", "wavefront_error", wfe)

        out = OpticsStage().run(state, params)

        mtf_x = out.mtf_terms["mtf_optics_x"]
        mtf_y = out.mtf_terms["mtf_optics_y"]

        # At non-zero frequencies, coma makes x and y differ.
        n = min(len(mtf_x), 20)
        # Skip DC (always 1.0) and check that x/y are not identical.
        assert not np.allclose(mtf_x[1:n], mtf_y[1:n], atol=1e-4)
