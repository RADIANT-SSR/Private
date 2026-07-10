"""EE_box computation from the EffectivePSF.

EE_box is the fraction of PSF energy enclosed in a box matching the
detector pixel footprint. It couples the spatial model to the
radiometric model for point-source and sub-pixel targets.

Per CLAUDE.md Rule 9, EE_box is applied exactly once, in
SpectralIntegrationStage only, and never to the background term.

See RADIANT_Spatial_Complete.md §2 and RADIANT_Signal_Chain_Architecture.md.
"""

from __future__ import annotations

from radiant.optics.errors import OpticsValidationError
from radiant.optics.psf.effective import EffectivePSF


def compute_ee_box(
    psf: EffectivePSF,
    n_pixels: int = 1,
) -> float:
    """Compute EE_box from the EffectivePSF.

    Parameters
    ----------
    psf:
        The effective PSF (fully convolved, unit-volume normalised).
    n_pixels:
        Side length of the box in pixels (default 1 = single pixel).

    Returns
    -------
    float
        Fraction of PSF energy within the n×n pixel box.

    Raises
    ------
    ValueError
        If n_pixels < 1.
    """
    if n_pixels < 1:
        raise OpticsValidationError(f"n_pixels must be >= 1, got {n_pixels}")
    return psf.ensquared_energy_nxn(n_pixels)
