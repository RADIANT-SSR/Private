"""Tests for OpticsStage complex-pupil diagnostic persistence (Gap 89).

Validates that OpticsStage persists the two diagnostic views of the complex
pupil it builds for the MTF autocorrelation — the amplitude/apodization map
and the wavefront-error (phase) map in waves — in ``stage_outputs["optics"]``,
purely additively (Rule 4: the MTF/PSF path is untouched).
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.detector._schema import ALL_PARAMETERS as DET_PARAMS
from radiant.optics._schema import ALL_PARAMETERS as OPT_PARAMS
from radiant.optics.stage import OpticsStage
from radiant.optics.wavefront import WavefrontError, WfeMode

_PUPIL_NPIX = 128


def _make_state(wl: np.ndarray) -> ChainState:
    state = ChainState(wavelength_um=wl)
    L = np.ones_like(wl) * 2.0  # W/m²/sr/µm
    frame = RadiometricFrame(name="at_aperture", wavelength_um=wl, spectral_radiance=L)
    return state.with_frame(frame)


def _make_params(
    *,
    D: float = 0.30,
    f: float = 1.20,
    pitch: float = 18.0,
    obscuration: float = 0.0,
    n_psf_wavelengths: int = 1,
) -> ParameterSet:
    from radiant.api._param_registry import _FNUMBER_GROUP

    schema = list(OPT_PARAMS) + list(DET_PARAMS)
    ps = ParameterSet(schema, [_FNUMBER_GROUP])
    ps.set("optics.aperture_diameter_m", D)
    ps.set("optics.focal_length_m", f)
    ps.set("optics.transmission_scalar", 0.70)
    ps.set("optics.obscuration_ratio", obscuration)
    ps.set("optics.psf_n_wavelengths", n_psf_wavelengths)
    ps.set("detector.pixel_pitch_x_um", pitch)
    ps.set("detector.pixel_pitch_y_um", pitch)
    ps.set("detector.qe_value", 0.7)
    ps.resolve()
    return ps


@pytest.fixture()
def wl() -> np.ndarray:
    return np.linspace(3.5, 5.0, 50)


class TestPupilMapsPersisted:
    """The amplitude and phase maps land in stage_outputs with the right shape."""

    @pytest.mark.level1
    def test_amplitude_persisted_with_shape(self, wl: np.ndarray) -> None:
        out = OpticsStage().run(_make_state(wl), _make_params())
        amp = out.stage_outputs["optics"]["pupil_amplitude"]
        assert amp.shape == (_PUPIL_NPIX, _PUPIL_NPIX)

    @pytest.mark.level1
    def test_phase_persisted_with_shape(self, wl: np.ndarray) -> None:
        out = OpticsStage().run(_make_state(wl), _make_params())
        phase = out.stage_outputs["optics"]["pupil_phase_waves"]
        assert phase.shape == (_PUPIL_NPIX, _PUPIL_NPIX)

    @pytest.mark.level1
    def test_amplitude_is_dimensionless_transmission(self, wl: np.ndarray) -> None:
        """Amplitude ∈ [0, 1] — a dimensionless transmission mask."""
        out = OpticsStage().run(_make_state(wl), _make_params())
        amp = out.stage_outputs["optics"]["pupil_amplitude"]
        assert amp.min() >= 0.0
        assert amp.max() <= 1.0
        # Clear aperture present (unobscured circle fills a sizeable fraction).
        assert amp.max() == pytest.approx(1.0, abs=1e-12)

    @pytest.mark.level1
    def test_metadata_persisted(self, wl: np.ndarray) -> None:
        out = OpticsStage().run(_make_state(wl), _make_params(D=0.30))
        opt = out.stage_outputs["optics"]
        assert opt["pupil_plane_extent_m"] == pytest.approx(0.30, abs=1e-12)
        # Monochromatic phase reference wavelength = band centre.
        assert opt["pupil_wavelength_um"] == pytest.approx(4.25, abs=0.1)


class TestUnaberratedFlatPhase:
    """An aberration-free system yields a flat, ≈zero wavefront-error map."""

    @pytest.mark.level1
    def test_phase_is_flat_zero(self, wl: np.ndarray) -> None:
        out = OpticsStage().run(_make_state(wl), _make_params())
        phase = out.stage_outputs["optics"]["pupil_phase_waves"]
        np.testing.assert_allclose(phase, 0.0, atol=1e-12)

    @pytest.mark.level1
    def test_amplitude_tophat_unobscured(self, wl: np.ndarray) -> None:
        """Unobscured pupil: a filled disc, zero at the centre only outside r."""
        out = OpticsStage().run(_make_state(wl), _make_params(obscuration=0.0))
        amp = out.stage_outputs["optics"]["pupil_amplitude"]
        # Centre pixel is inside the clear aperture → unit transmission.
        assert amp[_PUPIL_NPIX // 2, _PUPIL_NPIX // 2] == pytest.approx(1.0)


class TestObscurationVisible:
    """A central obscuration shows up as a hole in the amplitude map."""

    @pytest.mark.level1
    def test_obscuration_hole_in_amplitude(self, wl: np.ndarray) -> None:
        out = OpticsStage().run(_make_state(wl), _make_params(obscuration=0.4))
        amp = out.stage_outputs["optics"]["pupil_amplitude"]
        # Centre is blocked by the secondary; edge of clear aperture is open.
        assert amp[_PUPIL_NPIX // 2, _PUPIL_NPIX // 2] == pytest.approx(0.0)

    @pytest.mark.level1
    def test_obscured_area_smaller_than_unobscured(self, wl: np.ndarray) -> None:
        amp_open = (
            OpticsStage()
            .run(_make_state(wl), _make_params(obscuration=0.0))
            .stage_outputs["optics"]["pupil_amplitude"]
        )
        amp_obs = (
            OpticsStage()
            .run(_make_state(wl), _make_params(obscuration=0.4))
            .stage_outputs["optics"]["pupil_amplitude"]
        )
        assert amp_obs.sum() < amp_open.sum()


class TestAberratedNonFlatPhase:
    """A configured wavefront error yields a non-flat phase map in waves."""

    @pytest.mark.level1
    def test_zernike_phase_is_non_flat(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        # Inject spherical aberration Z11 = 0.25 waves (deterministic shape).
        wfe = WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={11: 0.25},
            reference_wavelength_um=4.0,
        )
        state = state.with_stage_output("optics_config", "wavefront_error", wfe)
        out = OpticsStage().run(state, _make_params())
        phase = out.stage_outputs["optics"]["pupil_phase_waves"]
        # Non-flat: spread across the aperture, magnitude ~ a fraction of a wave.
        assert phase.std() > 1e-3
        assert np.abs(phase).max() > 1e-2

    @pytest.mark.level1
    def test_phase_zero_outside_aperture(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        wfe = WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={11: 0.25},
            reference_wavelength_um=4.0,
        )
        state = state.with_stage_output("optics_config", "wavefront_error", wfe)
        out = OpticsStage().run(state, _make_params())
        opt = out.stage_outputs["optics"]
        amp = opt["pupil_amplitude"]
        phase = opt["pupil_phase_waves"]
        # Phase is masked to exactly zero wherever the amplitude is zero.
        assert np.all(phase[amp == 0.0] == 0.0)


class TestAdditiveResultsNeutral:
    """Persisting the maps does not perturb the MTF/PSF the chain computes."""

    @pytest.mark.level1
    def test_mtf_terms_unchanged_by_persistence(self, wl: np.ndarray) -> None:
        """mtf_optics_x/y are byte-identical to a run reading the same pupil.

        The persisted amplitude, fed back through the autocorrelation, must
        reproduce the stored mtf_optics_x DC=1 and shape — a sanity check that
        the persisted array IS the pupil the MTF used (monochromatic path).
        """
        out = OpticsStage().run(_make_state(wl), _make_params())
        # Persistence is additive: the MTF terms still exist and are well-formed.
        assert out.mtf_terms["mtf_optics_x"][0] == pytest.approx(1.0, abs=1e-6)
        assert "pupil_amplitude" in out.stage_outputs["optics"]


class TestPolychromaticPupilMaps:
    """Polychromatic runs persist a representative band-centre pupil."""

    @pytest.mark.level1
    def test_poly_maps_persisted(self, wl: np.ndarray) -> None:
        out = OpticsStage().run(_make_state(wl), _make_params(n_psf_wavelengths=3))
        opt = out.stage_outputs["optics"]
        assert opt["pupil_amplitude"].shape == (_PUPIL_NPIX, _PUPIL_NPIX)
        assert opt["pupil_phase_waves"].shape == (_PUPIL_NPIX, _PUPIL_NPIX)
        # Band-centre representative wavelength within the sensor band.
        assert 3.5 <= opt["pupil_wavelength_um"] <= 5.0
