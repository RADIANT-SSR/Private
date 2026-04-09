"""Photon and dark shot noise.

Implements noise terms #1–#4 ("photon-shot family") and term #5
("dark_shot") from ``docs/RADIANT_Detector_Complete.md`` §4 in their
minimum form for the 2B.4 cut: Poisson statistics on a non-negative
electron count.

For a Poisson process with mean ``μ``, the variance equals ``μ`` and
the standard deviation equals ``√μ``. These helpers are scalar and
pure; they do not know the difference between a signal term and a
background term — the caller picks which electron count to pass in.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt


def shot_noise_e(electrons: float) -> float:
    """Return ``√electrons`` for a non-negative scalar electron count.

    Parameters
    ----------
    electrons:
        Non-negative scalar electron count ``N``. ``float`` — per-pixel.

    Returns
    -------
    float
        ``√N`` in electrons RMS.

    Raises
    ------
    ValueError
        If ``electrons`` is negative or non-finite.
    """
    if not math.isfinite(electrons):
        raise ValueError(
            f"shot_noise_e: electrons = {electrons} is non-finite. The "
            "caller must resolve NaN/inf before invoking shot-noise helpers."
        )
    if electrons < 0.0:
        raise ValueError(
            f"shot_noise_e: electrons = {electrons} is negative. Shot noise "
            "is defined only for non-negative counts. Check the upstream "
            "signal path for sign errors or unit mismatches."
        )
    return math.sqrt(electrons)


def shot_noise_e_array(
    electrons: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Elementwise ``√electrons`` for an array of per-pixel counts.

    Parameters
    ----------
    electrons:
        Non-negative ``np.ndarray`` of per-pixel electron counts.

    Returns
    -------
    np.ndarray
        Same shape, ``√electrons`` in electrons RMS.

    Raises
    ------
    ValueError
        If any element is negative or non-finite.
    """
    arr = np.asarray(electrons, dtype=np.float64)
    if not np.all(np.isfinite(arr)):
        raise ValueError(
            "shot_noise_e_array: input contains non-finite entries. The "
            "caller must resolve NaN/inf before invoking shot-noise helpers."
        )
    if np.any(arr < 0.0):
        bad = float(arr.min())
        raise ValueError(
            f"shot_noise_e_array: input has negative entries (min={bad}). "
            "Shot noise is defined only for non-negative counts."
        )
    return np.sqrt(arr)


def combine_in_quadrature(*sigmas_e: float) -> float:
    """Combine independent Gaussian-equivalent noise terms in quadrature.

    ``σ_total = √(Σ σᵢ²)``. Each input must be non-negative and finite.
    Centralised here because the readout stage needs it for the
    temporal vs. spatial split.
    """
    total_sq = 0.0
    for i, s in enumerate(sigmas_e):
        if not math.isfinite(s) or s < 0.0:
            raise ValueError(
                f"combine_in_quadrature: term[{i}] = {s} is invalid. "
                "Each noise term must be a non-negative finite RMS value."
            )
        total_sq += s * s
    return math.sqrt(total_sq)
