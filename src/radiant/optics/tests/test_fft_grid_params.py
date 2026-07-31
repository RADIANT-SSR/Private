"""Tests for the CU-288 FFT-grid parameters (``optics.pupil_npix`` / ``optics.psf_oversample``).

The two knobs were hardcoded literals in ``optics/stage.py`` (128 / 8); CU-288
promoted them to schema parameters read once in ``_build_effective_psf`` and
threaded to every sampling site — target PSF, reference PSF, and the MTF
product path — so both Rule-4 spatial paths always share one grid.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.detector._schema import ALL_PARAMETERS as DET_PARAMS
from radiant.optics._schema import ALL_PARAMETERS as OPT_PARAMS
from radiant.optics._schema import PSF_OVERSAMPLE, PUPIL_NPIX
from radiant.optics.sampling import compute_sampling
from radiant.optics.stage import OpticsStage


def _make_state(wl: np.ndarray) -> ChainState:
    state = ChainState(wavelength_um=wl)
    L = np.ones_like(wl) * 2.0  # W/m²/sr/µm
    frame = RadiometricFrame(name="at_aperture", wavelength_um=wl, spectral_radiance=L)
    return state.with_frame(frame)


def _make_params(
    *,
    pupil_npix: int | None = None,
    psf_oversample: int | None = None,
) -> ParameterSet:
    from radiant.api._param_registry import _FNUMBER_GROUP

    schema = list(OPT_PARAMS) + list(DET_PARAMS)
    ps = ParameterSet(schema, [_FNUMBER_GROUP])
    ps.set("optics.aperture_diameter_m", 0.30)
    ps.set("optics.focal_length_m", 1.20)
    ps.set("optics.transmission_scalar", 0.70)
    ps.set("optics.obscuration_ratio", 0.0)
    ps.set("detector.pixel_pitch_x_um", 18.0)
    ps.set("detector.pixel_pitch_y_um", 18.0)
    ps.set("detector.qe_value", 0.7)
    if pupil_npix is not None:
        ps.set("optics.pupil_npix", pupil_npix)
    if psf_oversample is not None:
        ps.set("optics.psf_oversample", psf_oversample)
    ps.resolve()
    return ps


@pytest.fixture()
def wl() -> np.ndarray:
    return np.linspace(3.5, 5.0, 50)


class TestSchema:
    """The defaults reproduce the pre-CU-288 hardcoded grid exactly."""

    def test_pupil_npix_default_is_the_old_literal(self) -> None:
        assert PUPIL_NPIX.default == 128
        assert PUPIL_NPIX.dtype is int
        assert PUPIL_NPIX.bounds == (32, 512)

    def test_psf_oversample_default_is_the_old_literal(self) -> None:
        assert PSF_OVERSAMPLE.default == 8
        assert PSF_OVERSAMPLE.dtype is int
        # Floor 4, not compute_sampling's Nyquist floor of 2: oversample ≤ 3
        # can put the padded grid at exactly 2× the pupil width, where the
        # FFT-of-PSF path aliases and the Rule-4 tolerance is breached
        # (measured 0.032 vs 0.02, CU-288).
        assert PSF_OVERSAMPLE.bounds == (4, 16)


class TestStagePlumbing:
    """The stage reads the schema values and threads them to every grid site."""

    def test_default_pupil_grid_is_128(self, wl: np.ndarray) -> None:
        out = OpticsStage().run(_make_state(wl), _make_params())
        assert out.stage_outputs["optics"]["pupil_amplitude"].shape == (128, 128)

    def test_pupil_npix_sets_the_pupil_grid(self, wl: np.ndarray) -> None:
        out = OpticsStage().run(_make_state(wl), _make_params(pupil_npix=64))
        assert out.stage_outputs["optics"]["pupil_amplitude"].shape == (64, 64)

    def test_psf_oversample_sets_the_focal_spacing(self, wl: np.ndarray) -> None:
        """The ePSF sample spacing follows the sampling law for the chosen grid.

        Truth anchor (analytic): Δx_focal = λ·f / (N_padded · Δx_pupil) with
        N_padded the next power of 2 — the RADIANT_Spatial_Complete.md §4
        coupled-sampling constraint, computed here independently via
        ``compute_sampling`` and compared against the grid the stage built.
        """
        out = OpticsStage().run(_make_state(wl), _make_params(pupil_npix=64, psf_oversample=4))
        epsf = out.stage_outputs["optics"]["effective_psf"]
        band_center_m = float(wl[len(wl) // 2]) * 1e-6
        expected = compute_sampling(
            wavelength_m=band_center_m,
            focal_length_m=1.20,
            aperture_diameter_m=0.30,
            pixel_pitch_m=18.0e-6,
            pupil_npix=64,
            psf_oversample=4,
        ).focal_spacing_m
        assert epsf.sample_spacing_m == pytest.approx(expected, rel=1e-12)

    def test_reference_psf_shares_the_grid(self, wl: np.ndarray) -> None:
        """Strehl's reference PSF must live on the same grid as the target PSF."""
        out = OpticsStage().run(_make_state(wl), _make_params(pupil_npix=64, psf_oversample=4))
        epsf = out.stage_outputs["optics"]["effective_psf"]
        ref = out.stage_outputs["optics"]["reference_psf"]
        assert ref.data.shape == epsf.data.shape
        assert ref.sample_spacing_m == pytest.approx(epsf.sample_spacing_m, rel=1e-12)
