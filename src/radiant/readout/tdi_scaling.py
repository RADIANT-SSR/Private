"""TDI signal and noise scaling.

TDI accumulates signal from N stages. Different noise categories scale
differently through TDI accumulation:

- Signal: × N_tdi (linear accumulation)
- Shot noise: × √N_tdi (independent Poisson events)
- Read noise: × 1 (analog TDI) or × √N_tdi (digital TDI)
- FPN: × N_tdi (correlated across stages)

See §7 of ``docs/architecture/RADIANT_Detector_Complete.md``.
"""

from __future__ import annotations

from radiant.readout.errors import ReadoutValidationError


def tdi_scale_signal(signal_e: float, n_tdi: int) -> float:
    """Scale per-stage signal by TDI stage count: ``S × N_tdi``.

    TDI accumulates signal from N stages in the analog domain before
    a single readout.
    """
    if n_tdi < 1:
        raise ReadoutValidationError(f"tdi_scale_signal: n_tdi = {n_tdi} must be >= 1.")
    return signal_e * n_tdi


def tdi_scale_shot_noise(noise_e: float, n_tdi: int) -> float:
    """Scale shot-like noise by ``√N_tdi``.

    Independent Poisson events across N stages add in quadrature:
    ``σ_total = σ_per_stage × √N``.
    """
    if n_tdi < 1:
        raise ReadoutValidationError(f"tdi_scale_shot_noise: n_tdi = {n_tdi} must be >= 1.")
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
            raise ReadoutValidationError(f"tdi_scale_read_noise: n_tdi = {n_tdi} must be >= 1.")
        return noise_e * (n_tdi**0.5)
    return noise_e


def tdi_scale_fpn(noise_e: float, n_tdi: int) -> float:
    """Scale fixed-pattern noise by ``N_tdi``.

    FPN is correlated across TDI stages (same pixel column), so it
    scales linearly with the signal: ``σ × N``.
    """
    if n_tdi < 1:
        raise ReadoutValidationError(f"tdi_scale_fpn: n_tdi = {n_tdi} must be >= 1.")
    return noise_e * n_tdi
