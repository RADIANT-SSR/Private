"""Counting quantization noise — packet branch vs residue-ADC branch.

Implements ``docs/archive/Digital_Pixel_Readout_Plan.md`` §2.2 (Gap 117
Phase 1), rulings D2/D3 context. The quantization noise of the counting
chain depends on whether the analog residue is digitized:

- ``residue_readout = False`` — the sub-packet charge is discarded and DN
  is the bare counter word: the quantizer step is the packet itself,

      σ_q = Q_pkt / √12      [e- RMS]

- ``residue_readout = True`` — the residue passes through the **existing**
  analog ADC model (:mod:`radiant.readout.adc`) scoped to a full scale of
  one packet (ruling D2: residue gain = Q_pkt / 2^M e-/DN, M = adc_bits):

      σ_q = (Q_pkt / 2^M) / √12      [e- RMS]

Both are the standard uniform-quantizer result (RMS of a uniform
distribution over one step). The formula is a flux-ensemble statement:
valid when the signal spans at least several quantizer steps. In the
low-flux regime (Q_int ≲ Q_pkt without residue readout) the residue *is*
the signal and the uniform assumption degrades — see the Monte Carlo
regime tests.
"""

from __future__ import annotations

import math

from radiant.readout.adc import AnalogToDigital
from radiant.readout.errors import ReadoutValidationError


def _validate_packet(count_packet_e: float) -> None:
    if not math.isfinite(count_packet_e) or count_packet_e <= 0.0:
        raise ReadoutValidationError(
            f"count_packet_e = {count_packet_e} e- is invalid: quantization "
            f"noise needs a positive finite charge packet (0.0 is the "
            f"schema's 'unset' sentinel — set readout.count_packet_e first)."
        )


def residue_adc_gain_e_per_dn(count_packet_e: float, adc_bits: int) -> float:
    """Residue-ADC conversion gain ``Q_pkt / 2^M`` [e-/DN] (ruling D2).

    The residue ADC's full scale is one packet: M bits span [0, Q_pkt).
    """
    _validate_packet(count_packet_e)
    if adc_bits < 1:
        raise ReadoutValidationError(
            f"adc_bits = {adc_bits} is invalid: the residue ADC needs at "
            f"least one bit to digitize the sub-packet charge."
        )
    return count_packet_e / float(1 << adc_bits)


def counting_quantization_noise_e(
    count_packet_e: float,
    *,
    residue_readout: bool,
    adc_bits: int,
) -> float:
    """Quantization noise of the counting chain [e- RMS].

    Parameters
    ----------
    count_packet_e:
        Charge packet per count Q_pkt [e-], > 0.
    residue_readout:
        Whether the analog residue is digitized (plan §2.2 branch).
    adc_bits:
        Residue-ADC bit depth M. Consulted only when ``residue_readout``
        is True — the bare counter never sees the ADC.
    """
    _validate_packet(count_packet_e)
    if not residue_readout:
        # Quantizer step = one packet; uniform residue on [0, Q_pkt).
        return count_packet_e / math.sqrt(12.0)
    # Residue branch: the existing ADC model, full scale = one packet.
    adc = AnalogToDigital(
        gain_e_per_dn=residue_adc_gain_e_per_dn(count_packet_e, adc_bits),
        n_bits=adc_bits,
        name="residue_adc",
    )
    return adc.quantization_noise_e()
