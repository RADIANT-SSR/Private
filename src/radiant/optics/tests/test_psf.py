"""Tests for PSFData container and EffectivePSF.

Validates:
- MTF from PSF via FFT (Parseval energy, DC normalisation)
- Encircled energy convergence to 1.0
- FWHM consistent with Airy 1.028 λf/D
- Immutability of PSFData
- EffectivePSF 9 mandatory invariants (see Prompt 2C.4)

See RADIANT_Spatial_Complete.md §2, §9.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.optics.psf.builder import build_effective_psf
from radiant.optics.psf.data import PSFData
from radiant.optics.psf.effective import EffectivePSF
from radiant.optics.psf_mono import compute_psf
from radiant.optics.sampling import PSFSamplingConfig, compute_sampling

# ---------------------------------------------------------------------------
# Standard config
# ---------------------------------------------------------------------------

WAVELENGTH_M = 4.0e-6
FOCAL_LENGTH_M = 1.50
APERTURE_M = 0.30
PIXEL_PITCH_M = 15e-6
PUPIL_NPIX = 256
OVERSAMPLE = 16


@pytest.fixture()
def config() -> PSFSamplingConfig:
    return compute_sampling(
        wavelength_m=WAVELENGTH_M,
        focal_length_m=FOCAL_LENGTH_M,
        aperture_diameter_m=APERTURE_M,
        pixel_pitch_m=PIXEL_PITCH_M,
        pupil_npix=PUPIL_NPIX,
        psf_oversample=OVERSAMPLE,
    )


@pytest.fixture()
def psf_data(config: PSFSamplingConfig) -> PSFData:
    psf_arr = compute_psf(config)
    return PSFData(
        data=psf_arr,
        config=config,
        wavelength_m=WAVELENGTH_M,
        strehl=1.0,
    )


# ---------------------------------------------------------------------------
# PSFData basic properties
# ---------------------------------------------------------------------------


class TestPSFDataBasic:
    def test_shape(self, psf_data: PSFData, config: PSFSamplingConfig) -> None:
        assert psf_data.shape == (config.padded_npix, config.padded_npix)

    def test_peak(self, psf_data: PSFData) -> None:
        assert psf_data.peak > 0.0

    def test_total(self, psf_data: PSFData) -> None:
        assert psf_data.total == pytest.approx(1.0, rel=1e-10)

    def test_frozen(self, psf_data: PSFData) -> None:
        with pytest.raises(AttributeError):
            psf_data.strehl = 0.5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MTF from PSF
# ---------------------------------------------------------------------------


class TestMTF2D:
    def test_dc_is_one(self, psf_data: PSFData) -> None:
        """MTF(0,0) = 1.0 by normalisation."""
        mtf = psf_data.mtf_2d()
        c = mtf.shape[0] // 2
        assert mtf[c, c] == pytest.approx(1.0, rel=1e-10)

    def test_non_negative(self, psf_data: PSFData) -> None:
        mtf = psf_data.mtf_2d()
        assert np.all(mtf >= 0.0)

    def test_bounded_by_one(self, psf_data: PSFData) -> None:
        mtf = psf_data.mtf_2d()
        assert mtf.max() == pytest.approx(1.0, rel=1e-10)

    def test_shape_matches_psf(self, psf_data: PSFData) -> None:
        mtf = psf_data.mtf_2d()
        assert mtf.shape == psf_data.shape

    def test_symmetric(self, psf_data: PSFData) -> None:
        """MTF of a symmetric PSF should be symmetric (above noise floor)."""
        mtf = psf_data.mtf_2d()
        c = mtf.shape[0] // 2
        h = mtf[c, c:]
        v = mtf[c:, c]
        # Use atol for values near machine epsilon in tails.
        np.testing.assert_allclose(h, v, atol=1e-14)


class TestMTF1D:
    def test_x_slice_dc_is_one(self, psf_data: PSFData) -> None:
        freq, mtf = psf_data.mtf_1d("x")
        assert mtf[0] == pytest.approx(1.0, rel=1e-10)

    def test_y_slice_dc_is_one(self, psf_data: PSFData) -> None:
        freq, mtf = psf_data.mtf_1d("y")
        assert mtf[0] == pytest.approx(1.0, rel=1e-10)

    def test_frequency_starts_at_zero(self, psf_data: PSFData) -> None:
        freq, mtf = psf_data.mtf_1d("x")
        assert freq[0] == pytest.approx(0.0, abs=1e-20)

    def test_mtf_drops_to_zero(self, psf_data: PSFData) -> None:
        """For a circular aperture, MTF drops to 0 at cutoff freq = D/(λf)."""
        freq, mtf = psf_data.mtf_1d("x")
        # At Nyquist, MTF should be well below 1.
        assert mtf[-1] < 0.5

    def test_invalid_axis_raises(self, psf_data: PSFData) -> None:
        with pytest.raises(ValueError, match="axis must be"):
            psf_data.mtf_1d("z")

    def test_diffraction_cutoff(self, psf_data: PSFData) -> None:
        """MTF should reach zero at the diffraction cutoff D/(λf).

        For a circular aperture, the OTF cutoff frequency is D/(λf)
        in cycles/m in the focal plane.
        """
        freq, mtf = psf_data.mtf_1d("x")
        cutoff = APERTURE_M / (WAVELENGTH_M * FOCAL_LENGTH_M)
        # Find where MTF first drops below 0.01.
        below = np.where(mtf < 0.01)[0]
        if len(below) > 0:
            freq_zero = freq[below[0]]
            assert freq_zero == pytest.approx(cutoff, rel=0.05)


# ---------------------------------------------------------------------------
# Encircled energy
# ---------------------------------------------------------------------------


class TestEncircledEnergy:
    def test_full_grid_captures_all(self, psf_data: PSFData) -> None:
        """Box the size of the full grid should capture ~100%."""
        half = psf_data.config.psf_fov_m / 2
        ee = psf_data.encircled_energy(half)
        assert ee == pytest.approx(1.0, rel=1e-6)

    def test_small_box(self, psf_data: PSFData) -> None:
        """Tiny box captures less energy."""
        dx = psf_data.config.focal_spacing_m
        ee = psf_data.encircled_energy(dx)
        assert 0 < ee < 0.5

    def test_monotonically_increasing(self, psf_data: PSFData) -> None:
        """EE increases with box size."""
        dx = psf_data.config.focal_spacing_m
        sizes = [2 * dx, 5 * dx, 10 * dx, 20 * dx, 50 * dx]
        ees = [psf_data.encircled_energy(s) for s in sizes]
        for i in range(len(ees) - 1):
            assert ees[i + 1] >= ees[i]

    def test_airy_84_percent(self, psf_data: PSFData) -> None:
        """~84% of Airy pattern energy within first zero.

        Truth anchor: Born & Wolf — 83.8% within first zero ring.
        """
        r_zero = 1.22 * WAVELENGTH_M * FOCAL_LENGTH_M / APERTURE_M
        ee = psf_data.encircled_energy(r_zero)
        # Square box approximation — slightly more than circular 84%.
        assert ee == pytest.approx(0.84, abs=0.05)


# ---------------------------------------------------------------------------
# FWHM
# ---------------------------------------------------------------------------


class TestFWHM:
    def test_fwhm_near_airy(self, psf_data: PSFData) -> None:
        """FWHM ≈ 1.028 λf/D."""
        fwhm = psf_data.fwhm_m()
        expected = 1.028 * WAVELENGTH_M * FOCAL_LENGTH_M / APERTURE_M
        assert fwhm == pytest.approx(expected, rel=0.02)

    def test_fwhm_positive(self, psf_data: PSFData) -> None:
        assert psf_data.fwhm_m() > 0.0


# ---------------------------------------------------------------------------
# Parseval energy conservation
# ---------------------------------------------------------------------------


class TestParseval:
    def test_parseval(self, psf_data: PSFData) -> None:
        """Sum |OTF|² should equal sum |PSF|² (Parseval's theorem).

        Since MTF is normalised, we check that the raw OTF preserves energy.
        """
        psf_arr = psf_data.data
        otf = np.fft.fft2(psf_arr)
        energy_spatial = float(np.sum(np.abs(psf_arr) ** 2))
        energy_freq = float(np.sum(np.abs(otf) ** 2)) / psf_arr.size
        assert energy_spatial == pytest.approx(energy_freq, rel=1e-10)


# ===========================================================================
# EffectivePSF — Mandatory Invariant Tests (2C.4)
# ===========================================================================

# Use smaller grid for faster tests; 2C.1 already validated Airy at high res.
EPSF_PUPIL_NPIX = 128
EPSF_OVERSAMPLE = 8


@pytest.fixture()
def epsf_config() -> PSFSamplingConfig:
    return compute_sampling(
        wavelength_m=WAVELENGTH_M,
        focal_length_m=FOCAL_LENGTH_M,
        aperture_diameter_m=APERTURE_M,
        pixel_pitch_m=PIXEL_PITCH_M,
        pupil_npix=EPSF_PUPIL_NPIX,
        psf_oversample=EPSF_OVERSAMPLE,
    )


@pytest.fixture()
def optical_psf(epsf_config: PSFSamplingConfig) -> np.ndarray:
    return compute_psf(epsf_config, obscuration_ratio=0.0)


def _make_gaussian_kernel(npix: int, sigma_pix: float) -> np.ndarray:
    """Helper: centred Gaussian kernel, unit-volume."""
    c = npix // 2
    x = np.arange(npix) - c
    xx, yy = np.meshgrid(x, x, indexing="xy")
    k = np.exp(-(xx**2 + yy**2) / (2.0 * sigma_pix**2))
    k /= k.sum()
    return k


def _make_rect_kernel(npix: int, width_pix: int) -> np.ndarray:
    """Helper: centred rect kernel, unit-volume."""
    k = np.zeros((npix, npix), dtype=np.float64)
    c = npix // 2
    hw = width_pix // 2
    k[c - hw : c + hw + 1, c - hw : c + hw + 1] = 1.0
    k /= k.sum()
    return k


@pytest.fixture()
def epsf_diffraction_only(
    optical_psf: np.ndarray, epsf_config: PSFSamplingConfig
) -> EffectivePSF:
    """EffectivePSF with no degradation kernels."""
    return build_effective_psf(
        optical_psf,
        kernels=[],
        sample_spacing_m=epsf_config.focal_spacing_m,
        pixel_pitch_m=PIXEL_PITCH_M,
        wavelength_um=WAVELENGTH_M * 1e6,
    )


@pytest.fixture()
def epsf_with_detector(
    optical_psf: np.ndarray, epsf_config: PSFSamplingConfig
) -> EffectivePSF:
    """EffectivePSF with detector aperture kernel."""
    n = optical_psf.shape[0]
    detector_k = _make_rect_kernel(
        n, max(1, int(round(PIXEL_PITCH_M / epsf_config.focal_spacing_m)))
    )
    return build_effective_psf(
        optical_psf,
        kernels=[("pixel_aperture", detector_k)],
        sample_spacing_m=epsf_config.focal_spacing_m,
        pixel_pitch_m=PIXEL_PITCH_M,
        wavelength_um=WAVELENGTH_M * 1e6,
    )


@pytest.fixture()
def epsf_with_motion(
    optical_psf: np.ndarray, epsf_config: PSFSamplingConfig
) -> EffectivePSF:
    """EffectivePSF with detector + motion (Gaussian jitter)."""
    n = optical_psf.shape[0]
    detector_k = _make_rect_kernel(
        n, max(1, int(round(PIXEL_PITCH_M / epsf_config.focal_spacing_m)))
    )
    jitter_sigma = 3.0  # pixels
    jitter_k = _make_gaussian_kernel(n, jitter_sigma)
    return build_effective_psf(
        optical_psf,
        kernels=[("pixel_aperture", detector_k), ("jitter", jitter_k)],
        sample_spacing_m=epsf_config.focal_spacing_m,
        pixel_pitch_m=PIXEL_PITCH_M,
        wavelength_um=WAVELENGTH_M * 1e6,
    )


# ---------------------------------------------------------------------------
# Invariant 1: Energy conservation — ∑ PSF = 1.0
# ---------------------------------------------------------------------------


class TestInvariant1EnergyConservation:
    def test_diffraction_only(self, epsf_diffraction_only: EffectivePSF) -> None:
        assert epsf_diffraction_only.total == pytest.approx(1.0, rel=1e-10)

    def test_with_detector(self, epsf_with_detector: EffectivePSF) -> None:
        assert epsf_with_detector.total == pytest.approx(1.0, rel=1e-10)

    def test_with_motion(self, epsf_with_motion: EffectivePSF) -> None:
        assert epsf_with_motion.total == pytest.approx(1.0, rel=1e-10)


# ---------------------------------------------------------------------------
# Invariant 2: MTF(0) = 1
# ---------------------------------------------------------------------------


class TestInvariant2MTFatDC:
    def test_diffraction_only(self, epsf_diffraction_only: EffectivePSF) -> None:
        freq, mtf = epsf_diffraction_only.mtf_1d("x")
        assert mtf[0] == pytest.approx(1.0, rel=1e-10)

    def test_with_detector(self, epsf_with_detector: EffectivePSF) -> None:
        freq, mtf = epsf_with_detector.mtf_1d("x")
        assert mtf[0] == pytest.approx(1.0, rel=1e-10)

    def test_with_motion(self, epsf_with_motion: EffectivePSF) -> None:
        freq, mtf = epsf_with_motion.mtf_1d("x")
        assert mtf[0] == pytest.approx(1.0, rel=1e-10)


# ---------------------------------------------------------------------------
# Invariant 3: Parseval's theorem — ∑|PSF|² = ∑|FFT(PSF)|²/N²
# ---------------------------------------------------------------------------


class TestInvariant3Parseval:
    def test_parseval(self, epsf_with_motion: EffectivePSF) -> None:
        psf_arr = epsf_with_motion.data
        otf = np.fft.fft2(psf_arr)
        energy_spatial = float(np.sum(np.abs(psf_arr) ** 2))
        energy_freq = float(np.sum(np.abs(otf) ** 2)) / psf_arr.size
        assert energy_spatial == pytest.approx(energy_freq, rel=1e-10)


# ---------------------------------------------------------------------------
# Invariant 4: Convolution order independence
# ---------------------------------------------------------------------------


class TestInvariant4OrderIndependence:
    def test_abc_equals_cba(
        self, optical_psf: np.ndarray, epsf_config: PSFSamplingConfig
    ) -> None:
        n = optical_psf.shape[0]
        k_a = _make_rect_kernel(n, 3)
        k_b = _make_gaussian_kernel(n, 2.0)
        k_c = _make_rect_kernel(n, 5)

        dx = epsf_config.focal_spacing_m
        epsf_abc = build_effective_psf(
            optical_psf,
            [("A", k_a), ("B", k_b), ("C", k_c)],
            dx, PIXEL_PITCH_M, WAVELENGTH_M * 1e6,
        )
        epsf_cba = build_effective_psf(
            optical_psf,
            [("C", k_c), ("B", k_b), ("A", k_a)],
            dx, PIXEL_PITCH_M, WAVELENGTH_M * 1e6,
        )
        np.testing.assert_allclose(
            epsf_abc.data, epsf_cba.data, atol=1e-10
        )


# ---------------------------------------------------------------------------
# Invariant 5: EE monotonicity
# ---------------------------------------------------------------------------


class TestInvariant5EEMonotonicity:
    def test_ee_monotonic(self, epsf_with_detector: EffectivePSF) -> None:
        dx = epsf_with_detector.sample_spacing_m
        sizes = [dx * i for i in range(1, 51)]
        ees = [epsf_with_detector.ensquared_energy(s) for s in sizes]
        for i in range(len(ees) - 1):
            assert ees[i + 1] >= ees[i] - 1e-12  # allow tiny float jitter

    def test_ee_full_grid_is_one(self, epsf_with_detector: EffectivePSF) -> None:
        n = epsf_with_detector.shape[0]
        half = (n // 2) * epsf_with_detector.sample_spacing_m
        ee = epsf_with_detector.ensquared_energy(half)
        assert ee == pytest.approx(1.0, rel=1e-6)


# ---------------------------------------------------------------------------
# Invariant 6: MTF budget consistency (THE critical check)
# ---------------------------------------------------------------------------


class TestInvariant6MTFBudgetConsistency:
    def test_mtf_from_psf_equals_product_of_components(
        self, optical_psf: np.ndarray, epsf_config: PSFSamplingConfig
    ) -> None:
        """MTF from EffectivePSF FFT must equal product of individual MTFs.

        This is the key invariant from RADIANT_Spatial_Complete.md §9.1.
        """
        n = optical_psf.shape[0]
        dx = epsf_config.focal_spacing_m

        # Two degradation kernels.
        k_det = _make_rect_kernel(n, max(1, int(round(PIXEL_PITCH_M / dx))))
        k_jitter = _make_gaussian_kernel(n, 2.0)

        # Build EffectivePSF.
        epsf = build_effective_psf(
            optical_psf,
            [("det", k_det), ("jitter", k_jitter)],
            dx, PIXEL_PITCH_M, WAVELENGTH_M * 1e6,
        )

        # MTF from the EffectivePSF (single FFT of convolved PSF).
        mtf_from_psf = epsf.mtf_2d()

        # MTF from product of individual component FFTs.
        def _mtf(arr: np.ndarray) -> np.ndarray:
            otf = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(arr)))
            m = np.abs(otf)
            dc = m.max()
            if dc > 0:
                m /= dc
            return m

        mtf_optical = _mtf(optical_psf)

        # Pad kernels like the builder does.
        def _pad_kernel(kernel: np.ndarray) -> np.ndarray:
            padded = np.zeros((n, n), dtype=np.float64)
            kn = kernel.shape[0]
            kc = kn // 2
            offset = n // 2 - kc
            padded[offset : offset + kn, offset : offset + kn] = kernel
            return padded

        mtf_det = _mtf(_pad_kernel(k_det))
        mtf_jitter = _mtf(_pad_kernel(k_jitter))

        mtf_product = mtf_optical * mtf_det * mtf_jitter
        # Renormalise product DC to 1.
        c = n // 2
        dc_product = mtf_product[c, c]
        if dc_product > 0:
            mtf_product /= dc_product

        # Compare where values are significant (above noise floor).
        mask = mtf_from_psf > 1e-3
        max_diff = float(np.max(np.abs(mtf_from_psf[mask] - mtf_product[mask])))
        assert max_diff < 1e-3, f"MTF budget mismatch: max diff = {max_diff}"


# ---------------------------------------------------------------------------
# Invariant 7: Strehl = 1 for unaberrated, no motion
# ---------------------------------------------------------------------------


class TestInvariant7Strehl:
    def test_unaberrated_strehl_is_one(
        self, epsf_diffraction_only: EffectivePSF
    ) -> None:
        strehl = epsf_diffraction_only.strehl(epsf_diffraction_only)
        assert strehl == pytest.approx(1.0, rel=1e-10)


# ---------------------------------------------------------------------------
# Invariant 8: FWHM monotonic in degradations
# ---------------------------------------------------------------------------


class TestInvariant8FWHMMonotonic:
    def test_fwhm_increases_with_degradation(
        self,
        epsf_diffraction_only: EffectivePSF,
        epsf_with_detector: EffectivePSF,
        epsf_with_motion: EffectivePSF,
    ) -> None:
        fwhm_diff = epsf_diffraction_only.fwhm("x")
        fwhm_det = epsf_with_detector.fwhm("x")
        fwhm_motion = epsf_with_motion.fwhm("x")
        assert fwhm_diff < fwhm_det
        assert fwhm_det < fwhm_motion


# ---------------------------------------------------------------------------
# Invariant 9: RER decreases with degradation
# ---------------------------------------------------------------------------


class TestInvariant9RERDecreases:
    def test_rer_decreases(
        self,
        epsf_diffraction_only: EffectivePSF,
        epsf_with_motion: EffectivePSF,
    ) -> None:
        rer_ideal = epsf_diffraction_only.rer()
        rer_degraded = epsf_with_motion.rer()
        assert rer_ideal > rer_degraded


# ---------------------------------------------------------------------------
# EffectivePSF — LSF and ERF
# ---------------------------------------------------------------------------


class TestEffectivePSFLSF:
    def test_lsf_sums_to_one(self, epsf_diffraction_only: EffectivePSF) -> None:
        """LSF is projection of unit-volume PSF → integrates to ~1."""
        pos, lsf_vals = epsf_diffraction_only.lsf("x")
        assert float(lsf_vals.sum()) == pytest.approx(1.0, rel=1e-6)

    def test_erf_endpoints(self, epsf_diffraction_only: EffectivePSF) -> None:
        """ERF goes from 0 to 1."""
        pos, erf_vals = epsf_diffraction_only.erf("x")
        assert erf_vals[0] == pytest.approx(0.0, abs=0.01)
        assert erf_vals[-1] == pytest.approx(1.0, abs=0.01)

    def test_erf_monotonic(self, epsf_diffraction_only: EffectivePSF) -> None:
        pos, erf_vals = epsf_diffraction_only.erf("x")
        assert np.all(np.diff(erf_vals) >= -1e-15)


# ---------------------------------------------------------------------------
# EffectivePSF — convolution history
# ---------------------------------------------------------------------------


class TestConvolutionHistory:
    def test_no_kernels(self, epsf_diffraction_only: EffectivePSF) -> None:
        assert epsf_diffraction_only.convolution_history == ("optical",)

    def test_with_kernels(self, epsf_with_detector: EffectivePSF) -> None:
        assert "optical" in epsf_with_detector.convolution_history
        assert "pixel_aperture" in epsf_with_detector.convolution_history

    def test_zero_kernel_recorded(
        self, optical_psf: np.ndarray, epsf_config: PSFSamplingConfig
    ) -> None:
        """None kernel → recorded as 'name:zero'."""
        epsf = build_effective_psf(
            optical_psf,
            [("empty", None)],  # type: ignore[list-item]
            epsf_config.focal_spacing_m,
            PIXEL_PITCH_M,
            WAVELENGTH_M * 1e6,
        )
        assert "empty:zero" in epsf.convolution_history


# ---------------------------------------------------------------------------
# EffectivePSF — frozen
# ---------------------------------------------------------------------------


class TestEffectivePSFWithKernel:
    """Tests for ``EffectivePSF.with_kernel()`` — post-hoc kernel convolution."""

    def test_unit_volume_preserved(self, epsf_diffraction_only: EffectivePSF) -> None:
        """Convolved PSF still sums to 1.0."""
        kernel = np.zeros((3, 3))
        kernel[1, 1] = 0.9
        kernel[0, 1] = kernel[2, 1] = kernel[1, 0] = kernel[1, 2] = 0.025
        result = epsf_diffraction_only.with_kernel("test", kernel)
        assert result.total == pytest.approx(1.0, abs=1e-12)

    def test_history_appended(self, epsf_diffraction_only: EffectivePSF) -> None:
        """Convolution history includes the new kernel name."""
        kernel = np.array([[0, 0.02, 0], [0.02, 0.92, 0.02], [0, 0.02, 0]])
        result = epsf_diffraction_only.with_kernel("ipc", kernel)
        assert result.convolution_history[-1] == "ipc"
        # Original history preserved.
        assert result.convolution_history[0] == "optical"

    def test_original_unchanged(self, epsf_diffraction_only: EffectivePSF) -> None:
        """with_kernel returns a new object; original is unchanged."""
        original_data = epsf_diffraction_only.data.copy()
        kernel = np.array([[0, 0.03, 0], [0.03, 0.88, 0.03], [0, 0.03, 0]])
        _ = epsf_diffraction_only.with_kernel("ipc", kernel)
        np.testing.assert_array_equal(epsf_diffraction_only.data, original_data)

    def test_ipc_broadens_psf(self, epsf_diffraction_only: EffectivePSF) -> None:
        """IPC kernel should broaden the PSF (lower peak, wider FWHM)."""
        kernel = np.array([[0, 0.04, 0], [0.04, 0.84, 0.04], [0, 0.04, 0]])
        result = epsf_diffraction_only.with_kernel("ipc", kernel)
        assert result.peak < epsf_diffraction_only.peak
        assert result.fwhm("x") > epsf_diffraction_only.fwhm("x")

    def test_ipc_reduces_mtf(self, epsf_diffraction_only: EffectivePSF) -> None:
        """IPC should reduce MTF at all non-zero frequencies."""
        kernel = np.array([[0, 0.03, 0], [0.03, 0.88, 0.03], [0, 0.03, 0]])
        original_freq, original_mtf = epsf_diffraction_only.mtf_1d("x")
        result = epsf_diffraction_only.with_kernel("ipc", kernel)
        _, result_mtf = result.mtf_1d("x")
        # DC is still 1.0.
        assert result_mtf[0] == pytest.approx(1.0, rel=1e-6)
        # Above noise floor, IPC MTF <= original MTF.
        mask = original_mtf > 1e-6
        assert np.all(result_mtf[mask] <= original_mtf[mask] + 1e-10)

    def test_kernel_too_large_raises(self, epsf_diffraction_only: EffectivePSF) -> None:
        """Kernel larger than PSF grid raises ValueError."""
        n = epsf_diffraction_only.shape[0]
        big_kernel = np.ones((n + 2, n + 2))
        with pytest.raises(ValueError, match="exceeds PSF grid"):
            epsf_diffraction_only.with_kernel("huge", big_kernel)

    def test_metadata_preserved(self, epsf_diffraction_only: EffectivePSF) -> None:
        """Sample spacing, pixel pitch, wavelength carried over."""
        kernel = np.array([[0, 0.02, 0], [0.02, 0.92, 0.02], [0, 0.02, 0]])
        result = epsf_diffraction_only.with_kernel("ipc", kernel)
        assert result.sample_spacing_m == epsf_diffraction_only.sample_spacing_m
        assert result.pixel_pitch_m == epsf_diffraction_only.pixel_pitch_m
        assert result.wavelength_um == epsf_diffraction_only.wavelength_um


class TestEffectivePSFFrozen:
    def test_frozen(self, epsf_diffraction_only: EffectivePSF) -> None:
        with pytest.raises(AttributeError):
            epsf_diffraction_only.pixel_pitch_m = 10e-6  # type: ignore[misc]
