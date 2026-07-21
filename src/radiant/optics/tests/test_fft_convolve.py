"""Level 0 — exactness of the CU-165 FFT fast paths against the legacy formulas.

The CU-165 optimization must be **result-invariant**: `convolve_centered`
(rfft2 + shift-elision) and the projection-slice `mtf_1d` replace the legacy
full-complex expressions with mathematically identical ones (checkerboard
identity for even grids; projection-slice theorem for the ky=0 / kx=0 DFT
rows). These tests pin that equivalence numerically, at tolerances ~1e-13 —
ten orders tighter than the golden suite's rel=1e-3 — on grids that include
negative ringing, asymmetry, and the odd-size fallback path.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import pytest

from radiant.optics.psf.effective import EffectivePSF
from radiant.optics.psf.fft_convolve import convolve_centered


def _legacy_convolve(
    a: npt.NDArray[np.float64], b: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    """The pre-CU-165 expression, verbatim (builder.py / effective.with_kernel)."""
    a_fft = np.fft.fft2(np.fft.ifftshift(a))
    b_fft = np.fft.fft2(np.fft.ifftshift(b))
    return np.asarray(np.real(np.fft.fftshift(np.fft.ifft2(a_fft * b_fft))), dtype=np.float64)


def _legacy_mtf_1d(
    data: npt.NDArray[np.float64], dx: float, axis: str
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """The pre-CU-165 mtf_1d: full 2-D FFT, then one row/column slice."""
    otf = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(data)))
    mtf = np.abs(otf)
    dc = mtf.max()
    if dc > 0:
        mtf /= dc
    n = mtf.shape[0]
    center = n // 2
    mtf_slice = mtf[center, center:] if axis == "x" else mtf[center:, center]
    freq = np.arange(len(mtf_slice)) / (n * dx)
    return freq, mtf_slice


def _random_psf(n: int, seed: int, *, ringing: bool = False) -> npt.NDArray[np.float64]:
    """A unit-volume PSF-like array; optionally with small negative ringing."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:n, 0:n]
    cx, cy = n // 2 + 1.7, n // 2 - 2.3  # deliberately off-center / asymmetric
    data = np.exp(-(((x - cx) / (n / 9.0)) ** 2 + ((y - cy) / (n / 13.0)) ** 2))
    data += 0.02 * rng.random((n, n))
    if ringing:
        data += 1e-6 * np.sin(x * 2.1) * np.sin(y * 1.3)  # negative lobes
    return np.asarray(data / data.sum(), dtype=np.float64)


def _gauss_kernel(n: int, sigma: float, dx_off: float = 0.0) -> npt.NDArray[np.float64]:
    y, x = np.mgrid[0:n, 0:n]
    c = n // 2
    k = np.exp(-(((x - c - dx_off) ** 2 + (y - c) ** 2) / (2.0 * sigma**2)))
    return np.asarray(k / k.sum(), dtype=np.float64)


def _pad_center(kernel: npt.NDArray[np.float64], n: int) -> npt.NDArray[np.float64]:
    padded = np.zeros((n, n), dtype=np.float64)
    kn = kernel.shape[0]
    off = n // 2 - kn // 2
    padded[off : off + kn, off : off + kn] = kernel
    return padded


class TestConvolveCentered:
    @pytest.mark.parametrize("n", [16, 64, 128])
    def test_matches_legacy_even_grids(self, n: int) -> None:
        """rfft2 + shift-elision equals the legacy full-complex expression."""
        a = _random_psf(n, seed=1, ringing=True)
        b = _pad_center(_gauss_kernel(n // 4 + 1, sigma=n / 20.0, dx_off=0.8), n)
        new = convolve_centered(a, b)
        old = _legacy_convolve(a, b)
        assert np.max(np.abs(new - old)) <= 1e-13 * np.max(np.abs(old))

    def test_matches_legacy_odd_grid_fallback(self) -> None:
        """Odd n takes the legacy path (checkerboard identity needs even n)."""
        n = 33
        a = _random_psf(n, seed=2)
        b = _pad_center(_gauss_kernel(9, sigma=1.5), n)
        new = convolve_centered(a, b)
        old = _legacy_convolve(a, b)
        assert np.max(np.abs(new - old)) <= 1e-13 * np.max(np.abs(old))

    def test_asymmetric_kernel_orientation_preserved(self) -> None:
        """An off-center kernel must shift the result the same way as legacy."""
        n = 64
        a = _random_psf(n, seed=3)
        k = np.zeros((11, 11))
        k[5, 8] = 1.0  # delta 3 samples right of center → shifts PSF right
        b = _pad_center(k, n)
        new = convolve_centered(a, b)
        old = _legacy_convolve(a, b)
        assert np.max(np.abs(new - old)) <= 1e-13 * np.max(np.abs(old))
        # And the shift really happened (guards against a sign error that a
        # symmetric kernel could not detect).
        assert abs(int(np.argmax(new) % n) - int(np.argmax(a) % n) - 3) <= 1

    def test_delta_kernel_is_identity(self) -> None:
        n = 64
        a = _random_psf(n, seed=4, ringing=True)
        delta = np.zeros((n, n))
        delta[n // 2, n // 2] = 1.0
        new = convolve_centered(a, delta)
        assert np.max(np.abs(new - a)) <= 1e-13

    def test_volume_preserved(self) -> None:
        """Unit-volume PSF ⊛ unit-volume kernel keeps unit volume (pre-renorm)."""
        n = 64
        a = _random_psf(n, seed=5)
        b = _pad_center(_gauss_kernel(15, sigma=2.0), n)
        assert convolve_centered(a, b).sum() == pytest.approx(1.0, rel=1e-12)


class TestMtf1dProjectionSlice:
    def _epsf(self, n: int, seed: int) -> EffectivePSF:
        return EffectivePSF(
            data=_random_psf(n, seed=seed, ringing=True),
            sample_spacing_m=2.5e-6,
            pixel_pitch_m=25e-6,
            wavelength_um=10.0,
            convolution_history=("optical",),
        )

    @pytest.mark.parametrize("axis", ["x", "y"])
    @pytest.mark.parametrize("n", [16, 64, 256])
    def test_matches_legacy_slice(self, axis: str, n: int) -> None:
        """Projection-slice mtf_1d equals the legacy 2-D-FFT row/column slice."""
        epsf = self._epsf(n, seed=10 + n)
        freq_new, mtf_new = epsf.mtf_1d(axis)
        freq_old, mtf_old = _legacy_mtf_1d(epsf.data, epsf.sample_spacing_m, axis)
        np.testing.assert_array_equal(freq_new, freq_old)
        assert mtf_new.shape == mtf_old.shape
        assert np.max(np.abs(mtf_new - mtf_old)) <= 1e-12

    def test_odd_grid(self) -> None:
        """Odd-n slice lengths agree with the legacy indexing."""
        epsf = self._epsf(33, seed=7)
        for axis in ("x", "y"):
            freq_new, mtf_new = epsf.mtf_1d(axis)
            freq_old, mtf_old = _legacy_mtf_1d(epsf.data, epsf.sample_spacing_m, axis)
            np.testing.assert_array_equal(freq_new, freq_old)
            assert np.max(np.abs(mtf_new - mtf_old)) <= 1e-12

    def test_dc_is_unity(self) -> None:
        epsf = self._epsf(64, seed=8)
        _, mtf = epsf.mtf_1d("x")
        assert mtf[0] == pytest.approx(1.0, abs=1e-12)

    def test_invalid_axis_raises(self) -> None:
        epsf = self._epsf(16, seed=9)
        with pytest.raises(Exception, match="axis"):
            epsf.mtf_1d("z")
