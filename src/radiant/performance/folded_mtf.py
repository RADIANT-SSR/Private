"""Aliased (folded) MTF for undersampled systems.

For undersampled detectors (Q < 1), scene spatial frequencies above the
Nyquist frequency fold back into the baseband, creating spurious apparent
contrast.  The folded MTF captures this aliasing by summing all aliased
copies of the optical MTF::

    MTF_folded(f) = Σ_{k=-N}^{+N}  MTF_optical(|f + k × f_Nyquist|)

where ``f_Nyquist = 1 / (2 × pixel_pitch)``.

For well-sampled systems (Q >> 1), the optical MTF falls to zero well
below ``f_Nyquist``, so the folded MTF equals the optical MTF.

The **alias fraction** at each frequency quantifies how much of the
folded response is due to aliasing rather than true signal::

    alias_fraction(f) = (MTF_folded(f) - MTF_optical(f)) / MTF_folded(f)

Reference: Holst, *Electro-Optical Imaging System Performance*, Ch. 7.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class FoldedMTFResult:
    """Result of folded MTF computation.

    Parameters
    ----------
    freq:
        Spatial frequency array [cycles/m], same as input.
    mtf_folded:
        Folded (aliased) MTF values at each frequency.
    alias_fraction:
        Fraction of folded MTF due to aliasing at each frequency.
        Zero for well-sampled systems, approaches 1.0 when aliasing
        dominates.
    n_folds:
        Number of fold orders summed (±n_folds).
    """

    freq: npt.NDArray[np.float64]
    mtf_folded: npt.NDArray[np.float64]
    alias_fraction: npt.NDArray[np.float64]
    n_folds: int


def compute_folded_mtf(
    freq_cy_m: npt.NDArray[np.float64],
    mtf_values: npt.NDArray[np.float64],
    f_nyquist_cy_m: float,
    n_folds: int = 3,
) -> FoldedMTFResult:
    """Compute the aliased (folded) MTF.

    Sums ``2 * n_folds + 1`` copies of the optical MTF shifted by
    integer multiples of ``f_Nyquist``.  The optical MTF is interpolated
    (zero outside its defined range) at each shifted frequency.

    Parameters
    ----------
    freq_cy_m:
        Spatial frequency grid [cycles/m] at which to evaluate.
    mtf_values:
        Optical (pre-sampling) MTF values at ``freq_cy_m``.
    f_nyquist_cy_m:
        Nyquist frequency [cycles/m] = 1 / (2 × pixel_pitch).
    n_folds:
        Number of aliasing orders to sum (default 3 → k = -3..+3).
        Set to 0 to return the optical MTF unchanged.

    Returns
    -------
    FoldedMTFResult
        Folded MTF curve, alias fraction, and metadata.

    Raises
    ------
    ValueError
        If ``f_nyquist_cy_m <= 0`` or MTF values are negative.
    """
    freq_cy_m = np.asarray(freq_cy_m, dtype=np.float64)
    mtf_values = np.asarray(mtf_values, dtype=np.float64)

    if f_nyquist_cy_m <= 0.0:
        raise ValueError(
            f"f_nyquist_cy_m must be positive, got {f_nyquist_cy_m}. "
            f"Check that pixel_pitch_m is positive."
        )

    if np.any(mtf_values < 0.0):
        raise ValueError(
            "MTF values must be non-negative. Negative values indicate "
            "a computation error upstream."
        )

    if len(freq_cy_m) == 0:
        return FoldedMTFResult(
            freq=freq_cy_m,
            mtf_folded=np.array([], dtype=np.float64),
            alias_fraction=np.array([], dtype=np.float64),
            n_folds=n_folds,
        )

    if n_folds == 0:
        return FoldedMTFResult(
            freq=freq_cy_m.copy(),
            mtf_folded=mtf_values.copy(),
            alias_fraction=np.zeros_like(mtf_values),
            n_folds=0,
        )

    # Accumulate folded MTF: sum MTF_optical(|f + k*f_Nyquist|)
    # for k = -n_folds ... +n_folds.
    mtf_folded = np.zeros_like(freq_cy_m)

    for k in range(-n_folds, n_folds + 1):
        shifted_freq = np.abs(freq_cy_m + k * f_nyquist_cy_m)
        # Interpolate optical MTF at shifted frequencies.
        # Values outside the defined range are zero (MTF→0 beyond cutoff).
        mtf_shifted = np.interp(
            shifted_freq, freq_cy_m, mtf_values,
            left=mtf_values[0] if len(mtf_values) > 0 else 0.0,
            right=0.0,
        )
        mtf_folded += mtf_shifted

    # Alias fraction = (folded - optical) / folded.
    # Avoid division by zero where folded MTF is zero.
    alias_fraction = np.zeros_like(mtf_folded)
    nonzero = mtf_folded > 0.0
    alias_fraction[nonzero] = (
        (mtf_folded[nonzero] - mtf_values[nonzero]) / mtf_folded[nonzero]
    )

    return FoldedMTFResult(
        freq=freq_cy_m.copy(),
        mtf_folded=mtf_folded,
        alias_fraction=alias_fraction,
        n_folds=n_folds,
    )
