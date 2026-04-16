"""Sampling parameter Q — spatial sampling adequacy.

The sampling parameter Q characterises how well a detector samples the
optical point spread function::

    Q = λ · f/# / p

where λ is wavelength, f/# is the focal ratio, and p is the pixel pitch.

- Q > 1.5 : oversampled — PSF spans many pixels
- Q ≈ 1.0 : critically sampled (Nyquist)
- Q < 0.7 : undersampled / aliased
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SamplingResult:
    """Result of sampling parameter computation."""

    q_center: float
    """Q at band-center wavelength."""

    q_min: float
    """Q at the short-wavelength band edge (smallest Q, most undersampled)."""

    q_max: float
    """Q at the long-wavelength band edge (largest Q, most oversampled)."""


def compute_q(
    f_number: float,
    pitch_m: float,
    lambda_min_um: float,
    lambda_max_um: float,
) -> SamplingResult:
    """Compute the sampling parameter Q at band center and edges.

    Parameters
    ----------
    f_number : float
        Working f-number (dimensionless).
    pitch_m : float
        Pixel pitch [m].
    lambda_min_um : float
        Short-wavelength band edge [µm].
    lambda_max_um : float
        Long-wavelength band edge [µm].

    Returns
    -------
    SamplingResult
        Q at band center, band minimum, and band maximum.
    """
    pitch_um = pitch_m * 1e6  # convert m → µm for consistent units with λ

    lambda_center_um = 0.5 * (lambda_min_um + lambda_max_um)

    return SamplingResult(
        q_center=lambda_center_um * f_number / pitch_um,
        q_min=lambda_min_um * f_number / pitch_um,
        q_max=lambda_max_um * f_number / pitch_um,
    )
