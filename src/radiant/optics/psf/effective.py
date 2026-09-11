"""EffectivePSF — single source of truth for all spatial metrics.

End-state PSF after all spatial degradations (diffraction, defocus,
jitter, smear, IPC, diffusion) have been convolved. Every spatial
metric — MTF, EE, LSF, ERF, RER, FWHM — is derived from this
object's ``data`` array via FFT or numerical integration.

This enforces Rule 4: **never** compute MTF and EE from different PSFs.

See RADIANT_Spatial_Complete.md §2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.optics.errors import OpticsValidationError
from radiant.optics.pixel_phase import resolve_pixel_phase
from radiant.optics.psf.fft_convolve import convolve_centered


@dataclass(frozen=True)
class EffectivePSF:
    """End-state PSF after all spatial degradations have been applied.

    **Single source of truth** for MTF, EE, LSF, ERF, RER, FWHM.
    Every spatial metric is derived from ``self.data`` via FFT or
    numerical integration. No independent formulas.

    See RADIANT_Spatial_Complete.md §2.
    """

    data: npt.NDArray[np.float64]
    sample_spacing_m: float
    pixel_pitch_m: float
    wavelength_um: float
    convolution_history: tuple[str, ...]
    #: The kernels convolved in, paired with their history names and in the same
    #: order — the *unpadded* arrays as handed to :meth:`with_kernel`, on this
    #: PSF's sample grid. ``convolution_history`` records that a degradation was
    #: applied; this records **what it looked like**, which is what a view needs
    #: to show the convolution rather than only name it. Empty on a freshly built
    #: PSF (nothing convolved yet) and for the ``"optical"`` seed term, which is
    #: the diffraction PSF itself and not a kernel.
    kernels: tuple[tuple[str, npt.NDArray[np.float64]], ...] = ()

    # -- basic properties ---------------------------------------------------

    @property
    def shape(self) -> tuple[int, int]:
        return self.data.shape  # type: ignore[return-value]

    @property
    def peak(self) -> float:
        return float(self.data.max())

    @property
    def total(self) -> float:
        return float(self.data.sum())

    # -- kernel convolution -------------------------------------------------

    def with_kernel(self, name: str, kernel: npt.NDArray[np.float64]) -> EffectivePSF:
        """Return a new EffectivePSF with an additional kernel convolved in.

        Uses FFT-based convolution, identical to ``build_effective_psf``.
        The kernel must be a 2-D array normalised to unit volume.

        Parameters
        ----------
        name:
            Label for the convolution history (e.g. ``"ipc"``).
        kernel:
            2-D kernel array (must fit within the PSF grid).
        """
        n = self.data.shape[0]
        kn = kernel.shape[0]
        if kn > n:
            raise OpticsValidationError(
                f"Kernel '{name}' has size {kn} which exceeds PSF grid {n}."
            )

        # Pad kernel to PSF size, centered.
        padded = np.zeros((n, n), dtype=np.float64)
        kc = kn // 2
        offset = n // 2 - kc
        padded[offset : offset + kn, offset : offset + kn] = kernel

        # FFT convolution (CU-165 real-input fast path; exact — see fft_convolve).
        convolved = convolve_centered(self.data, padded)

        # Re-normalise to unit volume.
        total = convolved.sum()
        if total > 0:
            convolved /= total

        return EffectivePSF(
            data=convolved,
            sample_spacing_m=self.sample_spacing_m,
            pixel_pitch_m=self.pixel_pitch_m,
            wavelength_um=self.wavelength_um,
            convolution_history=self.convolution_history + (name,),
            # Retain the kernel beside its name so the convolution can be shown,
            # not merely listed. The unpadded array is kept (the padded copy is a
            # full PSF-grid array and would cost the same memory as the PSF).
            kernels=(*self.kernels, (name, kernel)),
        )

    # -- MTF ----------------------------------------------------------------

    def mtf_2d(self) -> npt.NDArray[np.float64]:
        """2-D MTF = |FFT(PSF)|, normalised so MTF(0,0) = 1."""
        otf = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(self.data)))
        mtf = np.abs(otf)
        dc = mtf.max()
        if dc > 0:
            mtf /= dc
        return mtf

    def mtf_1d(self, axis: str = "x") -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """1-D MTF slice along the specified axis.

        Computed via the projection-slice theorem (CU-165): the ky=0 (or
        kx=0) row of the 2-D OTF is exactly the 1-D DFT of the PSF's
        projection onto that axis, so one length-n real FFT of the LSF
        replaces the full n×n 2-D FFT (identical values; validated to
        ≤1e-12 against the 2-D slice in ``tests/test_fft_convolve.py``).
        Normalisation is by the DC term — for a real, non-negative PSF the
        2-D MTF's maximum is its DC value, so this matches the previous
        ``mtf_2d().max()`` normalisation.

        Parameters
        ----------
        axis:
            ``"x"`` for cross-track, ``"y"`` for along-track.

        Returns
        -------
        (freq_cycles_per_m, mtf_values)
        """
        n = self.data.shape[0]
        center = n // 2
        dx = self.sample_spacing_m

        if axis == "x":
            lsf_vals = self.data.sum(axis=0)
        elif axis == "y":
            lsf_vals = self.data.sum(axis=1)
        else:
            raise OpticsValidationError(f"axis must be 'x' or 'y', got {axis!r}")

        spectrum = np.abs(np.fft.rfft(np.fft.ifftshift(lsf_vals)))
        dc = spectrum[0]
        if dc > 0:
            spectrum /= dc
        mtf_slice = spectrum[: n - center]

        freq = np.arange(len(mtf_slice)) / (n * dx)
        return freq, mtf_slice

    # -- Ensquared energy ---------------------------------------------------

    def ensquared_energy(self, half_width_m: float) -> float:
        """Fraction of PSF energy within a square box of given half-width.

        Each sample ``i`` carries the energy of the detector-plane cell
        ``[i − 0.5, i + 0.5]·dx`` centred on it (``self.data`` is the
        unit-volume per-cell energy). Its 1-D weight is the fraction of that
        cell inside the box ``[−H, H]·dx`` with ``H = half_width / dx``:

            w(d) = clamp(H − d + 0.5, 0, 1),   d = |i − center|

        i.e. 1.0 for fully-enclosed cells, a linear taper across the one cell
        the box edge cuts, 0 outside. The 2-D box integral is the separable
        product ``data · outer(w, w)``.

        CU-188: this cell-area-overlap weighting replaces an earlier
        point-sampling scheme that gave every cell within ``floor(H)`` full
        weight and only tapered a fractional *overshoot* cell. That left the
        box-edge cells at full weight when ``H`` was integral (the common
        critically-sampled case), an O(dx) bias that over-stated EE_box — and
        hence point-source / sub-pixel SNR — by up to ~24% at the default
        pupil sampling. The overlap weighting is second-order accurate: the
        unaberrated-Airy Q=2 box matches the analytic 0.177327 to ~3e-4 at
        every ``psf_oversample`` including the default 8.
        """
        n = self.data.shape[0]
        center = n // 2
        dx = self.sample_spacing_m
        half_samples = half_width_m / dx  # H, box half-width in samples

        idx = np.arange(n)
        w_full = np.clip(half_samples - np.abs(idx - center) + 0.5, 0.0, 1.0)
        support = np.nonzero(w_full > 0.0)[0]
        if support.size == 0:
            return 0.0
        lo, hi = int(support[0]), int(support[-1]) + 1
        w = w_full[lo:hi]

        return float(np.einsum("i,j,ij->", w, w, self.data[lo:hi, lo:hi]))

    def ensquared_energy_nxn(
        self,
        n_pixels: int,
        *,
        phase_mode: str = "average",
        phase: tuple[float, float] = (0.0, 0.0),
    ) -> float:
        """EE collected by an n×n pixel block at the selected pixel sampling phase.

        ``phase_mode`` is the straddle convention (Gap 129; see
        :mod:`radiant.optics.pixel_phase` and RADIANT_Spatial_Complete.md §6.1):

        - ``"average"`` — expectation over a source uniformly placed across one
          pitch. This is the pitch-wide box integral of ``data``: with the
          photosite rect already convolved in, rect ⊛ rect is a triangle, and
          the box integral of the pixel-convolved PSF *is* the phase average.
        - ``"centered"`` / ``"worst_case"`` / ``"specified"`` — the block's
          energy at one phase, via :meth:`pixel_block_energy_at`.
        """
        offset = resolve_pixel_phase(phase_mode, phase[0], phase[1])
        if offset is None:
            half_width = (n_pixels / 2.0) * self.pixel_pitch_m
            return self.ensquared_energy(half_width)
        return self.pixel_block_energy_at(n_pixels, offset[0], offset[1])

    def pixel_block_energy_at(self, n_pixels: int, dx_pix: float, dy_pix: float) -> float:
        """Energy in an n×n pixel block whose centre is displaced from the image point.

        Exact identity, not a second box integral: the photosite rect
        ``rect_w`` (unit sum on the sample grid) is already convolved into
        ``data``, so ``data(δ)·(p/Δ)²`` is ``∫∫ PSF(x)·rect_p(x − δ) dx`` — the
        energy a full-pitch box at phase δ collects (the fill factor is applied
        downstream, CU-074, so the value is normalised to the pitch box for every
        ``fill_factor``). The block is the sum over its pixel centres
        ``δ + (i, j)·p``; ``data`` is read by bilinear interpolation.

        Parameters
        ----------
        n_pixels:
            Block side length in pixels (≥ 1).
        dx_pix, dy_pix:
            Displacement of the block centre from the PSF grid centre (the
            chief-ray image point), in pixel pitches.

        Raises
        ------
        OpticsValidationError
            If the pixel-aperture kernel has not been convolved in (the identity
            needs it), or ``n_pixels < 1``.
        """
        if n_pixels < 1:
            raise OpticsValidationError(f"n_pixels must be >= 1, got {n_pixels}")
        if "pixel_aperture" not in self.convolution_history:
            raise OpticsValidationError(
                "pixel_block_energy_at needs the pixel-aperture kernel convolved in "
                f"(history: {self.convolution_history}); the point-evaluation identity "
                "EE(δ) = data(δ)·(p/Δ)² holds only for the pixel-convolved PSF. Use "
                "ensquared_energy(...) on an optics-only PSF."
            )
        spp = self.pixel_pitch_m / self.sample_spacing_m
        n = self.data.shape[0]
        center = n // 2
        total = 0.0
        for i in range(n_pixels):
            for j in range(n_pixels):
                col = center + (dx_pix + (i - (n_pixels - 1) / 2.0)) * spp
                row = center + (dy_pix + (j - (n_pixels - 1) / 2.0)) * spp
                total += _bilinear(self.data, row, col)
        return float(total * spp * spp)

    # -- LSF, ERF, RER ------------------------------------------------------

    def lsf(self, axis: str = "x") -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """Line Spread Function = projection of PSF onto axis.

        Parameters
        ----------
        axis:
            ``"x"`` or ``"y"``.

        Returns
        -------
        (position_m, lsf_values)
        """
        n = self.data.shape[0]
        center = n // 2
        dx = self.sample_spacing_m

        if axis == "x":
            lsf_vals = self.data.sum(axis=0)  # project rows → x profile
        elif axis == "y":
            lsf_vals = self.data.sum(axis=1)  # project cols → y profile
        else:
            raise OpticsValidationError(f"axis must be 'x' or 'y', got {axis!r}")

        pos = (np.arange(n) - center) * dx
        return pos, lsf_vals

    def erf(self, axis: str = "x") -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """Edge Response Function = cumulative integral of LSF.

        Returns
        -------
        (position_m, erf_values)
            ERF normalised to [0, 1].
        """
        pos, lsf_vals = self.lsf(axis)
        erf_vals = np.cumsum(lsf_vals)
        total = erf_vals[-1]
        if total > 0:
            erf_vals /= total
        return pos, erf_vals

    def edge_slope(self, axis: str = "x") -> float:
        """Maximum slope of the ERF [contrast / m]."""
        pos, erf_vals = self.erf(axis)
        dx = self.sample_spacing_m
        slope = np.gradient(erf_vals, dx)
        return float(np.max(slope))

    def rer(self) -> float:
        """Relative Edge Response (GIQE-5 definition).

        RER = geometric mean of (ERF(+p/2) - ERF(-p/2)) in x and y,
        where p is the pixel pitch.
        """
        rer_vals = []
        for axis in ("x", "y"):
            pos, erf_vals = self.erf(axis)
            half_pitch = self.pixel_pitch_m / 2.0
            # Interpolate ERF at ±half_pitch.
            erf_plus = float(np.interp(half_pitch, pos, erf_vals))
            erf_minus = float(np.interp(-half_pitch, pos, erf_vals))
            rer_vals.append(erf_plus - erf_minus)
        return float(np.sqrt(rer_vals[0] * rer_vals[1]))

    # -- FWHM ---------------------------------------------------------------

    def fwhm(self, axis: str = "x") -> float:
        """Full-width at half-maximum along the specified axis [m]."""
        n = self.data.shape[0]
        center = n // 2
        dx = self.sample_spacing_m

        if axis == "x":
            profile = self.data[center, center:]
        elif axis == "y":
            profile = self.data[center:, center]
        else:
            raise OpticsValidationError(f"axis must be 'x' or 'y', got {axis!r}")

        peak = profile[0]
        half_max = peak / 2.0

        below = np.where(profile < half_max)[0]
        if len(below) == 0:
            return float(n * dx)

        idx = below[0]
        if idx > 0:
            y0, y1 = profile[idx - 1], profile[idx]
            frac = (half_max - y0) / (y1 - y0) if y1 != y0 else 0.0
            r_half = (idx - 1 + frac) * dx
        else:
            r_half = 0.0

        return 2.0 * r_half

    # -- Strehl -------------------------------------------------------------

    def strehl(self, reference: EffectivePSF) -> float:
        """Strehl ratio = peak(self) / peak(reference)."""
        ref_peak = reference.peak
        if ref_peak == 0.0:
            raise OpticsValidationError("Reference PSF peak is zero.")
        return self.peak / ref_peak


def _bilinear(data: npt.NDArray[np.float64], row: float, col: float) -> float:
    """Bilinearly interpolate ``data`` at fractional ``(row, col)``; 0 outside the grid."""
    n_rows, n_cols = data.shape
    if row < 0.0 or col < 0.0 or row > n_rows - 1 or col > n_cols - 1:
        return 0.0
    r0 = int(math.floor(row))
    c0 = int(math.floor(col))
    r1 = min(r0 + 1, n_rows - 1)
    c1 = min(c0 + 1, n_cols - 1)
    fr = row - r0
    fc = col - c0
    return float(
        data[r0, c0] * (1.0 - fr) * (1.0 - fc)
        + data[r1, c0] * fr * (1.0 - fc)
        + data[r0, c1] * (1.0 - fr) * fc
        + data[r1, c1] * fr * fc
    )
