"""Optical MTF via autocorrelation of the complex pupil function.

For incoherent imaging, the optical transfer function (OTF) is the
normalised autocorrelation of the generalized pupil function::

    OTF(f_x, f_y) = ∫∫ P(ξ,η) P*(ξ-λzf_x, η-λzf_y) dξdη
                     ────────────────────────────────────────
                     ∫∫ |P(ξ,η)|² dξdη

    MTF = |OTF|

This is mathematically equivalent to |FFT(PSF)| by the Wiener-Khinchin
theorem, but is computed directly from the pupil without constructing
an intermediate PSF.  The two paths serve as independent validation
of each other (Rule 4 consistency check).

Reference: Goodman, *Introduction to Fourier Optics*, Ch. 6.

See RADIANT_Spatial_Complete.md §1.2 and §9.1.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from radiant.optics.pupil_amplitude import SpiderVaneSpec, make_pupil_amplitude
from radiant.optics.pupil_phase import make_pupil_phase, make_pupil_phase_zernike
from radiant.optics.sampling import compute_sampling
from radiant.optics.wavefront import WavefrontError, WfeMode


def pupil_autocorrelation_mtf_2d(
    amplitude: npt.NDArray[np.float64],
    phase: npt.NDArray[np.float64],
    padded_npix: int,
) -> npt.NDArray[np.float64]:
    """Compute the 2-D optical MTF from the pupil autocorrelation.

    Parameters
    ----------
    amplitude:
        Pupil amplitude mask, shape ``(npix, npix)``.
        From :func:`~radiant.optics.pupil_amplitude.make_pupil_amplitude`.
    phase:
        Pupil phase screen in radians, shape ``(npix, npix)``.
        From :func:`~radiant.optics.pupil_phase.make_pupil_phase` or
        :func:`~radiant.optics.pupil_phase.make_pupil_phase_zernike`.
    padded_npix:
        Side length of the zero-padded FFT grid (same value used
        for PSF computation — typically a power of 2).

    Returns
    -------
    ndarray of shape ``(padded_npix, padded_npix)``
        2-D MTF with DC at center, normalised so MTF(0,0) = 1.
    """
    npix = amplitude.shape[0]
    npad = padded_npix

    # Complex pupil function.
    pupil = amplitude * np.exp(1j * phase)

    # Zero-pad to FFT size, centered (same layout as compute_psf).
    padded = np.zeros((npad, npad), dtype=np.complex128)
    offset = (npad - npix) // 2
    padded[offset : offset + npix, offset : offset + npix] = pupil

    # Autocorrelation via Wiener-Khinchin:
    #   autocorr = IFFT(|FFT(P)|²)
    P_fft = np.fft.fft2(np.fft.ifftshift(padded))
    power_spectrum = np.abs(P_fft) ** 2
    autocorr = np.fft.fftshift(np.fft.ifft2(power_spectrum))

    # MTF = |autocorrelation|, normalised so DC = 1.
    mtf = np.abs(autocorr)
    dc = mtf.max()
    if dc > 0:
        mtf /= dc

    return mtf


def pupil_autocorrelation_mtf_1d(
    mtf_2d: npt.NDArray[np.float64],
    sample_spacing_m: float,
    axis: str = "x",
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Extract a 1-D MTF slice and corresponding frequency axis.

    Slicing convention matches :meth:`EffectivePSF.mtf_1d` exactly:
    ``"x"`` takes the horizontal slice through the DC row (center row,
    columns from center rightward); ``"y"`` takes the vertical slice
    (center column, rows from center downward).

    Parameters
    ----------
    mtf_2d:
        2-D MTF array with DC at center, from
        :func:`pupil_autocorrelation_mtf_2d`.
    sample_spacing_m:
        PSF sample spacing on the focal plane [m].
    axis:
        ``"x"`` for cross-track, ``"y"`` for along-track.

    Returns
    -------
    (freq_cycles_per_m, mtf_values)
        Spatial frequency in cycles/m and corresponding MTF values.
    """
    n = mtf_2d.shape[0]
    center = n // 2

    if axis == "x":
        mtf_slice = mtf_2d[center, center:]
    elif axis == "y":
        mtf_slice = mtf_2d[center:, center]
    else:
        raise ValueError(f"axis must be 'x' or 'y', got {axis!r}")

    freq = np.arange(len(mtf_slice)) / (n * sample_spacing_m)
    return freq, mtf_slice


def _resolve_wfe_for_wavelength(
    wfe: WavefrontError | None,
    wavelength_um: float,
    chromatic_zernikes: dict[float, dict[int, float]] | None,
) -> WavefrontError | None:
    """Resolve per-wavelength WFE for chromatic Zernike systems."""
    if chromatic_zernikes is None:
        return wfe
    best_wl = min(chromatic_zernikes.keys(), key=lambda wl: abs(wl - wavelength_um))
    coeffs = chromatic_zernikes[best_wl]
    ref_wl = wfe.reference_wavelength_um if wfe is not None else 0.633
    return WavefrontError(
        mode=WfeMode.ZERNIKE,
        zernike_coeffs=coeffs,
        reference_wavelength_um=ref_wl,
    )


def _build_pupil_phase(
    npix: int,
    wfe: WavefrontError | None,
    wavelength_m: float,
    obscuration_ratio: float,
) -> npt.NDArray[np.float64]:
    """Build the pupil phase screen — same dispatch as compute_psf."""
    if wfe is None:
        return np.zeros((npix, npix), dtype=np.float64)
    if wfe.mode == WfeMode.SCALAR_RMS:
        rms = wfe.rms_waves if wfe.rms_waves is not None else 0.0
        return make_pupil_phase(npix, rms, wavelength_m)
    if wfe.mode == WfeMode.ZERNIKE:
        assert wfe.zernike_coeffs is not None
        ref_m = wfe.reference_wavelength_um * 1e-6
        return make_pupil_phase_zernike(
            npix,
            wfe.zernike_coeffs,
            reference_wavelength_m=ref_m,
            operating_wavelength_m=wavelength_m,
            obscuration_ratio=obscuration_ratio,
        )
    raise NotImplementedError(f"WFE mode {wfe.mode.value!r} not supported.")


def polychromatic_pupil_mtf(
    wavelengths_m: npt.NDArray[np.float64],
    weights: npt.NDArray[np.float64],
    focal_length_m: float,
    aperture_diameter_m: float,
    pixel_pitch_m: float,
    obscuration_ratio: float = 0.0,
    wfe: WavefrontError | None = None,
    pupil_npix: int = 128,
    psf_oversample: int = 8,
    chromatic_zernikes: dict[float, dict[int, float]] | None = None,
    vanes: SpiderVaneSpec | None = None,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Polychromatic optical MTF via weighted average of monochromatic pupil autocorrelations.

    For each wavelength, computes the pupil autocorrelation MTF on its
    native grid, then interpolates onto a common reference frequency grid
    (defined by lambda_max) before weighted averaging.

    Parameters
    ----------
    wavelengths_m:
        Wavelengths [m], shape ``(N,)``.
    weights:
        Photon-flux weights, shape ``(N,)``. All must be positive.
    focal_length_m:
        Effective focal length [m].
    aperture_diameter_m:
        Clear aperture diameter [m].
    pixel_pitch_m:
        Detector pixel pitch [m].
    obscuration_ratio:
        Central obscuration ratio (0 = unobscured).
    wfe:
        Wavefront error specification. ``None`` = perfect optics.
    pupil_npix:
        Pupil grid side length.
    psf_oversample:
        Oversampling factor (samples per pixel).
    chromatic_zernikes:
        For refractive systems: wavelength-dependent Zernike coefficients.

    Returns
    -------
    (freq_cycles_per_m, mtf_optics_x, mtf_optics_y)
        Spatial frequency in cycles/m and the weighted-average optical
        MTF for x and y axes.
    """
    wavelengths_m = np.asarray(wavelengths_m, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    n_wl = len(wavelengths_m)

    # Reference grid from lambda_max (coarsest focal spacing).
    lam_max = float(wavelengths_m.max())
    ref_config = compute_sampling(
        wavelength_m=lam_max,
        focal_length_m=focal_length_m,
        aperture_diameter_m=aperture_diameter_m,
        pixel_pitch_m=pixel_pitch_m,
        pupil_npix=pupil_npix,
        psf_oversample=psf_oversample,
    )
    dx_ref = ref_config.focal_spacing_m
    n_padded = ref_config.padded_npix

    # Reference frequency grid (from lambda_max grid).
    n_half = n_padded // 2 + 1
    freq_ref = np.arange(n_half) / (n_padded * dx_ref)

    mtf_accum_x = np.zeros(n_half, dtype=np.float64)
    mtf_accum_y = np.zeros(n_half, dtype=np.float64)
    w_total = 0.0

    for i in range(n_wl):
        lam_i = float(wavelengths_m[i])
        w_i = float(weights[i])

        # Compute sampling config for this wavelength.
        config_i = compute_sampling(
            wavelength_m=lam_i,
            focal_length_m=focal_length_m,
            aperture_diameter_m=aperture_diameter_m,
            pixel_pitch_m=pixel_pitch_m,
            pupil_npix=pupil_npix,
            psf_oversample=psf_oversample,
        )
        # Force same padded grid size as reference.
        dx_i = (lam_i * focal_length_m) / (n_padded * config_i.pupil_spacing_m)

        # Build pupil.
        wfe_i = _resolve_wfe_for_wavelength(wfe, lam_i * 1e6, chromatic_zernikes)
        amplitude = make_pupil_amplitude(pupil_npix, obscuration_ratio, vanes)
        phase = _build_pupil_phase(pupil_npix, wfe_i, lam_i, obscuration_ratio)

        # Compute 2-D MTF from pupil autocorrelation.
        mtf_2d_i = pupil_autocorrelation_mtf_2d(amplitude, phase, n_padded)

        # Extract 1-D slices on this wavelength's native frequency grid.
        freq_i, mtf_x_i = pupil_autocorrelation_mtf_1d(mtf_2d_i, dx_i, "x")
        _, mtf_y_i = pupil_autocorrelation_mtf_1d(mtf_2d_i, dx_i, "y")

        # Interpolate onto the reference frequency grid.
        mtf_x_interp = np.interp(freq_ref, freq_i, mtf_x_i, right=0.0)
        mtf_y_interp = np.interp(freq_ref, freq_i, mtf_y_i, right=0.0)

        mtf_accum_x += w_i * mtf_x_interp
        mtf_accum_y += w_i * mtf_y_interp
        w_total += w_i

    mtf_accum_x /= w_total
    mtf_accum_y /= w_total

    return freq_ref, mtf_accum_x, mtf_accum_y
