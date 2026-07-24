"""Parameter definitions for the readout stage.

Covers read noise, ADC, gain, TDI, binning, coadds, saturation,
and CDS per ``docs/architecture/RADIANT_Detector_Complete.md`` §6-§9.
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


# ---------------------------------------------------------------------------
# Well capacity and saturation
# ---------------------------------------------------------------------------

FULL_WELL_CAPACITY_E = ParameterDef(
    name="readout.full_well_capacity_e",
    description="Full well capacity per pixel [e-].",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=100000.0,
    bounds=(100.0, 1e8),
    tags=frozenset({"readout", "saturation"}),
    default_justification="100 ke- is typical for scientific CMOS and cooled IR FPAs.",
)

# ---------------------------------------------------------------------------
# CDS
# ---------------------------------------------------------------------------

CDS_ENABLED = ParameterDef(
    name="readout.cds_enabled",
    description="Correlated double sampling enabled (1=yes, 0=no).",
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=1,
    tags=frozenset({"readout", "cds"}),
    default_justification="Most modern ROICs use CDS.",
)

NODE_CAPACITANCE_F = ParameterDef(
    name="readout.node_capacitance_F",
    description="Sense-node capacitance [F]. Zero disables kTC noise.",
    dtype=float,
    canonical_unit="F",
    input_unit="F",
    default=0.0,
    bounds=(0.0, 1e-9),
    tags=frozenset({"readout", "noise"}),
)

# ---------------------------------------------------------------------------
# TDI
# ---------------------------------------------------------------------------

N_TDI = ParameterDef(
    name="readout.n_tdi",
    description="Number of TDI stages. 1 = no TDI.",
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=1,
    bounds=(1, 1000),
    tags=frozenset({"readout", "tdi"}),
)

TDI_MODE = ParameterDef(
    name="readout.tdi_mode",
    description=(
        "TDI readout mode: 'analog' (single readout after charge accumulation) "
        "or 'digital' (each stage read independently, summed digitally)."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="analog",
    enum_values=("analog", "digital"),
    tags=frozenset({"readout", "tdi"}),
    default_justification="Analog TDI is the traditional CCD-based approach.",
)

TDI_MISALIGN_PIXELS = ParameterDef(
    name="readout.tdi_misalign_pixels",
    description="Cross-scan TDI misalignment in pixel units. Zero = perfect alignment.",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 10.0),
    tags=frozenset({"readout", "tdi", "spatial"}),
    default_justification="Zero = no cross-scan misalignment.",
)

# ---------------------------------------------------------------------------
# Binning
# ---------------------------------------------------------------------------

BINNING_X_ONCHIP = ParameterDef(
    name="readout.binning_x_onchip",
    description="On-chip binning factor along x. 1 = no binning.",
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=1,
    bounds=(1, 64),
    tags=frozenset({"readout", "binning"}),
)

BINNING_Y_ONCHIP = ParameterDef(
    name="readout.binning_y_onchip",
    description="On-chip binning factor along y. 1 = no binning.",
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=1,
    bounds=(1, 64),
    tags=frozenset({"readout", "binning"}),
)

BINNING_X_OFFCHIP = ParameterDef(
    name="readout.binning_x_offchip",
    description="Off-chip binning factor along x. 1 = no binning.",
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=1,
    bounds=(1, 64),
    tags=frozenset({"readout", "binning"}),
)

BINNING_Y_OFFCHIP = ParameterDef(
    name="readout.binning_y_offchip",
    description="Off-chip binning factor along y. 1 = no binning.",
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=1,
    bounds=(1, 64),
    tags=frozenset({"readout", "binning"}),
)

# ---------------------------------------------------------------------------
# Coadds
# ---------------------------------------------------------------------------

N_COADDS = ParameterDef(
    name="readout.n_coadds",
    description="Number of coadded frames. 1 = no coadd.",
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=1,
    bounds=(1, 10000),
    tags=frozenset({"readout", "coadd"}),
)

COADD_MODE = ParameterDef(
    name="readout.coadd_mode",
    description="Coadd combination mode: 'sum', 'average', or 'median'.",
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="sum",
    tags=frozenset({"readout", "coadd"}),
)

ELECTRONICS_SIGMA_UM = ParameterDef(
    name="readout.electronics_sigma_um",
    description=(
        "Electronics MTF: equivalent Gaussian blur sigma on the focal "
        "plane [µm] from finite amplifier bandwidth at the pixel clock "
        "rate. Blurs the readout (cross-scan, x) axis only. Zero "
        "(default) = ideal electronics, no blur. Enters both the "
        "EffectivePSF (kernel) and the MTF product (analytic term) per "
        "Rule 4."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="um",
    default=0.0,
    bounds=(0.0, 100.0),
    tags=frozenset({"readout", "mtf"}),
    default_justification="0.0 = ideal electronics (backward compatible).",
)

FRAME_PERIOD_S = ParameterDef(
    name="readout.frame_period_s",
    description=(
        "Frame period [s]: the time between frame starts, stored "
        "independently of the integration time "
        "(spectral_integration.integration_time_s) per RADIANT_Conventions.md "
        "§4. Frame rate = 1/frame_period and duty cycle = t_int/frame_period "
        "are derived by radiant.readout.frame_timing and published in "
        "stage_outputs['readout']. Default 0.0 means 'unset': the frame period "
        "defaults to the integration time (frame rate = 1/t_int, duty cycle = "
        "1.0) with a logged warning. A duty cycle > 1 (integration longer than "
        "the frame period) is rejected."
    ),
    dtype=float,
    canonical_unit="s",
    input_unit="s",
    default=0.0,
    bounds=(0.0, 1.0e6),
    tags=frozenset({"readout", "timing"}),
    default_justification=(
        "0.0 = unset: derive the frame period from the integration time "
        "(duty cycle 1.0), the backward-compatible continuous-readout case."
    ),
)

ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    READ_NOISE_E_RMS,
    GAIN_E_PER_DN,
    ADC_BITS,
    FULL_WELL_CAPACITY_E,
    CDS_ENABLED,
    NODE_CAPACITANCE_F,
    N_TDI,
    TDI_MODE,
    TDI_MISALIGN_PIXELS,
    BINNING_X_ONCHIP,
    BINNING_Y_ONCHIP,
    BINNING_X_OFFCHIP,
    BINNING_Y_OFFCHIP,
    N_COADDS,
    COADD_MODE,
    ELECTRONICS_SIGMA_UM,
    FRAME_PERIOD_S,
)
