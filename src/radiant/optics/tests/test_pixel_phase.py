"""Pixel sampling phase (straddle factor) — Gap 129.

Level 0/1 tests for ``optics/pixel_phase.py`` and
``EffectivePSF.ensquared_energy_nxn(phase_mode=...)`` /
``pixel_block_energy_at``. Anchors: the Q=2 unaberrated Airy whose
pixel-centred 1×1 ensquared energy is 0.177327 (Track A2 §8, adaptive 2-D
quadrature independent of RADIANT); every other check is an identity
between two *definitions* (explicit phase average vs box integral) or an
ordering the physics fixes (corner < edge < centred for a symmetric PSF).
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.optics.errors import OpticsValidationError
from radiant.optics.pixel_kernel import make_pixel_aperture_kernel_2d
from radiant.optics.pixel_phase import PIXEL_PHASE_MODES, resolve_pixel_phase
from radiant.optics.psf.builder import build_effective_psf
from radiant.optics.psf.effective import EffectivePSF
from radiant.optics.psf_mono import compute_psf
from radiant.optics.sampling import compute_sampling

# Q = 2 unaberrated Airy: λ = 4 µm, f = 1.2 m, D = 0.30 m (F# = 4), p = 8 µm.
_WL_M = 4.0e-6
_F_M = 1.2
_D_M = 0.30
_PITCH_M = 8.0e-6
_EE_CENTRED_ANALYTIC = 0.177327  # Track A2 §8d


def _optics_only(pitch_m: float = _PITCH_M) -> EffectivePSF:
    config = compute_sampling(
        wavelength_m=_WL_M,
        focal_length_m=_F_M,
        aperture_diameter_m=_D_M,
        pixel_pitch_m=pitch_m,
        pupil_npix=128,
        psf_oversample=8,
    )
    return build_effective_psf(
        compute_psf(config),
        kernels=[],
        sample_spacing_m=config.focal_spacing_m,
        pixel_pitch_m=pitch_m,
        wavelength_um=_WL_M * 1e6,
    )


def _with_pixel(opt: EffectivePSF, fill_factor: float = 1.0) -> EffectivePSF:
    n = opt.data.shape[0]
    n_k = n if n % 2 else n - 1
    kernel = make_pixel_aperture_kernel_2d(
        n_k, opt.sample_spacing_m, opt.pixel_pitch_m, opt.pixel_pitch_m, fill_factor
    )
    return opt.with_kernel("pixel_aperture", kernel)


@pytest.fixture(scope="module")
def optics_only() -> EffectivePSF:
    return _optics_only()


@pytest.fixture(scope="module")
def pixel_conv(optics_only: EffectivePSF) -> EffectivePSF:
    return _with_pixel(optics_only)


def _box_at_offset(opt: EffectivePSF, dx_pix: float, dy_pix: float) -> float:
    """Explicit pitch-wide box on the optics-only PSF, displaced by (dx, dy) pitches."""
    n = opt.data.shape[0]
    c = n // 2
    spp = opt.pixel_pitch_m / opt.sample_spacing_m
    half = spp / 2.0
    idx = np.arange(n)
    wx = np.clip(half - np.abs(idx - c - dx_pix * spp) + 0.5, 0.0, 1.0)
    wy = np.clip(half - np.abs(idx - c - dy_pix * spp) + 0.5, 0.0, 1.0)
    return float(np.einsum("i,j,ij->", wy, wx, opt.data))


class TestResolvePixelPhase:
    @pytest.mark.level0
    def test_modes(self) -> None:
        assert resolve_pixel_phase("average") is None
        assert resolve_pixel_phase("centered") == (0.0, 0.0)
        assert resolve_pixel_phase("worst_case") == (0.5, 0.5)
        assert resolve_pixel_phase("specified", 0.25, -0.1) == (0.25, -0.1)
        assert PIXEL_PHASE_MODES == ("average", "centered", "worst_case", "specified")

    @pytest.mark.level0
    def test_specified_ignores_offsets_in_other_modes(self) -> None:
        assert resolve_pixel_phase("centered", 0.4, 0.4) == (0.0, 0.0)

    @pytest.mark.level0
    def test_bad_mode_raises(self) -> None:
        with pytest.raises(OpticsValidationError, match="Unknown pixel_phase_mode"):
            resolve_pixel_phase("corner")

    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [0.51, -0.6])
    def test_specified_out_of_range_raises(self, bad: float) -> None:
        with pytest.raises(OpticsValidationError, match="outside"):
            resolve_pixel_phase("specified", bad, 0.0)


class TestPixelBlockEnergyAt:
    @pytest.mark.level0
    def test_centred_matches_analytic_anchor(self, pixel_conv: EffectivePSF) -> None:
        """Chain-level anchor: the pixel-convolved PSF evaluated at (0,0) is the
        Track A2 centred EE (0.177327) — the identity EE(δ) = data(δ)·(p/Δ)²."""
        ee = pixel_conv.ensquared_energy_nxn(1, phase_mode="centered")
        assert ee == pytest.approx(_EE_CENTRED_ANALYTIC, abs=1e-3)

    @pytest.mark.level0
    def test_average_equals_explicit_phase_average(
        self, optics_only: EffectivePSF, pixel_conv: EffectivePSF
    ) -> None:
        """The shipped box integral of the pixel-convolved PSF is the expectation
        over a source uniformly placed across one pitch (rect ⊛ rect = triangle)."""
        offs = np.linspace(-0.5, 0.5, 33)
        grid = [[_box_at_offset(optics_only, ox, oy) for ox in offs] for oy in offs]
        explicit = float(np.mean(grid))
        plain_box = pixel_conv.ensquared_energy_nxn(1)
        assert plain_box == pytest.approx(explicit, abs=5e-4)
        assert pixel_conv.ensquared_energy_nxn(1, phase_mode="average") == plain_box

    @pytest.mark.level0
    def test_point_evaluation_matches_explicit_box_at_phase(
        self, optics_only: EffectivePSF, pixel_conv: EffectivePSF
    ) -> None:
        for dx, dy in ((0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.25, -0.125)):
            expected = _box_at_offset(optics_only, dx, dy)
            got = pixel_conv.pixel_block_energy_at(1, dx, dy)
            assert got == pytest.approx(expected, abs=5e-4), (dx, dy)

    @pytest.mark.level0
    def test_ordering_corner_edge_centred_average(self, pixel_conv: EffectivePSF) -> None:
        centred = pixel_conv.ensquared_energy_nxn(1, phase_mode="centered")
        average = pixel_conv.ensquared_energy_nxn(1, phase_mode="average")
        edge = pixel_conv.ensquared_energy_nxn(1, phase_mode="specified", phase=(0.5, 0.0))
        corner = pixel_conv.ensquared_energy_nxn(1, phase_mode="worst_case")
        assert corner < edge < average < centred
        # Q=2 magnitudes from the Gap 129 investigation (regression pins, abs 2e-3).
        assert average == pytest.approx(0.1606, abs=2e-3)
        assert edge == pytest.approx(0.1532, abs=2e-3)
        assert corner == pytest.approx(0.1321, abs=2e-3)

    @pytest.mark.level0
    def test_specified_reproduces_named_modes(self, pixel_conv: EffectivePSF) -> None:
        assert pixel_conv.ensquared_energy_nxn(
            1, phase_mode="specified", phase=(0.0, 0.0)
        ) == pixel_conv.ensquared_energy_nxn(1, phase_mode="centered")
        assert pixel_conv.ensquared_energy_nxn(
            1, phase_mode="specified", phase=(0.5, 0.5)
        ) == pixel_conv.ensquared_energy_nxn(1, phase_mode="worst_case")

    @pytest.mark.level0
    def test_symmetric_psf_even_in_phase(self, pixel_conv: EffectivePSF) -> None:
        plus = pixel_conv.pixel_block_energy_at(1, 0.3, -0.2)
        minus = pixel_conv.pixel_block_energy_at(1, -0.3, 0.2)
        assert plus == pytest.approx(minus, rel=1e-6)

    @pytest.mark.level0
    def test_3x3_average_matches_box_and_exceeds_1x1(self, pixel_conv: EffectivePSF) -> None:
        avg3 = pixel_conv.ensquared_energy_nxn(3, phase_mode="average")
        cen3 = pixel_conv.ensquared_energy_nxn(3, phase_mode="centered")
        wc3 = pixel_conv.ensquared_energy_nxn(3, phase_mode="worst_case")
        assert avg3 == pytest.approx(pixel_conv.ensquared_energy(1.5 * _PITCH_M), rel=1e-12)
        assert wc3 < avg3 < cen3
        assert cen3 > pixel_conv.ensquared_energy_nxn(1, phase_mode="centered")
        # A 3×3 block at Q=2 captures most of the Airy core+first ring.
        assert 0.6 < wc3 < cen3 < 1.0

    @pytest.mark.level0
    def test_fill_factor_normalises_to_the_pitch_box(self, optics_only: EffectivePSF) -> None:
        """With FF < 1 the identity still returns the *pitch*-box value; the fill
        factor multiplies downstream (CU-074), so FF·EE(δ) is the photosite energy."""
        ff = 0.64
        conv_ff = _with_pixel(optics_only, fill_factor=ff)
        n = optics_only.data.shape[0]
        c = n // 2
        spp = optics_only.pixel_pitch_m / optics_only.sample_spacing_m
        half_w = np.sqrt(ff) * spp / 2.0
        idx = np.arange(n)
        w = np.clip(half_w - np.abs(idx - c) + 0.5, 0.0, 1.0)
        photosite_centred = float(np.einsum("i,j,ij->", w, w, optics_only.data))
        ee = conv_ff.pixel_block_energy_at(1, 0.0, 0.0)
        assert ee * ff == pytest.approx(photosite_centred, abs=1e-3)

    @pytest.mark.level0
    def test_requires_pixel_kernel(self, optics_only: EffectivePSF) -> None:
        with pytest.raises(OpticsValidationError, match="pixel-aperture kernel"):
            optics_only.pixel_block_energy_at(1, 0.0, 0.0)
        # The average mode needs no such precondition (it is the plain box).
        assert 0.0 < optics_only.ensquared_energy_nxn(1) < 1.0

    @pytest.mark.level0
    def test_bad_n_raises(self, pixel_conv: EffectivePSF) -> None:
        with pytest.raises(OpticsValidationError, match="n_pixels"):
            pixel_conv.pixel_block_energy_at(0, 0.0, 0.0)
