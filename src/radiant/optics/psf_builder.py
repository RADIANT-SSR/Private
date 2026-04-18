"""PSF builder — convolve optical PSF with degradation kernels.

Takes a raw optical PSF array and a sequence of degradation kernels
(jitter, smear, defocus, IPC, diffusion, etc.) and produces an
``EffectivePSF`` via FFT-based convolution.

See RADIANT_Spatial_Complete.md §2.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from radiant.optics.effective_psf import EffectivePSF


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
