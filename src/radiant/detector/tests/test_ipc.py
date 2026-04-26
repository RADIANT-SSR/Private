"""Tests for inter-pixel capacitance (IPC) kernel and MTF.

Validates:
- 3×3 kernel structure and normalisation
- Analytic MTF: (1-4α) + 2α·cos(2πfx·p) + 2α·cos(2πfy·p)
- Zero coupling → unity MTF
- Kernel FFT matches analytic MTF

See RADIANT_Detector_Complete.md §11.10 and RADIANT_Spatial_Complete.md §9.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.detector.ipc import ipc_kernel, ipc_mtf_1d, ipc_mtf_analytic

# ---------------------------------------------------------------------------
# ipc_kernel
# ---------------------------------------------------------------------------


class TestIPCKernel:
    @pytest.mark.level0
    def test_shape(self) -> None:
        k = ipc_kernel(0.02)
        assert k.shape == (3, 3)

    @pytest.mark.level0
    def test_unit_volume(self) -> None:
        """Kernel sums to 1.0."""
        k = ipc_kernel(0.03)
        assert float(k.sum()) == pytest.approx(1.0, rel=1e-12)

    @pytest.mark.level0
    def test_center_value(self) -> None:
        alpha = 0.04
        k = ipc_kernel(alpha)
        assert k[1, 1] == pytest.approx(1.0 - 4.0 * alpha, rel=1e-12)

    @pytest.mark.level0
    def test_neighbour_values(self) -> None:
        alpha = 0.02
        k = ipc_kernel(alpha)
        assert k[0, 1] == pytest.approx(alpha, rel=1e-12)
        assert k[2, 1] == pytest.approx(alpha, rel=1e-12)
        assert k[1, 0] == pytest.approx(alpha, rel=1e-12)
        assert k[1, 2] == pytest.approx(alpha, rel=1e-12)

    @pytest.mark.level0
    def test_corners_zero(self) -> None:
        k = ipc_kernel(0.03)
        assert k[0, 0] == 0.0
        assert k[0, 2] == 0.0
        assert k[2, 0] == 0.0
        assert k[2, 2] == 0.0

    @pytest.mark.level0
    def test_zero_coupling(self) -> None:
        """Zero coupling → delta kernel."""
        k = ipc_kernel(0.0)
        assert k[1, 1] == 1.0
        assert float(k.sum()) == 1.0

    @pytest.mark.level0
    def test_coupling_too_large_raises(self) -> None:
        with pytest.raises(ValueError, match="IPC coupling"):
            ipc_kernel(0.25)

    @pytest.mark.level0
    def test_negative_coupling_raises(self) -> None:
        with pytest.raises(ValueError, match="IPC coupling"):
            ipc_kernel(-0.01)


# ---------------------------------------------------------------------------
# ipc_mtf_analytic — Truth Anchor
# ---------------------------------------------------------------------------


class TestIPCMTFAnalytic:
    @pytest.mark.level0
    def test_dc_is_one(self) -> None:
        """MTF(0,0) = (1-4α) + 2α + 2α = 1.0."""
        fx = np.array([0.0])
        fy = np.array([0.0])
        mtf = ipc_mtf_analytic(fx, fy, coupling=0.03, pixel_pitch_m=15e-6)
        assert mtf[0] == pytest.approx(1.0, rel=1e-12)

    @pytest.mark.level0
    def test_nyquist(self) -> None:
        """At Nyquist (f = 1/(2p)), cos(2π·f·p) = cos(π) = -1.

        MTF(f_Ny) = (1-4α) + 2α·(-1) + 2α·(-1) = 1-8α.
        """
        pitch = 15e-6
        f_ny = 1.0 / (2.0 * pitch)
        alpha = 0.03
        fx = np.array([f_ny])
        fy = np.array([f_ny])
        mtf = ipc_mtf_analytic(fx, fy, alpha, pitch)
        expected = 1.0 - 8.0 * alpha
        assert mtf[0] == pytest.approx(expected, rel=1e-10)

    @pytest.mark.level0
    def test_zero_coupling_unity(self) -> None:
        freq = np.linspace(0, 1e5, 50)
        mtf = ipc_mtf_analytic(freq, np.zeros_like(freq), 0.0, 15e-6)
        np.testing.assert_array_equal(mtf, np.ones_like(freq))

    @pytest.mark.level0
    def test_hand_calculation(self) -> None:
        """Manual check at f = 1/(4p).

        cos(2π · f · p) = cos(π/2) = 0.
        MTF = (1-4α) + 0 + 2α = 1 - 2α (along x only).
        """
        pitch = 15e-6
        f = 1.0 / (4.0 * pitch)
        alpha = 0.05
        fx = np.array([f])
        fy = np.array([0.0])
        mtf = ipc_mtf_analytic(fx, fy, alpha, pitch)
        expected = 1.0 - 2.0 * alpha
        assert mtf[0] == pytest.approx(expected, rel=1e-10)


# ---------------------------------------------------------------------------
# ipc_mtf_1d
# ---------------------------------------------------------------------------


class TestIPCMTF1D:
    @pytest.mark.level0
    def test_x_axis(self) -> None:
        freq = np.array([0.0, 1e4])
        mtf = ipc_mtf_1d(freq, 0.02, 15e-6, axis="x")
        assert mtf[0] == pytest.approx(1.0, rel=1e-12)
        assert len(mtf) == 2

    @pytest.mark.level0
    def test_y_axis(self) -> None:
        freq = np.array([0.0])
        mtf = ipc_mtf_1d(freq, 0.02, 15e-6, axis="y")
        assert mtf[0] == pytest.approx(1.0, rel=1e-12)

    @pytest.mark.level0
    def test_invalid_axis(self) -> None:
        with pytest.raises(ValueError, match="axis must be"):
            ipc_mtf_1d(np.array([0.0]), 0.02, 15e-6, axis="z")


# ---------------------------------------------------------------------------
# Cross-model: kernel FFT vs analytic MTF
# ---------------------------------------------------------------------------


class TestIPCCrossModel:
    @pytest.mark.level1
    def test_kernel_fft_matches_analytic(self) -> None:
        """FFT of the 3×3 IPC kernel matches the analytic MTF formula."""
        alpha = 0.03
        pitch = 15e-6

        k = ipc_kernel(alpha)

        # Embed in a larger grid and FFT.
        n = 128
        padded = np.zeros((n, n), dtype=np.float64)
        # Center the 3×3 kernel.
        c = n // 2
        padded[c - 1 : c + 2, c - 1 : c + 2] = k

        otf = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(padded)))
        mtf_fft = np.abs(otf)
        mtf_fft /= mtf_fft.max()

        # Compare along x-axis (fy=0).
        mtf_x = mtf_fft[c, c:]
        # The kernel is sampled at pixel pitch, so freq spacing = 1/(n*pitch).
        freq = np.arange(len(mtf_x)) / (n * pitch)
        mtf_analytic = ipc_mtf_1d(freq, alpha, pitch, axis="x")

        # They should match closely.
        np.testing.assert_allclose(mtf_x, mtf_analytic, atol=0.01)
