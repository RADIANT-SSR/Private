"""TDI misalignment MTF.

Time-delay-and-integration (TDI) accumulates signal across multiple
detector rows. If the rows are not perfectly aligned to the scan
direction, the misalignment produces a smear-like blur:

    MTF_tdi(f) = |sinc(π · f · misalign)|

where ``misalign`` is the cross-scan misalignment on the focal plane [m].

TDI is a readout-architecture concern and lives in the readout stage
per the RADIANT file tree.

See RADIANT_Spatial_Complete.md §6 (step 7).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def tdi_misalign_mtf_1d(
    freq: npt.NDArray[np.float64],
    misalign_m: float,
) -> npt.NDArray[np.float64]:
    """Compute the 1-D TDI misalignment MTF.

    Parameters
    ----------
    freq:
        Spatial frequencies [cycles/m].
    misalign_m:
        Cross-scan misalignment on the focal plane [m].
        Must be non-negative.

    Returns
    -------
    ndarray
        |sinc(π · f · misalign)| at each frequency.
        Returns all-ones if misalign_m is zero (perfect alignment).

    Raises
    ------
    ValueError
        If misalign_m is negative.
    """
    if misalign_m < 0.0:
        raise ValueError(f"misalign_m must be non-negative, got {misalign_m}")
    if misalign_m == 0.0:
        return np.ones_like(freq)
    return np.abs(np.sinc(freq * misalign_m))


def tdi_misalign_m(
    misalign_pixels: float,
    pixel_pitch_m: float,
) -> float:
    """Convert TDI misalignment from pixels to metres.

    Parameters
    ----------
    misalign_pixels:
        Cross-scan misalignment in pixel units.
    pixel_pitch_m:
        Pixel pitch [m].

    Returns
    -------
    float
        Misalignment in metres.
    """
    if pixel_pitch_m <= 0.0:
        raise ValueError(f"pixel_pitch_m must be positive, got {pixel_pitch_m}")
    return abs(misalign_pixels) * pixel_pitch_m


# ---------------------------------------------------------------------------
# TDI signal and noise scaling (§7 of Detector Complete)
# ---------------------------------------------------------------------------


def tdi_scale_signal(signal_e: float, n_tdi: int) -> float:
    """Scale per-stage signal by TDI stage count: ``S × N_tdi``.

    TDI accumulates signal from N stages in the analog domain before
    a single readout.
    """
    if n_tdi < 1:
        raise ValueError(f"tdi_scale_signal: n_tdi = {n_tdi} must be >= 1.")
    return signal_e * n_tdi


def tdi_scale_shot_noise(noise_e: float, n_tdi: int) -> float:
    """Scale shot-like noise by ``√N_tdi``.

    Independent Poisson events across N stages add in quadrature:
    ``σ_total = σ_per_stage × √N``.
    """
    if n_tdi < 1:
        raise ValueError(f"tdi_scale_shot_noise: n_tdi = {n_tdi} must be >= 1.")
    return noise_e * (n_tdi**0.5)


def tdi_scale_read_noise(noise_e: float, n_tdi: int = 1, digital: bool = False) -> float:
    """Scale read noise through TDI.

    Analog TDI (default): charge is accumulated on-chip with a single
    readout → ``σ × 1``. This is the classic √N SNR improvement.

    Digital TDI: each of N stages is read independently and summed
    digitally → ``σ × √N`` (N independent readouts).

    Parameters
    ----------
    noise_e:
        Per-readout read noise [e- RMS].
    n_tdi:
        Number of TDI stages (only used when ``digital=True``).
    digital:
        If True, use digital-TDI scaling (√N).
    """
    if digital:
        if n_tdi < 1:
            raise ValueError(f"tdi_scale_read_noise: n_tdi = {n_tdi} must be >= 1.")
        return noise_e * (n_tdi**0.5)
    return noise_e


def tdi_scale_fpn(noise_e: float, n_tdi: int) -> float:
    """Scale fixed-pattern noise by ``N_tdi``.

    FPN is correlated across TDI stages (same pixel column), so it
    scales linearly with the signal: ``σ × N``.
    """
    if n_tdi < 1:
        raise ValueError(f"tdi_scale_fpn: n_tdi = {n_tdi} must be >= 1.")
    return noise_e * n_tdi
