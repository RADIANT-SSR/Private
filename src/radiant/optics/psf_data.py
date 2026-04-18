"""PSFData — immutable container for a raw optical PSF.

Wraps a 2-D PSF array with its sampling metadata and provides
methods to extract the MTF, encircled energy, and FWHM from the
raw (pre-degradation) optical PSF.

``PSFData`` is the output of the diffraction engine.
``EffectivePSF`` (in ``effective_psf.py``) is the post-degradation
single source of truth for spatial metrics.

See RADIANT_Spatial_Complete.md §2.
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
