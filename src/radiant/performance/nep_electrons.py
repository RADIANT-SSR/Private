"""Noise-equivalent power (NEP) ⇄ noise electrons.

Connects the optical-power figure of merit NEP to the electron-domain noise
the RADIANT chain models. For an integrating detector of quantum efficiency
η observing at wavelength λ over integration time t_int, the incident power
P produces ``n_e = η · P · λ/(hc) · t_int`` electrons. SNR = 1 (the NEP
condition) means the signal electrons equal the noise electrons σ_e, so:

    NEP = σ_e · h·c / (η · λ · t_int)        [W]
    σ_e = NEP · η · λ · t_int / (h·c)         [e-]

The integrating-detector noise bandwidth is ``Δf = 1/(2·t_int)`` — the
bridge to :mod:`radiant.performance.detectivity` (D*).

Scenario 6.1 (Dr. Chen) uses this to check a datasheet D*/NEP against the
chain's computed read/dark/shot noise in electrons.
"""

from __future__ import annotations

from radiant.core.constants import hc
from radiant.core.exceptions import RadiantError

__all__ = [
    "NepElectronsError",
    "integrating_bandwidth_hz",
    "nep_from_noise_electrons",
    "noise_electrons_from_nep",
]


class NepElectronsError(RadiantError):
    """Raised for out-of-range NEP/electron conversion inputs."""


def _validate(qe: float, wavelength_um: float, integration_time_s: float) -> None:
    if not 0.0 < qe <= 1.0:
        raise NepElectronsError(f"qe must be in (0, 1], got {qe}.")
    if wavelength_um <= 0.0:
        raise NepElectronsError(f"wavelength_um must be positive, got {wavelength_um}.")
    if integration_time_s <= 0.0:
        raise NepElectronsError(f"integration_time_s must be positive, got {integration_time_s}.")


def nep_from_noise_electrons(
    noise_e: float, qe: float, wavelength_um: float, integration_time_s: float
) -> float:
    """NEP [W] from noise electrons ``σ_e``.

    ``NEP = σ_e · h·c / (η · λ · t_int)``.
    """
    if noise_e < 0.0:
        raise NepElectronsError(f"noise_e must be ≥ 0, got {noise_e}.")
    _validate(qe, wavelength_um, integration_time_s)
    lam_m = wavelength_um * 1e-6
    return noise_e * hc / (qe * lam_m * integration_time_s)


def noise_electrons_from_nep(
    nep_w: float, qe: float, wavelength_um: float, integration_time_s: float
) -> float:
    """Noise electrons ``σ_e`` from NEP [W].

    ``σ_e = NEP · η · λ · t_int / (h·c)``.
    """
    if nep_w < 0.0:
        raise NepElectronsError(f"nep_w must be ≥ 0, got {nep_w}.")
    _validate(qe, wavelength_um, integration_time_s)
    lam_m = wavelength_um * 1e-6
    return nep_w * qe * lam_m * integration_time_s / hc


def integrating_bandwidth_hz(integration_time_s: float) -> float:
    """Noise-equivalent bandwidth ``Δf = 1/(2·t_int)`` [Hz] of an integrator."""
    if integration_time_s <= 0.0:
        raise NepElectronsError(f"integration_time_s must be positive, got {integration_time_s}.")
    return 1.0 / (2.0 * integration_time_s)
