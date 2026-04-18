"""Diffraction engine: pupil function and FFT-based PSF computation.

Implements scalar Fraunhofer diffraction for a circular aperture with
optional central obscuration and wavefront error (WFE). The PSF is
computed via the FFT of the complex pupil function::

    P(x, y) = A(x, y) · exp(i · 2π · OPD(x, y) / λ)
    PSF = |FFT(P)|² / Σ|FFT(P)|²

where ``A`` is the pupil amplitude mask (1 inside clear aperture,
0 outside) and ``OPD`` is the optical path difference in metres.

Assumptions:
- Scalar diffraction (polarization ignored)
- Paraxial approximation (valid for f/# > 2)
- Spatially coherent pupil

See RADIANT_Spatial_Complete.md §3.1 for the full derivation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy.ndimage import zoom

from radiant.optics.sampling import PSFSamplingConfig, compute_sampling
from radiant.optics.wavefront import WavefrontError, WfeMode
from radiant.optics.zernike import evaluate_zernike_opd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PolychromaticPSFResult:
    """Structured result from polychromatic PSF computation.

    Parameters
    ----------
    combined_psf:
        Weighted sum of monochromatic PSFs (unit-volume normalised).
    pixel_scale_m:
        Focal-plane sample spacing [m].
    per_wavelength:
        Per-wavelength PSF arrays keyed by wavelength [um], or None
        if not requested.
    wavelengths_um:
        Wavelength grid used [um].
    weights:
        Spectral weights used (same order as wavelengths_um).
    """

    combined_psf: npt.NDArray[np.float64]
    pixel_scale_m: float
    per_wavelength: dict[float, npt.NDArray[np.float64]] | None
    wavelengths_um: npt.NDArray[np.float64]
    weights: npt.NDArray[np.float64]


def make_pupil_amplitude(
    npix: int,
    obscuration_ratio: float = 0.0,
) -> npt.NDArray[np.float64]:
    """Generate a circular pupil amplitude mask.

    The aperture is centered on the grid and has unit radius (fills
    the grid from -0.5 to +0.5 in normalised coordinates). The central
    obscuration is a concentric circle of radius ``obscuration_ratio``.

    Parameters
    ----------
    npix:
        Side length of the square pupil grid.
    obscuration_ratio:
        D_secondary / D_primary. Must be in [0, 1).

    Returns
    -------
    ndarray of shape (npix, npix)
        Binary amplitude: 1.0 in clear aperture, 0.0 outside.
    """
    if not (0.0 <= obscuration_ratio < 1.0):
        raise ValueError(
            f"obscuration_ratio must be in [0, 1), got {obscuration_ratio}"
        )

    # Normalised coordinates: [-0.5, +0.5]
    x = np.linspace(-0.5, 0.5, npix, endpoint=False) + 0.5 / npix
    xx, yy = np.meshgrid(x, x, indexing="xy")
    r = np.sqrt(xx**2 + yy**2)

    mask = np.zeros((npix, npix), dtype=np.float64)
    mask[r <= 0.5] = 1.0
    if obscuration_ratio > 0.0:
        mask[r <= 0.5 * obscuration_ratio] = 0.0

    return mask


def make_pupil_phase(
    npix: int,
    wfe_rms_waves: float = 0.0,
    wavelength_m: float = 1.0,
) -> npt.NDArray[np.float64]:
    """Generate a wavefront phase screen.

    For ``wfe_rms_waves = 0``, returns a zero-phase array (perfect
    optics). For non-zero WFE, generates a random phase screen with
    the specified RMS in waves. The phase is uniform-random per pixel,
    scaled to the correct RMS — suitable for Strehl estimation but not
    for realistic aberration modelling.

    Parameters
    ----------
    npix:
        Side length of the square grid.
    wfe_rms_waves:
        Wavefront error RMS in waves at ``wavelength_m``.
    wavelength_m:
        Operating wavelength [m]. Used to convert waves → radians.

    Returns
    -------
    ndarray of shape (npix, npix)
        Phase in radians.
    """
    if wfe_rms_waves < 0.0:
        raise ValueError(f"wfe_rms_waves must be non-negative, got {wfe_rms_waves}")

    if wfe_rms_waves == 0.0:
        return np.zeros((npix, npix), dtype=np.float64)

    if wfe_rms_waves > 1.0:
        logger.warning(
            "WFE = %.2f waves exceeds 1 wave — PSF will be severely degraded. "
            "Check if this is intentional.",
            wfe_rms_waves,
        )

    # Random phase with correct RMS.
    rng = np.random.default_rng(seed=42)
    phase_raw = rng.standard_normal((npix, npix))
    phase_raw -= phase_raw.mean()
    phase_raw /= phase_raw.std()
    phase_rad = phase_raw * (2.0 * np.pi * wfe_rms_waves)
    return phase_rad


def make_pupil_phase_zernike(
    npix: int,
    coeffs: dict[int, float],
    reference_wavelength_m: float,
    operating_wavelength_m: float,
    obscuration_ratio: float = 0.0,
) -> npt.NDArray[np.float64]:
    """Generate a wavefront phase screen from Zernike coefficients.

    Evaluates the Zernike OPD map on the pupil grid, converts from
    waves (at reference wavelength) to radians (at operating wavelength)::

        phase_rad = 2*pi * OPD_waves * (lambda_ref / lambda_operating)

    Parameters
    ----------
    npix:
        Side length of the square grid (must match pupil amplitude grid).
    coeffs:
        Noll-indexed Zernike coefficients in waves at reference wavelength.
    reference_wavelength_m:
        Wavelength at which coefficients are defined [m].
    operating_wavelength_m:
        Wavelength at which the PSF is computed [m].
    obscuration_ratio:
        Central obscuration ratio (0 = unobscured).

    Returns
    -------
    ndarray of shape (npix, npix)
        Phase screen in radians. Zero outside the pupil.
    """
    opd_waves = evaluate_zernike_opd(coeffs, npix, obscuration_ratio)
    # OPD in meters = opd_waves * lambda_ref
    # Phase at operating lambda = 2*pi * OPD_m / lambda_operating
    scale = reference_wavelength_m / operating_wavelength_m
    return 2.0 * np.pi * opd_waves * scale


def compute_psf(
    config: PSFSamplingConfig,
    obscuration_ratio: float = 0.0,
    wfe: WavefrontError | None = None,
) -> npt.NDArray[np.float64]:
    """Compute the diffraction PSF via FFT of the complex pupil.

    Dispatches on ``wfe.mode``:

    - ``None`` or ``SCALAR_RMS`` with ``rms_waves=0``: diffraction-limited.
    - ``SCALAR_RMS``: random phase screen scaled to RMS (Strehl-correct
      but aberration-agnostic).
    - ``ZERNIKE``: deterministic phase from Zernike coefficients (correct
      PSF shape for each aberration type).

    Parameters
    ----------
    config:
        PSF sampling configuration from :func:`compute_sampling`.
    obscuration_ratio:
        Central obscuration ratio D_sec / D_pri.
    wfe:
        Wavefront error specification. ``None`` = perfect optics.

    Returns
    -------
    ndarray of shape (padded_npix, padded_npix)
        Normalised PSF (sums to 1.0).
    """
    npix = config.pupil_npix
    npad = config.padded_npix

    amplitude = make_pupil_amplitude(npix, obscuration_ratio)

    # --- Phase screen dispatch ---
    if wfe is None:
        phase = np.zeros((npix, npix), dtype=np.float64)
    elif wfe.mode == WfeMode.SCALAR_RMS:
        rms = wfe.rms_waves if wfe.rms_waves is not None else 0.0
        phase = make_pupil_phase(npix, rms, config.wavelength_m)
    elif wfe.mode == WfeMode.ZERNIKE:
        assert wfe.zernike_coeffs is not None
        ref_m = wfe.reference_wavelength_um * 1e-6
        phase = make_pupil_phase_zernike(
            npix,
            wfe.zernike_coeffs,
            reference_wavelength_m=ref_m,
            operating_wavelength_m=config.wavelength_m,
            obscuration_ratio=obscuration_ratio,
        )
    else:
        raise NotImplementedError(
            f"WFE mode {wfe.mode.value!r} is not supported in compute_psf. "
            f"Supported modes: scalar_rms, zernike."
        )

    # Complex pupil function.
    pupil = amplitude * np.exp(1j * phase)

    # Zero-pad to FFT size.
    padded = np.zeros((npad, npad), dtype=np.complex128)
    # Center the pupil in the padded grid.
    offset = (npad - npix) // 2
    padded[offset : offset + npix, offset : offset + npix] = pupil

    # FFT → PSF intensity.
    U = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(padded)))
    psf = np.abs(U) ** 2

    # Normalise to unit volume.
    total = psf.sum()
    if total > 0:
        psf /= total

    return psf


def _center_crop_or_pad(
    arr: npt.NDArray[np.float64],
    target_size: int,
) -> npt.NDArray[np.float64]:
    """Center-crop or zero-pad a 2-D array to target_size × target_size."""
    n = arr.shape[0]
    if n == target_size:
        return arr
    if n > target_size:
        # Center-crop
        start = (n - target_size) // 2
        return arr[start : start + target_size, start : start + target_size].copy()
    # Zero-pad
    out = np.zeros((target_size, target_size), dtype=arr.dtype)
    start = (target_size - n) // 2
    out[start : start + n, start : start + n] = arr
    return out


def _nearest_chromatic_wl(
    target_um: float, chromatic_zernikes: dict[float, dict[int, float]]
) -> dict[int, float]:
    """Return the Zernike coefficients at the nearest tabulated wavelength."""
    best_wl = min(chromatic_zernikes.keys(), key=lambda wl: abs(wl - target_um))
    return chromatic_zernikes[best_wl]


def _resolve_wfe_for_wavelength(
    wfe: WavefrontError | None,
    wavelength_um: float,
    chromatic_zernikes: dict[float, dict[int, float]] | None,
) -> WavefrontError | None:
    """Resolve per-wavelength WFE for chromatic Zernike systems.

    When ``chromatic_zernikes`` is provided, creates a ZERNIKE-mode
    WavefrontError with coefficients from the nearest tabulated
    wavelength, using the reference wavelength from ``wfe``.

    When ``chromatic_zernikes`` is None, returns ``wfe`` unchanged.
    """
    if chromatic_zernikes is None:
        return wfe

    coeffs = _nearest_chromatic_wl(wavelength_um, chromatic_zernikes)
    ref_wl = wfe.reference_wavelength_um if wfe is not None else 0.633
    return WavefrontError(
        mode=WfeMode.ZERNIKE,
        zernike_coeffs=coeffs,
        reference_wavelength_um=ref_wl,
    )


def compute_polychromatic_psf(
    wavelengths_m: npt.NDArray[np.float64],
    weights: npt.NDArray[np.float64],
    focal_length_m: float,
    aperture_diameter_m: float,
    pixel_pitch_m: float,
    obscuration_ratio: float = 0.0,
    wfe: WavefrontError | None = None,
    pupil_npix: int = 128,
    psf_oversample: int = 8,
    store_per_wavelength: bool = False,
    chromatic_zernikes: dict[float, dict[int, float]] | None = None,
) -> PolychromaticPSFResult:
    """Compute a polychromatic PSF as the weighted sum of monochromatic PSFs.

    Each monochromatic PSF is computed on its native FFT grid, then
    resampled to a common reference grid (defined by lambda_max) before
    weighted summation. The result is normalised to unit volume.

    Parameters
    ----------
    wavelengths_m:
        Wavelengths [m], shape (N,).
    weights:
        Photon-flux weights, shape (N,). All must be strictly positive.
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
        When ``chromatic_zernikes`` is provided, ``wfe`` supplies the
        reference wavelength; Zernike coefficients are overridden
        per-wavelength from ``chromatic_zernikes``.
    pupil_npix:
        Pupil grid side length.
    psf_oversample:
        Oversampling factor (samples per pixel).
    store_per_wavelength:
        If True, store each monochromatic PSF in
        ``result.per_wavelength`` keyed by wavelength [um].
    chromatic_zernikes:
        For refractive systems: wavelength-dependent Zernike coefficients.
        Maps wavelength_um → {noll_j: coeff_waves}. When provided, each
        monochromatic PSF uses the Zernike set from the nearest tabulated
        wavelength instead of the single ``wfe`` Zernike set.

    Returns
    -------
    PolychromaticPSFResult
        Structured result with combined PSF, per-wavelength PSFs (if
        requested), wavelengths, and weights.

    Raises
    ------
    ValueError
        If inputs are invalid (mismatched lengths, non-positive weights).
    """
    wavelengths_m = np.asarray(wavelengths_m, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)

    if wavelengths_m.shape != weights.shape:
        raise ValueError(
            f"wavelengths_m and weights must have the same length, "
            f"got {len(wavelengths_m)} and {len(weights)}"
        )
    if not np.all(weights > 0.0):
        raise ValueError("All weights must be strictly positive.")
    if len(wavelengths_m) == 0:
        raise ValueError("At least one wavelength is required.")

    n_wl = len(wavelengths_m)
    wavelengths_um = wavelengths_m * 1e6

    # --- Single wavelength: delegate to monochromatic path ---
    if n_wl == 1:
        config = compute_sampling(
            wavelength_m=float(wavelengths_m[0]),
            focal_length_m=focal_length_m,
            aperture_diameter_m=aperture_diameter_m,
            pixel_pitch_m=pixel_pitch_m,
            pupil_npix=pupil_npix,
            psf_oversample=psf_oversample,
        )
        wfe_i = _resolve_wfe_for_wavelength(
            wfe, float(wavelengths_um[0]), chromatic_zernikes
        )
        psf = compute_psf(config, obscuration_ratio, wfe_i)
        per_wl: dict[float, npt.NDArray[np.float64]] | None = None
        if store_per_wavelength:
            per_wl = {float(wavelengths_um[0]): psf.copy()}
        return PolychromaticPSFResult(
            combined_psf=psf,
            pixel_scale_m=config.focal_spacing_m,
            per_wavelength=per_wl,
            wavelengths_um=wavelengths_um,
            weights=weights,
        )

    # --- Reference grid from lambda_max (coarsest spacing) ---
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

    # --- Accumulate weighted PSFs ---
    psf_accum = np.zeros((n_padded, n_padded), dtype=np.float64)
    w_total = 0.0
    per_wl_dict: dict[float, npt.NDArray[np.float64]] = {}

    for i in range(n_wl):
        lam_i = float(wavelengths_m[i])
        w_i = float(weights[i])

        config_i = compute_sampling(
            wavelength_m=lam_i,
            focal_length_m=focal_length_m,
            aperture_diameter_m=aperture_diameter_m,
            pixel_pitch_m=pixel_pitch_m,
            pupil_npix=pupil_npix,
            psf_oversample=psf_oversample,
        )
        config_i_forced = PSFSamplingConfig(
            pupil_npix=config_i.pupil_npix,
            padded_npix=n_padded,
            psf_oversample=config_i.psf_oversample,
            pupil_spacing_m=config_i.pupil_spacing_m,
            focal_spacing_m=(lam_i * focal_length_m) / (n_padded * config_i.pupil_spacing_m),
            wavelength_m=lam_i,
            focal_length_m=focal_length_m,
        )

        wfe_i = _resolve_wfe_for_wavelength(
            wfe, float(wavelengths_um[i]), chromatic_zernikes
        )
        psf_i = compute_psf(config_i_forced, obscuration_ratio, wfe_i)

        zoom_factor = lam_i / lam_max

        if abs(zoom_factor - 1.0) < 1e-12:
            psf_resampled = psf_i
        else:
            psf_resampled = zoom(psf_i, zoom_factor, order=3, mode="constant", cval=0.0)
            psf_resampled = _center_crop_or_pad(psf_resampled, n_padded)
            np.maximum(psf_resampled, 0.0, out=psf_resampled)

        total_i = psf_resampled.sum()
        if total_i > 0:
            psf_resampled /= total_i

        if store_per_wavelength:
            per_wl_dict[float(wavelengths_um[i])] = psf_resampled.copy()

        psf_accum += w_i * psf_resampled
        w_total += w_i

    psf_accum /= w_total
    total = psf_accum.sum()
    if total > 0:
        psf_accum /= total

    return PolychromaticPSFResult(
        combined_psf=psf_accum,
        pixel_scale_m=dx_ref,
        per_wavelength=per_wl_dict if store_per_wavelength else None,
        wavelengths_um=wavelengths_um,
        weights=weights,
    )


def compute_strehl(psf: npt.NDArray[np.float64], psf_ref: npt.NDArray[np.float64]) -> float:
    """Compute the Strehl ratio.

    Parameters
    ----------
    psf:
        Aberrated PSF (unit-volume normalised).
    psf_ref:
        Diffraction-limited reference PSF (unit-volume normalised,
        same grid).

    Returns
    -------
    float
        Strehl ratio = peak(psf) / peak(psf_ref).
    """
    ref_peak = psf_ref.max()
    if ref_peak == 0.0:
        raise ValueError("Reference PSF peak is zero — cannot compute Strehl.")
    return float(psf.max() / ref_peak)
