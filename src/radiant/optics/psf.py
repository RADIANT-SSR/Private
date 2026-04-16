"""PSF container, EffectivePSF, and PSF-to-OTF/MTF transform.

Wraps a 2-D PSF array with its sampling metadata and provides
methods to extract the MTF, encircled energy, LSF, ERF, RER,
and derived spatial metrics.

``PSFData`` is the raw optical PSF from the diffraction engine.
``EffectivePSF`` is the single source of truth for all spatial
metrics after all degradation kernels have been convolved.

See RADIANT_Spatial_Complete.md §2 and §9 for definitions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.optics.sampling import PSFSamplingConfig


@dataclass(frozen=True)
class PSFData:
    """Immutable container for a 2-D PSF and its sampling grid.

    Parameters
    ----------
    data:
        2-D PSF array, unit-volume normalised (sums to 1.0).
    config:
        The :class:`PSFSamplingConfig` that produced this PSF.
    wavelength_m:
        Wavelength at which this PSF was computed [m].
    strehl:
        Strehl ratio (1.0 for diffraction-limited).
    """

    data: npt.NDArray[np.float64]
    config: PSFSamplingConfig
    wavelength_m: float
    strehl: float = 1.0

    @property
    def shape(self) -> tuple[int, int]:
        return self.data.shape  # type: ignore[return-value]

    @property
    def peak(self) -> float:
        """Peak intensity of the PSF."""
        return float(self.data.max())

    @property
    def total(self) -> float:
        """Total energy (should be ~1.0 for a normalised PSF)."""
        return float(self.data.sum())

    def mtf_2d(self) -> npt.NDArray[np.float64]:
        """Compute the 2-D MTF from the PSF.

        MTF = |FFT(PSF)|, normalised so MTF(0,0) = 1.

        Returns
        -------
        ndarray
            2-D MTF array (same shape as the PSF).
        """
        otf = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(self.data)))
        mtf = np.abs(otf)
        dc = mtf.max()
        if dc > 0:
            mtf /= dc
        return mtf

    def mtf_1d(self, axis: str = "x") -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """Extract a 1-D MTF slice along the specified axis.

        Parameters
        ----------
        axis:
            ``"x"`` for cross-track (horizontal), ``"y"`` for
            along-track (vertical).

        Returns
        -------
        (freq_cycles_per_m, mtf_values)
            Spatial frequency in cycles/m and corresponding MTF.
        """
        mtf_2d = self.mtf_2d()
        n = mtf_2d.shape[0]
        center = n // 2

        if axis == "x":
            mtf_slice = mtf_2d[center, center:]
        elif axis == "y":
            mtf_slice = mtf_2d[center:, center]
        else:
            raise ValueError(f"axis must be 'x' or 'y', got {axis!r}")

        # Spatial frequency grid.
        dx = self.config.focal_spacing_m
        freq = np.arange(len(mtf_slice)) / (n * dx)

        return freq, mtf_slice

    def encircled_energy(self, half_width_m: float) -> float:
        """Compute the encircled energy within a square box.

        Parameters
        ----------
        half_width_m:
            Half-width of the box in metres (physical FPA coordinates).

        Returns
        -------
        float
            Fraction of total PSF energy within the box.
        """
        n = self.data.shape[0]
        center = n // 2
        dx = self.config.focal_spacing_m
        half_pix = int(round(half_width_m / dx))

        lo = max(center - half_pix, 0)
        hi = min(center + half_pix + 1, n)
        box = self.data[lo:hi, lo:hi]
        return float(box.sum())

    def fwhm_m(self) -> float:
        """Estimate the PSF full-width at half-maximum [m].

        Uses a radial profile from the PSF center. Returns the
        diameter where the profile drops to 50% of peak.
        """
        n = self.data.shape[0]
        center = n // 2
        dx = self.config.focal_spacing_m

        # Radial profile (horizontal slice from center).
        profile = self.data[center, center:]
        peak = profile[0]
        half_max = peak / 2.0

        # Find first crossing below half-max.
        below = np.where(profile < half_max)[0]
        if len(below) == 0:
            return float(n * dx)  # PSF never drops below half-max

        idx = below[0]
        # Linear interpolation between idx-1 and idx.
        if idx > 0:
            y0, y1 = profile[idx - 1], profile[idx]
            frac = (half_max - y0) / (y1 - y0) if y1 != y0 else 0.0
            r_half = (idx - 1 + frac) * dx
        else:
            r_half = 0.0

        return 2.0 * r_half  # diameter = 2 × radius


# ---------------------------------------------------------------------------
# EffectivePSF — single source of truth for all spatial metrics
# ---------------------------------------------------------------------------


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

    def with_kernel(
        self, name: str, kernel: npt.NDArray[np.float64]
    ) -> "EffectivePSF":
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
            raise ValueError(
                f"Kernel '{name}' has size {kn} which exceeds PSF grid {n}."
            )

        # Pad kernel to PSF size, centered.
        padded = np.zeros((n, n), dtype=np.float64)
        kc = kn // 2
        offset = n // 2 - kc
        padded[offset : offset + kn, offset : offset + kn] = kernel

        # FFT convolution.
        psf_fft = np.fft.fft2(np.fft.ifftshift(self.data))
        k_fft = np.fft.fft2(np.fft.ifftshift(padded))
        convolved = np.real(np.fft.fftshift(np.fft.ifft2(psf_fft * k_fft)))

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

    def mtf_1d(
        self, axis: str = "x"
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """1-D MTF slice along the specified axis.

        Parameters
        ----------
        axis:
            ``"x"`` for cross-track, ``"y"`` for along-track.

        Returns
        -------
        (freq_cycles_per_m, mtf_values)
        """
        mtf_2d = self.mtf_2d()
        n = mtf_2d.shape[0]
        center = n // 2
        dx = self.sample_spacing_m

        if axis == "x":
            mtf_slice = mtf_2d[center, center:]
        elif axis == "y":
            mtf_slice = mtf_2d[center:, center]
        else:
            raise ValueError(f"axis must be 'x' or 'y', got {axis!r}")

        freq = np.arange(len(mtf_slice)) / (n * dx)
        return freq, mtf_slice

    # -- Ensquared energy ---------------------------------------------------

    def ensquared_energy(self, half_width_m: float) -> float:
        """Fraction of PSF energy within a square box of given half-width.

        Uses sub-sample interpolation at the box boundary to avoid
        grid-quantization error when the PSF sample spacing does not
        evenly divide the requested half-width (e.g. after FFT
        power-of-2 padding).  A 1-D weight vector is constructed
        with 1.0 for fully enclosed samples and fractional weight
        at the boundary; the 2-D box integral is the separable
        product ``data · outer(w, w)``.
        """
        n = self.data.shape[0]
        center = n // 2
        dx = self.sample_spacing_m
        half_samples = half_width_m / dx  # exact, may be fractional

        # Build 1-D weight vector for the relevant index range.
        # Box spans [center - half_samples, center + half_samples].
        # Sample i is fully inside if |i - center| <= floor(half_samples).
        # The boundary samples at floor(half_samples)+1 from center get
        # fractional weight equal to the overshoot.
        n_full = int(half_samples)
        frac = half_samples - n_full

        lo = max(center - n_full - (1 if frac > 0.0 else 0), 0)
        hi = min(center + n_full + 1 + (1 if frac > 0.0 else 0), n)
        w = np.ones(hi - lo, dtype=np.float64)

        if frac > 0.0:
            # Weight the outermost sample on each side by the fraction
            if lo == center - n_full - 1:
                w[0] = frac
            if hi == center + n_full + 2:
                w[-1] = frac

        return float(np.einsum("i,j,ij->", w, w, self.data[lo:hi, lo:hi]))

    def ensquared_energy_nxn(self, n_pixels: int) -> float:
        """EE within an n×n pixel box centred on the PSF."""
        half_width = (n_pixels / 2.0) * self.pixel_pitch_m
        return self.ensquared_energy(half_width)

    # -- LSF, ERF, RER ------------------------------------------------------

    def lsf(
        self, axis: str = "x"
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
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
            raise ValueError(f"axis must be 'x' or 'y', got {axis!r}")

        pos = (np.arange(n) - center) * dx
        return pos, lsf_vals

    def erf(
        self, axis: str = "x"
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
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
            raise ValueError(f"axis must be 'x' or 'y', got {axis!r}")

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
            raise ValueError("Reference PSF peak is zero.")
        return self.peak / ref_peak


# ---------------------------------------------------------------------------
# Builder: convolve optical PSF with degradation kernels
# ---------------------------------------------------------------------------


def build_effective_psf(
    optical_psf: npt.NDArray[np.float64],
    kernels: list[tuple[str, npt.NDArray[np.float64]]],
    sample_spacing_m: float,
    pixel_pitch_m: float,
    wavelength_um: float,
) -> EffectivePSF:
    """Convolve the optical PSF with a sequence of degradation kernels.

    Each kernel is a 2-D array normalised to unit volume (or 1-D, in
    which case it is applied as a separable outer product). Convolution
    is performed via FFT multiplication.

    Parameters
    ----------
    optical_psf:
        2-D optical PSF (unit-volume normalised).
    kernels:
        List of (name, kernel_2d) tuples. Each kernel must have the
        same sample spacing as the PSF grid. Zero-size kernels (None
        or single-pixel delta) are recorded as ``"name:zero"`` and
        skipped.
    sample_spacing_m:
        Physical sample spacing [m].
    pixel_pitch_m:
        Detector pixel pitch [m].
    wavelength_um:
        Wavelength [µm].

    Returns
    -------
    EffectivePSF
        The fully convolved PSF with all spatial metrics.
    """
    psf = optical_psf.copy()
    history: list[str] = ["optical"]

    for name, kernel in kernels:
        # Check for zero/delta kernel.
        if kernel is None:
            history.append(f"{name}:zero")
            continue
        if kernel.size == 1:
            history.append(f"{name}:zero")
            continue
        # Check if kernel is effectively a delta.
        if kernel.shape[0] > 1:
            c = kernel.shape[0] // 2
            if kernel.ndim == 2 and kernel[c, c] > 0.999 and float(kernel.sum()) < 1.001:
                # Nearly all energy at center → skip.
                non_center = kernel.copy()
                non_center[c, c] = 0.0
                if non_center.sum() < 1e-10:
                    history.append(f"{name}:zero")
                    continue

        history.append(name)

        # Pad kernel to PSF size for FFT convolution.
        n = psf.shape[0]
        padded_kernel = np.zeros((n, n), dtype=np.float64)

        if kernel.ndim == 1:
            # 1-D kernel: assumed to apply along a single axis.
            # Use outer product with a delta in the orthogonal axis
            # so that e.g. a smear kernel only blurs along-track.
            # Caller convention: 1-D kernels in the ``kernels`` list
            # are paired with a name ending in "_x" or "_y" to
            # indicate the axis.  Default (no suffix) applies along x.
            delta = np.zeros_like(kernel)
            delta[len(delta) // 2] = 1.0
            if name.endswith("_y"):  # noqa: SIM108
                kernel_2d = np.outer(kernel, delta)
            else:
                kernel_2d = np.outer(delta, kernel)
        else:
            kernel_2d = kernel

        kn = kernel_2d.shape[0]
        if kn > n:
            raise ValueError(
                f"Kernel '{name}' has size {kn} which exceeds PSF grid {n}. "
                "Increase PSF grid size or reduce the degradation magnitude."
            )

        # Center the kernel in the padded grid.
        kc = kn // 2
        offset = n // 2 - kc
        padded_kernel[offset : offset + kn, offset : offset + kn] = kernel_2d

        # FFT convolution: shift both to put DC at corners, multiply, shift back.
        PSF_fft = np.fft.fft2(np.fft.ifftshift(psf))
        K_fft = np.fft.fft2(np.fft.ifftshift(padded_kernel))
        psf = np.real(np.fft.fftshift(np.fft.ifft2(PSF_fft * K_fft)))

    # Re-normalise to unit volume (absorb FFT round-off).
    total = psf.sum()
    if total > 0:
        psf /= total

    return EffectivePSF(
        data=psf,
        sample_spacing_m=sample_spacing_m,
        pixel_pitch_m=pixel_pitch_m,
        wavelength_um=wavelength_um,
        convolution_history=tuple(history),
    )
