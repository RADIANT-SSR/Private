"""ROIC noise sources (§4, terms 9–11).

Each function computes a single ROIC noise source in electrons RMS.
All are pure functions with no shared state.

Sources:
    read_noise_term      — Read noise passthrough
    ktc_reset_noise      — kTC reset noise: sqrt(kT·C) / q
    quantization_noise   — ADC quantization noise: LSB / sqrt(12)

See ``docs/architecture/RADIANT_Detector_Complete.md`` §4.
"""

from __future__ import annotations

import math

from radiant.core.constants import k_B, q
from radiant.detector.errors import DetectorValidationError


def read_noise_term(sigma_rms: float) -> float:
    """Read noise passthrough [e- RMS].

    The stored value is the effective per-frame read noise. CDS
    convention is handled by the readout stage.
    """
    if sigma_rms < 0.0:
        raise DetectorValidationError(f"read_noise_term: sigma_rms = {sigma_rms} < 0.")
    return sigma_rms


def ktc_reset_noise(node_capacitance_F: float, temp_K: float, cds_enabled: bool) -> float:
    """kTC reset noise: ``√(kT·C) / q`` [e- RMS].

    When CDS is enabled, kTC noise is fully suppressed (returns 0).

    Parameters
    ----------
    node_capacitance_F:
        Sense-node capacitance [F]. Zero disables.
    temp_K:
        Detector temperature [K].
    cds_enabled:
        If True, CDS suppresses kTC entirely.
    """
    if cds_enabled:
        return 0.0
    if node_capacitance_F <= 0.0:
        return 0.0
    if temp_K <= 0.0:
        return 0.0
    # σ_charge = √(kTC) in coulombs → divide by q for electrons
    return math.sqrt(k_B * temp_K * node_capacitance_F) / q


def quantization_noise(gain_e_per_dn: float) -> float:
    """ADC quantization noise: ``LSB / √12`` [e- RMS]."""
    if gain_e_per_dn <= 0.0:
        raise DetectorValidationError(
            f"quantization_noise: gain_e_per_dn = {gain_e_per_dn} must be > 0."
        )
    return gain_e_per_dn / math.sqrt(12.0)
