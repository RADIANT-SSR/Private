"""Strehl ratio — Marechal approximation.

Estimates the Strehl ratio from RMS wavefront error::

    S = exp(-(2π · OPD_rms / λ)²)

where OPD_rms = WFE_rms_waves × λ_ref is the physical OPD in the same
units as λ.

Valid for WFE < ~λ/5 (Strehl > ~0.8).  For larger aberrations the
Marechal approximation underestimates Strehl but remains a useful
first-order metric.

Reference: Maréchal (1947); Born & Wolf, *Principles of Optics*, §9.
"""

from __future__ import annotations

import math


def compute_strehl(
    wfe_rms_waves: float,
    wfe_ref_wavelength_um: float,
    operating_wavelength_um: float,
) -> float:
    """Compute the Marechal Strehl ratio.

    Parameters
    ----------
    wfe_rms_waves : float
        RMS wavefront error in waves at the reference wavelength.
    wfe_ref_wavelength_um : float
        Reference wavelength at which WFE was measured [µm].
    operating_wavelength_um : float
        Operating (band-center) wavelength [µm].

    Returns
    -------
    float
        Strehl ratio in [0, 1].  Returns 1.0 for zero WFE.
    """
    if wfe_rms_waves == 0.0:
        return 1.0

    # OPD_rms in µm = WFE_rms_waves × λ_ref_µm
    opd_rms_um = wfe_rms_waves * wfe_ref_wavelength_um
    phase_variance = (2.0 * math.pi * opd_rms_um / operating_wavelength_um) ** 2
    return math.exp(-phase_variance)
