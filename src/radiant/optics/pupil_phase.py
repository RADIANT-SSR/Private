"""Wavefront phase screen generation — Zernike-based, deterministic.

Generates the phase component ``phi(x, y)`` of the complex pupil
function ``P = A * exp(i * phi)``.  Two entry points:

- ``make_pupil_phase_zernike``: deterministic phase from Zernike
  polynomial coefficients (correct PSF shape per aberration type).
- ``make_pupil_phase_for_wfe``: the single WavefrontError dispatch used
  by BOTH the PSF path and the MTF product path, so a given WFE builds
  the identical pupil phase on both (Rule 4; CU-058).

A ``scalar_rms`` WFE is expanded over a fixed low-order Zernike set
(Noll Z4–Z11, equal RMS per term — see ``scalar_rms.py``) and enters
through the same Zernike path, so the reference→operating wavelength
rescale applies to every mode (CU-355; the pre-fix white-noise screen
ignored wavelength and put all its variance at the grid sample scale).

See RADIANT_Spatial_Complete.md section 3.3.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from radiant.optics.scalar_rms import scalar_rms_zernike_coeffs
from radiant.optics.zernike_opd import evaluate_zernike_opd

if TYPE_CHECKING:
    from radiant.optics.wavefront import WavefrontError

logger = logging.getLogger(__name__)


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


def make_pupil_phase_for_wfe(
    npix: int,
    wfe: WavefrontError | None,
    operating_wavelength_m: float,
    obscuration_ratio: float = 0.0,
) -> npt.NDArray[np.float64]:
    """Pupil phase for a WavefrontError — the single dispatch for both paths.

    Both the PSF path (``psf_mono.compute_psf``) and the MTF product path
    (``pupil_mtf``) build their complex pupil through this one function, so
    a given ``WavefrontError`` produces the *identical* phase screen on both
    paths — the construction Rule 4's consistency invariant relies on
    (CU-058).

    Dispatch:

    - ``None`` → zero phase (diffraction-limited).
    - ``SCALAR_RMS`` → deterministic low-order Zernike expansion of the RMS
      budget (Noll Z4–Z11, ``scalar_rms.scalar_rms_zernike_coeffs``; CU-355).
      If the WFE also carries ``zernike_coeffs`` (e.g. defocus folded in as
      Noll Z4 by the optics stage), those coefficients are **added** to the
      expansion so budget + fold live in one pupil phase.
    - ``ZERNIKE`` → deterministic Zernike phase.

    All modes convert waves at the WFE's reference wavelength to radians at
    ``operating_wavelength_m`` (constant OPD, wavelength-dependent phase).

    Raises
    ------
    NotImplementedError
        For modes with no pupil-phase representation (``OPD_MAP``,
        ``FIELD_DEPENDENT`` — the stage resolves the latter to ZERNIKE
        before PSF/MTF construction).
    """
    # Runtime import: wavefront.py does not import pupil_phase, no cycle.
    from radiant.optics.wavefront import WfeMode

    if wfe is None:
        return np.zeros((npix, npix), dtype=np.float64)

    if wfe.mode == WfeMode.SCALAR_RMS:
        rms = wfe.rms_waves if wfe.rms_waves is not None else 0.0
        coeffs = scalar_rms_zernike_coeffs(rms, obscuration_ratio)
        if wfe.zernike_coeffs:
            for j, c in wfe.zernike_coeffs.items():
                coeffs[j] = coeffs.get(j, 0.0) + c
        if not coeffs:
            return np.zeros((npix, npix), dtype=np.float64)
        return make_pupil_phase_zernike(
            npix,
            coeffs,
            reference_wavelength_m=wfe.reference_wavelength_um * 1e-6,
            operating_wavelength_m=operating_wavelength_m,
            obscuration_ratio=obscuration_ratio,
        )

    if wfe.mode == WfeMode.ZERNIKE:
        assert wfe.zernike_coeffs is not None
        return make_pupil_phase_zernike(
            npix,
            wfe.zernike_coeffs,
            reference_wavelength_m=wfe.reference_wavelength_um * 1e-6,
            operating_wavelength_m=operating_wavelength_m,
            obscuration_ratio=obscuration_ratio,
        )

    raise NotImplementedError(
        f"WFE mode {wfe.mode.value!r} has no pupil-phase representation. "
        f"Supported modes: scalar_rms, zernike."
    )
