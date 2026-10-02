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
    description=(
        "Pixel pitch along the along-track (y) axis. Required — there is no "
        "'defaults to x pitch' fallback; set it explicitly (equal to "
        "pixel_pitch_x_um for square pixels)."
    ),
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
# Pixel sampling phase — straddle factor (Gap 129)
# ---------------------------------------------------------------------------
#
# Where the geometric image of a point-source / sub-pixel target lands on the
# pixel grid. The EE_box the chain applies (Rule 9) is evaluated at this phase:
# ``average`` is the expectation over a source uniformly placed across one
# pitch (the shipped behaviour before Gap 129 — rect ⊛ rect = triangle),
# ``centered`` puts the image on a pixel centre, ``worst_case`` on a four-pixel
# corner, ``specified`` at (pixel_phase_x, pixel_phase_y) pitches from the
# centre. Ignored in the extended regime (EE_box ≡ 1). Owned here because the
# grid is the detector's and the box is defined by pitch + fill factor above;
# evaluated in PlatformStage from the fully degraded PSF.

PIXEL_PHASE_MODE = ParameterDef(
    name="detector.pixel_phase_mode",
    description=(
        "Pixel sampling phase (straddle) convention for point-source / sub-pixel "
        "EE_box: average (uniform over one pitch — expectation), centered (image on "
        "a pixel centre), worst_case (image on a four-pixel corner), specified "
        "(pixel_phase_x / pixel_phase_y)."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="average",
    enum_values=("average", "centered", "worst_case", "specified"),
    tags=frozenset({"detector", "pixel", "spatial"}),
    default_justification=(
        "The phase average is the expected signal for a randomly placed source and "
        "is bit-identical to the pre-Gap-129 chain value."
    ),
)

PIXEL_PHASE_X = ParameterDef(
    name="detector.pixel_phase_x",
    description=(
        "Cross-track offset of the geometric image point from the pixel centre, as a "
        "fraction of the pixel pitch (0 = centred, ±0.5 = pixel edge). Used only when "
        "pixel_phase_mode = specified."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(-0.5, 0.5),
    tags=frozenset({"detector", "pixel", "spatial"}),
)

PIXEL_PHASE_Y = ParameterDef(
    name="detector.pixel_phase_y",
    description=(
        "Along-track offset of the geometric image point from the pixel centre, as a "
        "fraction of the pixel pitch (0 = centred, ±0.5 = pixel edge). Used only when "
        "pixel_phase_mode = specified."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(-0.5, 0.5),
    tags=frozenset({"detector", "pixel", "spatial"}),
)

# ---------------------------------------------------------------------------
# Quantum efficiency
# ---------------------------------------------------------------------------
#
# QE is specified one of two ways:
#   - ``detector.qe_value`` — scalar QE, applied uniformly in wavelength.
#   - ``detector.qe_table_path`` — path to a wavelength-vs-QE table, which
#     supersedes the scalar (loaded by RadiantSession per Rule 6).
# ``qe_value`` is required UNLESS ``qe_table_path`` is set — enforced via
# ``ParameterDef.required_unless`` (the "Phase 2C ConsistencyGroup" this
# comment previously promised was never built; two scenarios (1.2, 1.1)
# independently hit the spurious "qe_value is not set" rejection before
# the resolver learned about the alternative — Gap 66).

QE_VALUE = ParameterDef(
    name="detector.qe_value",
    description="Wavelength-independent scalar quantum efficiency.",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=None,
    bounds=(0.0, 1.0),
    tags=frozenset({"detector", "qe"}),
    required_unless="detector.qe_table_path,detector.qe_material",
)

QE_TABLE_PATH = ParameterDef(
    name="detector.qe_table_path",
    is_file_path=True,
    description=(
        "Path to a wavelength-vs-QE CSV. When set, RadiantSession loads it "
        "(io.qe_csv) onto the wavelength grid and applies it spectrally, "
        "superseding the scalar qe_value; past-cutoff QE is zero."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"detector", "qe"}),
    default_justification="Empty string signals 'use qe_value instead'.",
)

QE_MATERIAL = ParameterDef(
    name="detector.qe_material",
    description=(
        "Named bundled detector QE curve: a material in the bundled detector "
        "library (e.g. 'insb', 'hgcdte_mwir', 'silicon' — the API rejects unknown names "
        "with the legal vocabulary). Resolved pre-chain by the API layer onto the "
        "wavelength grid, QE = 0 past the data span. Precedence: qe_table_path (explicit "
        "file) > qe_material (library) > qe_value (scalar). Empty = disabled."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"detector", "qe", "library"}),
)


QE_TEMPERATURE_COEFF_PER_K = ParameterDef(
    name="detector.qe_temperature_coeff_per_K",
    description=(
        "Linear QE temperature coefficient [1/K]. QE(T) = QE_base · "
        "(1 + coeff·(detector_temperature_K − qe_temperature_ref_K)), applied "
        "to the scalar qe_value or the qe_table_path curve. Default 0 "
        "(temperature-independent QE)."
    ),
    dtype=float,
    canonical_unit="1/K",
    input_unit="1/K",
    default=0.0,
    bounds=(-0.1, 0.1),
    tags=frozenset({"detector", "qe"}),
    default_justification="0 = no QE temperature dependence (historical behaviour).",
)

QE_TEMPERATURE_REF_K = ParameterDef(
    name="detector.qe_temperature_ref_K",
    description=(
        "Reference temperature [K] at which the QE (qe_value / qe_table_path) "
        "was characterised. Only used when qe_temperature_coeff_per_K ≠ 0."
    ),
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=300.0,
    bounds=(1.0, 1000.0),
    tags=frozenset({"detector", "qe"}),
    default_justification="Room-temperature nominal; irrelevant when coeff = 0.",
)

# ---------------------------------------------------------------------------
# Dark current
# ---------------------------------------------------------------------------
#
# Ceiling rationale (CU-382). The three bounds below — dark rate, DSNU, and
# ROIC glow — were 1e9 / 1e6 / 1e6, which excluded real parts. A 20 um pixel at
# 1 A/m^2 dark-current density (1e-4 A/cm^2, a routine LWIR figure) needs
# 1 * (20e-6)^2 / 1.602e-19 = 2.50e9 e-/s, above the old dark ceiling; DSNU is a
# few percent of the dark SIGNAL, so its ceiling has to track dark x t_int; and
# glow is the same physical quantity as dark in the same units. Each old ceiling
# was its DEFAULT's rationale (a room-temperature Si CCD) applied to the bound,
# which is a category error: a default describes the typical part, a bound
# describes every expressible part. All three are now 1e12: that clears a 50 um
# pixel at 10 A/m^2 (1.56e11 e-/s) with room to spare, and it is the same ceiling
# readout.full_well_capacity_e carries, so a dark signal larger than the largest
# expressible well is unreachable anyway. Nothing downstream assumes a magnitude.
# Bounds are enforced at resolve time, not at set() — see the tests.

DARK_MODEL = ParameterDef(
    name="detector.dark_model",
    description=(
        "Dark-current source (Gap 123). 'measured' (default): use dark_rate_e_per_s "
        "with optional Arrhenius scaling — the historical behaviour. 'rule07' / "
        "'rule22': derive the per-pixel dark rate from the published empirical "
        "HgCdTe p-on-n law J(λc, T) (Tennant 2008 / Zandian 2023) using "
        "dark_cutoff_um, detector_temperature_K, and the pixel area — for "
        "blank-sheet design studies with no measured datasheet value. HgCdTe-only "
        "laws; an explicitly set dark_rate_e_per_s or dark_activation_energy_eV "
        "alongside a non-measured dark_model is rejected as over-specified."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="measured",
    enum_values=("measured", "rule07", "rule22"),
    tags=frozenset({"detector", "dark"}),
    default_justification="'measured' preserves the pre-Gap-123 behaviour bit-identically.",
)

DARK_CUTOFF_UM = ParameterDef(
    name="detector.dark_cutoff_um",
    description=(
        "Detector cutoff wavelength [µm] for the predictive dark-current laws "
        "(dark_model = 'rule07' / 'rule22'). 0 = unset; required when a "
        "predictive dark_model is selected, unused otherwise."
    ),
    dtype=float,
    canonical_unit="um",
    input_unit="um",
    default=0.0,
    bounds=(0.0, 30.0),
    tags=frozenset({"detector", "dark"}),
    default_justification="0 signals 'unset'; only consulted by the predictive dark models.",
)

DARK_RATE_E_PER_S = ParameterDef(
    name="detector.dark_rate_e_per_s",
    description="Dark current generation rate per pixel [e-/s].",
    dtype=float,
    canonical_unit="1/s",
    input_unit="1/s",
    default=100.0,
    bounds=(0.0, 1e12),
    tags=frozenset({"detector", "noise", "dark"}),
    default_justification="Order-of-magnitude room-temperature Si CCD reference.",
)

DARK_CURRENT_DENSITY_A_PER_CM2 = ParameterDef(
    name="detector.dark_current_density_a_per_cm2",
    description=(
        "Dark current density [A/cm²] — the form every datasheet and external "
        "radiometric model states. Converted to a per-pixel rate as J·A_pixel/q. "
        "Enter A/m² with unit='A/m2'. 0 = unset; mutually exclusive with "
        "dark_rate_e_per_s."
    ),
    dtype=float,
    canonical_unit="A/cm2",
    input_unit="A/cm2",
    default=0.0,
    bounds=(0.0, 1e6),
    tags=frozenset({"detector", "noise", "dark"}),
    default_justification=(
        "0.0 = unset, so the historical dark_rate_e_per_s door stays the one in "
        "force and no existing result moves. The two are alternate spellings of "
        "the same measured quantity, not two quantities, so setting both is "
        "rejected as over-specification rather than silently preferring one."
    ),
)

DARK_REFERENCE_TEMP = ParameterDef(
    name="detector.dark_reference_temperature_K",
    description="Temperature at which dark_rate_e_per_s is specified [K].",
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=77.0,
    bounds=(1.0, 500.0),
    tags=frozenset({"detector", "dark"}),
    default_justification=(
        "Matches the detector_temperature_K default (77 K) so the default "
        "config is self-consistent: with dark_activation_energy_eV = 0 the "
        "dark rate is temperature-inert, and a mismatched reference would "
        "otherwise make the default warn spuriously (CU-081)."
    ),
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
    canonical_unit="e-^2",
    input_unit="e-^2",
    default=0.0,
    bounds=(0.0, 1e12),
    tags=frozenset({"detector", "noise"}),
)

# The 1/f band is set by the measurement's own transfer function (CU-381,
# radiant.readout.flicker_transfer): the per-frame boxcar rolls off at ~1/t_int,
# the co-add comb sets the correlation, and the corner frequency marks where the
# white floor (already charged as read noise) takes over. The two band
# parameters below are therefore OVERRIDES, not required inputs — both default
# to 0.0 = unset, following readout.frame_period_s's precedent.

FLICKER_CORNER_HZ = ParameterDef(
    name="detector.flicker_corner_hz",
    description=(
        "Frequency where the 1/f PSD meets the white noise floor [Hz]. "
        "Above it the power is charged as read noise. 0 = unset."
    ),
    dtype=float,
    canonical_unit="Hz",
    input_unit="Hz",
    default=0.0,
    bounds=(0.0, 1e9),
    tags=frozenset({"detector", "noise"}),
    default_justification=(
        "0.0 = unset. There is no universal corner frequency — it is a measured "
        "ROIC property. Left unset with flicker_K > 0, RADIANT integrates to the "
        "boxcar roll-off instead, which OVERSTATES the term (the band above the "
        "corner is billed twice: once here, once as read noise) and warns saying "
        "so. Overstating noise is the safe direction for an unsupplied input; "
        "silently picking a corner is not."
    ),
)

FLICKER_F_LOW = ParameterDef(
    name="detector.flicker_f_low_hz",
    description=(
        "Low-frequency limit for 1/f integration [Hz] — the reciprocal of the "
        "longest timescale the measurement is compared over. "
        "0 = derive from the stack duration (n_coadds x frame_period_s)."
    ),
    dtype=float,
    canonical_unit="Hz",
    input_unit="Hz",
    default=0.0,
    bounds=(0.0, 1e6),
    tags=frozenset({"detector", "noise"}),
    default_justification=(
        "0.0 = derive as 1 / (n_coadds x frame_period_s). The 1/f integral "
        "diverges at DC for an un-referenced sum — slow drift couples in with "
        "full weight, and a single integration cannot tell 1/f drift from signal "
        "— so what makes 1/f *noise* rather than *offset* is the comparison "
        "window. Deriving it from the stack duration states that; the former "
        "0.01 Hz default corresponded to no timing anywhere in RADIANT."
    ),
)

FLICKER_F_HIGH = ParameterDef(
    name="detector.flicker_f_high_hz",
    description=(
        "Optional upper clamp on the 1/f integration band [Hz]. 0 = unset; "
        "rarely needed, since the integration-time boxcar already rolls off."
    ),
    dtype=float,
    canonical_unit="Hz",
    input_unit="Hz",
    default=0.0,
    bounds=(0.0, 1e9),
    tags=frozenset({"detector", "noise"}),
    default_justification=(
        "0.0 = unset. Physically redundant: H_box = sinc(pi f t_int) rolls off at "
        "~1/t_int, which IS the upper limit, and flicker_corner_hz cuts where the "
        "white floor takes over. The former 1.0e6 default was a fiction the sinc "
        "would have handled — at t_int = 5 ms it integrated 3.5 decades the "
        "detector cannot respond to. Retained as an override so an analyst can "
        "clamp the band explicitly (e.g. scenario 2.2's corner sweep)."
    ),
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
    canonical_unit="e-",
    input_unit="e-",
    default=0.0,
    bounds=(0.0, 1e12),
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
    enum_values=("imaging", "detection"),
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
    canonical_unit="e-",
    input_unit="e-",
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
    bounds=(0.0, 1e12),
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
    QE_MATERIAL,
    PIXEL_PITCH_X,
    PIXEL_PITCH_Y,
    FILL_FACTOR,
    PIXEL_PHASE_MODE,
    PIXEL_PHASE_X,
    PIXEL_PHASE_Y,
    QE_VALUE,
    QE_TABLE_PATH,
    QE_TEMPERATURE_COEFF_PER_K,
    QE_TEMPERATURE_REF_K,
    DARK_MODEL,
    DARK_CUTOFF_UM,
    DARK_RATE_E_PER_S,
    DARK_CURRENT_DENSITY_A_PER_CM2,
    DARK_REFERENCE_TEMP,
    DARK_ACTIVATION_EV,
    DETECTOR_TEMPERATURE_K,
    GR_FACTOR,
    R0A_OHM_CM2,
    FLICKER_K,
    FLICKER_CORNER_HZ,
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
