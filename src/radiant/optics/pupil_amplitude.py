"""Circular pupil amplitude mask generation.

Generates the binary amplitude function ``A(x, y)`` for a circular
aperture with optional central obscuration and secondary-support spider
vanes.  The mask is centered on a square grid with normalised coordinates
``[-0.5, +0.5]``.

Because RADIANT derives BOTH the PSF (via FT of the complex pupil) and the
optical MTF (via pupil autocorrelation) from this one amplitude mask, any
feature added here enters both spatial paths automatically, satisfying the
dual-path consistency invariant (CLAUDE.md Rule 4).

See RADIANT_Spatial_Complete.md section 3.1.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class SpiderVaneSpec:
    """Secondary-support spider-vane geometry for the pupil mask.

    Attributes
    ----------
    n_struts:
        Number of radial support struts (0 = none). A 4-strut spider at
        the default offset is the familiar "+" that produces a four-point
        diffraction spike.
    width_frac:
        Strut width as a fraction of the pupil diameter (0 ≤ width_frac).
        The stage converts a physical strut width in metres to this
        fraction (``width_m / aperture_diameter_m``) at the boundary.
    angle_offset_deg:
        Rotation of the whole strut pattern about the optical axis [deg].
    """

    n_struts: int = 0
    width_frac: float = 0.0
    angle_offset_deg: float = 0.0

    @property
    def active(self) -> bool:
        """True when the spec actually removes pupil area."""
        return self.n_struts > 0 and self.width_frac > 0.0


def make_pupil_amplitude(
    npix: int,
    obscuration_ratio: float = 0.0,
    vanes: SpiderVaneSpec | None = None,
    mask_override: npt.NDArray[np.float64] | None = None,
) -> npt.NDArray[np.float64]:
    """Generate a circular pupil amplitude mask.

    The aperture is centered on the grid and has unit radius (fills
    the grid from -0.5 to +0.5 in normalised coordinates). The central
    obscuration is a concentric circle of radius ``obscuration_ratio``.
    Optional spider vanes are opaque radial struts from the centre outward.

    Parameters
    ----------
    npix:
        Side length of the square pupil grid.
    obscuration_ratio:
        D_secondary / D_primary. Must be in [0, 1).
    vanes:
        Optional :class:`SpiderVaneSpec`. ``None`` or an inactive spec
        (no struts / zero width) leaves the mask unchanged — so the
        default reproduces the historical unobscured/obscured pupil
        exactly.
    mask_override:
        Optional measured/arbitrary amplitude mask (segmented aperture,
        non-circular primary, wavefront-sensor pupil image). When given it
        **supersedes** the parametric circular/obscuration/vane geometry
        entirely — the caller owns the full aperture. Must be a
        ``(npix, npix)`` array of amplitudes in [0, 1]. ``None`` (default)
        keeps the parametric mask, so results are unchanged. (Gap 54.)

    Returns
    -------
    ndarray of shape (npix, npix)
        Binary amplitude: 1.0 in clear aperture, 0.0 outside / obscured /
        under a strut — or the supplied ``mask_override``.
    """
    if mask_override is not None:
        if mask_override.shape != (npix, npix):
            raise ValueError(
                f"mask_override shape {mask_override.shape} must equal (npix, npix) = "
                f"({npix}, {npix})."
            )
        if mask_override.min() < 0.0 or mask_override.max() > 1.0:
            raise ValueError("mask_override amplitudes must lie in [0, 1].")
        return mask_override.astype(np.float64, copy=True)

    if not (0.0 <= obscuration_ratio < 1.0):
        raise ValueError(f"obscuration_ratio must be in [0, 1), got {obscuration_ratio}")

    # Normalised coordinates: [-0.5, +0.5]
    x = np.linspace(-0.5, 0.5, npix, endpoint=False) + 0.5 / npix
    xx, yy = np.meshgrid(x, x, indexing="xy")
    r = np.sqrt(xx**2 + yy**2)

    mask = np.zeros((npix, npix), dtype=np.float64)
    mask[r <= 0.5] = 1.0
    if obscuration_ratio > 0.0:
        mask[r <= 0.5 * obscuration_ratio] = 0.0

    if vanes is not None and vanes.active:
        if vanes.width_frac < 0.0:
            raise ValueError(f"spider vane width_frac must be ≥ 0, got {vanes.width_frac}")
        half_w = 0.5 * vanes.width_frac
        for k in range(vanes.n_struts):
            theta = np.radians(vanes.angle_offset_deg + k * 360.0 / vanes.n_struts)
            u_x, u_y = np.cos(theta), np.sin(theta)
            # Projection along the strut direction (radially outward half-line)
            t = xx * u_x + yy * u_y
            # Perpendicular distance to the strut centre line
            d_perp = np.abs(xx * u_y - yy * u_x)
            strut = (d_perp <= half_w) & (t >= 0.0)
            mask[strut] = 0.0

    return mask
