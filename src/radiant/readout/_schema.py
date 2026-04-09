"""Parameter definitions for the readout stage (2B.4 minimum subset).

Only the parameters needed by :mod:`radiant.readout.read_noise` and
:mod:`radiant.readout.adc` are defined here. TDI, on-chip and off-chip
binning, coadds, two-stage saturation, and the full readout-order
canonical chain from ``docs/RADIANT_Detector_Complete.md`` §6 will
be added by later tasks.
"""

from __future__ import annotations

from radiant.core.parameters import ParameterDef

# ---------------------------------------------------------------------------
# Read noise (Gaussian 1σ stub)
# ---------------------------------------------------------------------------

READ_NOISE_E_RMS = ParameterDef(
    name="readout.read_noise_e_rms",
    description="Per-frame read noise delivered to the signal path [e- RMS].",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=5.0,
    bounds=(0.0, 1.0e4),
    tags=frozenset({"readout", "noise"}),
    default_justification="5 e- RMS is a typical post-CDS scientific CMOS read noise.",
)

# ---------------------------------------------------------------------------
# ADC
# ---------------------------------------------------------------------------

GAIN_E_PER_DN = ParameterDef(
    name="readout.gain_e_per_dn",
    description="System conversion gain: electrons per digital number (LSB).",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=1.0,
    bounds=(1.0e-3, 1.0e6),
    tags=frozenset({"readout", "adc"}),
    default_justification=(
        "Unit gain is the default for bit-limited-rather-than-noise-limited ADCs."
    ),
)

ADC_BITS = ParameterDef(
    name="readout.adc_bits",
    description="ADC bit depth.",
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=16,
    bounds=(4, 32),
    tags=frozenset({"readout", "adc"}),
    default_justification="16-bit is the most common bit depth for scientific cameras.",
)


ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    READ_NOISE_E_RMS,
    GAIN_E_PER_DN,
    ADC_BITS,
)
