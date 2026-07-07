"""Parameter definitions for the detector stage.

Covers pixel geometry, QE, dark current, and all 16 noise source
parameters from ``docs/architecture/RADIANT_Detector_Complete.md`` §4 and §11.
"""

from __future__ import annotations

from radiant.core.parameters import ParameterDef

# ---------------------------------------------------------------------------
# Pixel geometry
# ---------------------------------------------------------------------------

PIXEL_PITCH_X = ParameterDef(
    name="detector.pixel_pitch_x_um",
    description="Pixel pitch along the cross-track (x) axis.",
    dtype=float,
    canonical_unit="m",
    input_unit="um",
    default=None,
    bounds=(0.1, 1000.0),
    tags=frozenset({"detector", "pixel"}),
)

PIXEL_PITCH_Y = ParameterDef(
    name="detector.pixel_pitch_y_um",
    description="Pixel pitch along the along-track (y) axis. Defaults to x pitch.",
    dtype=float,
    canonical_unit="m",
    input_unit="um",
    default=None,
    bounds=(0.1, 1000.0),
    tags=frozenset({"detector", "pixel"}),
)

FILL_FACTOR = ParameterDef(
    name="detector.fill_factor",
    description="Photosensitive fraction of the pixel cell.",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=1.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"detector", "pixel"}),
    default_justification="Most modern EO sensors have near-unity fill factor.",
)

# ---------------------------------------------------------------------------
# Quantum efficiency
# ---------------------------------------------------------------------------
#
# QE is specified exactly one of two ways:
#   - ``detector.qe_value`` — scalar QE, applied uniformly in wavelength.
#   - ``detector.qe_table_path`` — path to a wavelength-vs-QE table.
# Exactly one must be set; the stage wrapper (Phase 2C) will enforce the
# XOR via a ConsistencyGroup. At the primitives layer, both parameters
# default to ``None`` and the loader picks whichever is populated.

QE_VALUE = ParameterDef(
    name="detector.qe_value",
    description="Wavelength-independent scalar quantum efficiency.",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=None,
    bounds=(0.0, 1.0),
    tags=frozenset({"detector", "qe"}),
)

QE_TABLE_PATH = ParameterDef(
    name="detector.qe_table_path",
    description="Path to a wavelength-vs-QE table (loaded by SpectralDataStore).",
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"detector", "qe"}),
    default_justification="Empty string signals 'use qe_value instead'.",
)

# ---------------------------------------------------------------------------
# Dark current
# ---------------------------------------------------------------------------

DARK_RATE_E_PER_S = ParameterDef(
    name="detector.dark_rate_e_per_s",
    description="Dark current generation rate per pixel [e-/s].",
    dtype=float,
    canonical_unit="1/s",
    input_unit="1/s",
    default=100.0,
    bounds=(0.0, 1e9),
    tags=frozenset({"detector", "noise", "dark"}),
    default_justification="Order-of-magnitude room-temperature Si CCD reference.",
)

DARK_REFERENCE_TEMP = ParameterDef(
    name="detector.dark_reference_temperature_K",
    description="Temperature at which dark_rate_e_per_s is specified [K].",
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=300.0,
    bounds=(1.0, 500.0),
    tags=frozenset({"detector", "dark"}),
)

DARK_ACTIVATION_EV = ParameterDef(
    name="detector.dark_activation_energy_eV",
    description=(
        "Arrhenius activation energy for dark-rate temperature scaling. Zero disables scaling."
    ),
    dtype=float,
    canonical_unit="eV",
    input_unit="eV",
    default=0.0,
    bounds=(0.0, 5.0),
    tags=frozenset({"detector", "dark"}),
)


# ---------------------------------------------------------------------------
# Detector temperature
# ---------------------------------------------------------------------------

DETECTOR_TEMPERATURE_K = ParameterDef(
    name="detector.detector_temperature_K",
    description="Detector operating temperature [K].",
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=77.0,
    bounds=(1.0, 500.0),
    tags=frozenset({"detector", "temperature"}),
    default_justification="77 K is standard LN₂ cooling for IR detectors.",
)

# ---------------------------------------------------------------------------
# Detector-material noise parameters (§4, terms 6-8)
# ---------------------------------------------------------------------------

GR_FACTOR = ParameterDef(
    name="detector.gr_factor",
    description="G-R noise factor (0 = disabled, 1 = classic HgCdTe).",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 10.0),
    tags=frozenset({"detector", "noise"}),
)

R0A_OHM_CM2 = ParameterDef(
    name="detector.r0a_ohm_cm2",
    description="Detector R₀A product [Ω·cm²]. Zero disables Johnson noise.",
    dtype=float,
    canonical_unit="ohm_cm2",
    input_unit="ohm_cm2",
    default=0.0,
    bounds=(0.0, 1e12),
    tags=frozenset({"detector", "noise"}),
)

FLICKER_K = ParameterDef(
    name="detector.flicker_K",
    description="1/f flicker noise coefficient [e-²]. Zero disables.",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 1e12),
    tags=frozenset({"detector", "noise"}),
)

FLICKER_F_LOW = ParameterDef(
    name="detector.flicker_f_low_hz",
    description="Lower frequency bound for 1/f integration [Hz].",
    dtype=float,
    canonical_unit="Hz",
    input_unit="Hz",
    default=0.01,
    bounds=(1e-6, 1e6),
    tags=frozenset({"detector", "noise"}),
)

FLICKER_F_HIGH = ParameterDef(
    name="detector.flicker_f_high_hz",
    description="Upper frequency bound for 1/f integration [Hz].",
    dtype=float,
    canonical_unit="Hz",
    input_unit="Hz",
    default=1.0e6,
    bounds=(1e-3, 1e9),
    tags=frozenset({"detector", "noise"}),
)

# ---------------------------------------------------------------------------
# Fixed-pattern noise parameters (§4, terms 12-14)
# ---------------------------------------------------------------------------

PRNU_PCT = ParameterDef(
    name="detector.prnu_pct",
    description="Photo-response non-uniformity [%]. Zero disables.",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 100.0),
    tags=frozenset({"detector", "noise", "spatial"}),
)

DSNU_E_RMS = ParameterDef(
    name="detector.dsnu_e_rms",
    description="Dark-signal non-uniformity [e- RMS]. Zero disables.",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 1e6),
    tags=frozenset({"detector", "noise", "spatial"}),
)

NOISE_REGIME = ParameterDef(
    name="detector.noise_regime",
    description=(
        "Noise regime: 'imaging' (temporal only, FPN calibrated out) "
        "or 'detection' (temporal + spatial)."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="imaging",
    tags=frozenset({"detector", "noise"}),
)

CLUTTER_SIGMA = ParameterDef(
    name="detector.clutter_sigma",
    description="Scene clutter coefficient (fractional). Zero disables.",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"detector", "noise", "spatial"}),
)

# ---------------------------------------------------------------------------
# Persistence and glow (§4, terms 15-16)
# ---------------------------------------------------------------------------

PERSISTENCE_FRACTION = ParameterDef(
    name="detector.persistence_fraction",
    description="Fraction of prior-frame signal that persists. Zero disables.",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"detector", "noise"}),
)

PERSISTENCE_TAU_S = ParameterDef(
    name="detector.persistence_tau_s",
    description="Persistence time constant [s].",
    dtype=float,
    canonical_unit="s",
    input_unit="s",
    default=1.0,
    bounds=(1e-6, 1e3),
    tags=frozenset({"detector", "noise"}),
)

PRIOR_SIGNAL_E = ParameterDef(
    name="detector.prior_signal_e",
    description="Signal electrons from prior frame (for persistence). Zero disables.",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 1e9),
    tags=frozenset({"detector", "noise"}),
)

GLOW_E_PER_S = ParameterDef(
    name="detector.glow_e_per_s",
    description="Detector/ROIC glow rate [e-/s/pixel]. Zero disables.",
    dtype=float,
    canonical_unit="1/s",
    input_unit="1/s",
    default=0.0,
    bounds=(0.0, 1e6),
    tags=frozenset({"detector", "noise"}),
)

# ---------------------------------------------------------------------------
# IPC coupling
# ---------------------------------------------------------------------------

IPC_COUPLING = ParameterDef(
    name="detector.ipc_coupling",
    description="Inter-pixel capacitance coupling fraction α [0, 0.25).",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 0.25),
    tags=frozenset({"detector", "spatial"}),
)

CHARGE_DIFFUSION_LENGTH_M = ParameterDef(
    name="detector.charge_diffusion_length_m",
    description="RMS charge diffusion length [m]. Zero disables diffusion MTF.",
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 1e-3),
    tags=frozenset({"detector", "spatial"}),
    default_justification="Zero = no charge diffusion (ideal detector).",
)

N_PIXELS_CROSS = ParameterDef(
    name="detector.n_pixels_cross",
    description="Number of detector pixels in the cross-track direction.",
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=0,
    bounds=(0, 1_000_000),
    tags=frozenset({"detector", "pixel", "geometry"}),
    default_justification="0 = not set; swath width skipped.",
)

ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    PIXEL_PITCH_X,
    PIXEL_PITCH_Y,
    FILL_FACTOR,
    QE_VALUE,
    QE_TABLE_PATH,
    DARK_RATE_E_PER_S,
    DARK_REFERENCE_TEMP,
    DARK_ACTIVATION_EV,
    DETECTOR_TEMPERATURE_K,
    GR_FACTOR,
    R0A_OHM_CM2,
    FLICKER_K,
    FLICKER_F_LOW,
    FLICKER_F_HIGH,
    PRNU_PCT,
    DSNU_E_RMS,
    NOISE_REGIME,
    CLUTTER_SIGMA,
    PERSISTENCE_FRACTION,
    PERSISTENCE_TAU_S,
    PRIOR_SIGNAL_E,
    GLOW_E_PER_S,
    IPC_COUPLING,
    CHARGE_DIFFUSION_LENGTH_M,
    N_PIXELS_CROSS,
)
