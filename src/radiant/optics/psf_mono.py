"""Monochromatic PSF via FFT of the complex pupil function.

Implements scalar Fraunhofer diffraction for a circular aperture with
optional central obscuration and wavefront error (WFE)::

    P(x, y) = A(x, y) · exp(i · 2π · OPD(x, y) / λ)
    PSF = |FFT(P)|² / Σ|FFT(P)|²

where ``A`` is the pupil amplitude mask (1 inside clear aperture,
0 outside) and ``OPD`` is the optical path difference in metres.

Assumptions:
- Scalar diffraction (polarization ignored)
- Paraxial approximation (valid for f/# > 2)
- Spatially coherent pupil

See RADIANT_Spatial_Complete.md §3.1 for the full derivation.
See also ``psf_poly.py`` for polychromatic PSF.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from radiant.optics.pupil_amplitude import make_pupil_amplitude
from radiant.optics.pupil_phase import make_pupil_phase, make_pupil_phase_zernike
from radiant.optics.sampling import PSFSamplingConfig
from radiant.optics.wavefront import WavefrontError, WfeMode


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
