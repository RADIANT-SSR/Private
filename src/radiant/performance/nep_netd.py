"""Noise-equivalent power (NEP) ⇄ noise-equivalent temperature (NETD).

NETD is the target temperature difference that produces SNR = 1. It is the
NEP referred to temperature through the rate at which optical power on the
detector changes with target temperature:

    NETD = NEP / (dP/dT)         [K]
    NEP  = NETD · (dP/dT)        [W]

where ``dP/dT`` [W/K] is the derivative of the in-band optical power
reaching the detector with respect to target temperature — the same
sensitivity that drives the electron-domain NEDT
(:mod:`radiant.performance.nedt`), here in the optical-power domain.

Scenario 6.1 (Dr. Chen) converts a datasheet NETD to NEP (and thence D*);
scenario 4.5 (Lisa) inverts a vendor microbolometer NETD into the power
noise floor for an altitude trade.
"""

from __future__ import annotations

from radiant.core.exceptions import RadiantError

__all__ = ["NepNetdError", "nep_from_netd", "netd_from_nep"]


class NepNetdError(RadiantError):
    """Raised for out-of-range NEP/NETD conversion inputs."""


def netd_from_nep(nep_w: float, dp_dt_w_per_K: float) -> float:
    """NETD [K] from NEP [W] and the optical-power temperature derivative.

    ``NETD = NEP / (dP/dT)``.
    """
    if nep_w < 0.0:
        raise NepNetdError(f"nep_w must be ≥ 0, got {nep_w}.")
    if dp_dt_w_per_K <= 0.0:
        raise NepNetdError(
            f"dp_dt_w_per_K must be > 0, got {dp_dt_w_per_K} "
            "(no thermal sensitivity → NETD undefined)."
        )
    return nep_w / dp_dt_w_per_K


def nep_from_netd(netd_K: float, dp_dt_w_per_K: float) -> float:
    """NEP [W] from NETD [K] and the optical-power temperature derivative.

    ``NEP = NETD · (dP/dT)``.
    """
    if netd_K < 0.0:
        raise NepNetdError(f"netd_K must be ≥ 0, got {netd_K}.")
    if dp_dt_w_per_K <= 0.0:
        raise NepNetdError(f"dp_dt_w_per_K must be > 0, got {dp_dt_w_per_K}.")
    return netd_K * dp_dt_w_per_K
