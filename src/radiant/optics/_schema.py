"""Parameter definitions for the optics stage.

Covers the full RADIANT_Optics.md section 10 scalar-parameter inventory:
aperture geometry, focal length / f-number consistency group,
transmission mode selection, WFE mode, nearfield, and stray light.

Complex parameters (filter lists, element lists, Zernike dicts, file
paths for spectral data) are not representable as scalar ParameterDefs
and are handled as stage configuration passed directly to the stage.

The consistency group for ``(aperture_diameter_m, focal_length_m,
f_number)`` is named ``fnumber`` to match the resolver in
:func:`radiant.optics.aperture.resolve_fnumber_group`.
"""

from __future__ import annotations

from radiant.core.parameters import ParameterDef

# ---------------------------------------------------------------------------
# Aperture geometry
# ---------------------------------------------------------------------------

APERTURE_DIAMETER_M = ParameterDef(
    name="optics.aperture_diameter_m",
    description="Clear entrance-pupil diameter of the primary [m].",
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=None,  # required
    bounds=(1e-4, 20.0),
    group="fnumber",
    tags=frozenset({"optics", "aperture"}),
)

OBSCURATION_RATIO = ParameterDef(
    name="optics.obscuration_ratio",
    description=(
        "Central obscuration ratio ``D_secondary / D_primary``. Defaults to 0 "
        "(unobscured). Must satisfy 0 ≤ ε < 1."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 0.99),
    tags=frozenset({"optics", "aperture"}),
    default_justification="Most operational apertures are unobscured; Cassegrains override.",
)

# ---------------------------------------------------------------------------
# Focal length / f-number consistency group
# ---------------------------------------------------------------------------

FOCAL_LENGTH_M = ParameterDef(
    name="optics.focal_length_m",
    description="Effective focal length of the telescope [m].",
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=None,  # required (or derivable from f/# and D)
    bounds=(1e-4, 100.0),
    group="fnumber",
    tags=frozenset({"optics", "aperture"}),
)

F_NUMBER = ParameterDef(
    name="optics.f_number",
    description=(
        "Dimensionless f/# = focal_length_m / aperture_diameter_m. Part of "
        "the {D, f, f/#} consistency group; supply any two and the third "
        "is derived."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=None,  # derived when omitted
    bounds=(0.3, 200.0),
    group="fnumber",
    tags=frozenset({"optics", "aperture"}),
)

# ---------------------------------------------------------------------------
# Scalar transmission (Mode 1 only for 2B.3)
# ---------------------------------------------------------------------------

TRANSMISSION_SCALAR = ParameterDef(
    name="optics.transmission_scalar",
    description=(
        "Flat broadband optical throughput ``τ_opt`` (Mode 1 of "
        "RADIANT_Optics.md §5.1). Dimensionless in [0, 1]."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.7,
    bounds=(0.0, 1.0),
    tags=frozenset({"optics", "throughput"}),
    default_justification=(
        "0.7 is a typical end-to-end broadband throughput for a two-mirror "
        "telescope with an ambient-temperature filter stack, per "
        "RADIANT_Optics.md examples."
    ),
)


# ---------------------------------------------------------------------------
# Transmission mode
# ---------------------------------------------------------------------------

TRANSMISSION_INPUT_MODE = ParameterDef(
    name="optics.transmission_input_mode",
    description=(
        "Which of the five transmission input modes to use: "
        "scalar, spectral_file, telescope_plus_filters, "
        "key_elements, full_prescription."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="scalar",
    tags=frozenset({"optics", "throughput"}),
)

OPTICS_TEMPERATURE_K = ParameterDef(
    name="optics.optics_temperature_K",
    description=(
        "Default physical temperature of the optical train [K]. "
        "Used for synthesized lumped elements in Modes 1-4."
    ),
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=290.0,
    bounds=(1.0, 1000.0),
    tags=frozenset({"optics", "thermal"}),
    default_justification="290 K is standard room-temperature optics.",
)

OPTICS_DISTANCE_TO_FPA_M = ParameterDef(
    name="optics.optics_distance_to_fpa_m",
    description=(
        "Default distance from the optical train to the FPA [m]. "
        "Used as the distance_to_fpa_m for synthesized lumped elements. "
        "A value of 0.0 means 'use focal_length_m'."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 100.0),
    tags=frozenset({"optics", "geometry"}),
    default_justification="0 is a sentinel meaning 'use focal_length_m'.",
)

# ---------------------------------------------------------------------------
# Wavefront error
# ---------------------------------------------------------------------------

WFE_MODE = ParameterDef(
    name="optics.wfe_mode",
    description=("Wavefront error input mode: scalar_rms, zernike, opd_map, or field_dependent."),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="scalar_rms",
    tags=frozenset({"optics", "wavefront"}),
)

WFE_RMS_WAVES = ParameterDef(
    name="optics.wfe_rms_waves",
    description=("RMS wavefront error in waves at the reference wavelength (scalar_rms mode)."),
    dtype=float,
    canonical_unit="waves",
    input_unit="waves",
    default=0.0,
    bounds=(0.0, 2.0),
    tags=frozenset({"optics", "wavefront"}),
    default_justification="0 waves = perfect optics (diffraction-limited).",
)

WFE_REFERENCE_WAVELENGTH_UM = ParameterDef(
    name="optics.wfe_reference_wavelength_um",
    description=(
        "Reference wavelength at which the WFE is specified [um]. "
        "HeNe 0.633 um is the standard interferometry wavelength."
    ),
    dtype=float,
    canonical_unit="um",
    input_unit="um",
    default=0.633,
    bounds=(0.1, 30.0),
    tags=frozenset({"optics", "wavefront"}),
    default_justification="HeNe laser wavelength, standard for optical testing.",
)

# ---------------------------------------------------------------------------
# Defocus
# ---------------------------------------------------------------------------

DEFOCUS_UM = ParameterDef(
    name="optics.defocus_um",
    description=(
        "Linear defocus: displacement of the detector plane from best focus [µm]. "
        "Positive = behind focus, negative = in front. Both produce identical "
        "blur (absolute value used). Zero = no defocus."
    ),
    dtype=float,
    canonical_unit="um",
    input_unit="um",
    default=0.0,
    bounds=(-500.0, 500.0),
    tags=frozenset({"optics", "defocus"}),
    default_justification="0 = perfect focus (backward compatible).",
)

# ---------------------------------------------------------------------------
# Nearfield
# ---------------------------------------------------------------------------

COLD_STOP_EFFICIENCY = ParameterDef(
    name="optics.cold_stop_efficiency",
    description=(
        "Cold-stop efficiency: fraction of the FPA hemisphere filled by "
        "warm (nearfield-emitting) elements. Unity for uncooled instruments."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=1.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"optics", "thermal"}),
    default_justification="1.0 = uncooled (no cold stop).",
)

NEARFIELD_ENABLED = ParameterDef(
    name="optics.nearfield_enabled",
    description=(
        "Enable nearfield (warm-optics) emission calculation. "
        "Set to 0 to disable (int: 1=True, 0=False)."
    ),
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=1,
    bounds=(0, 1),
    tags=frozenset({"optics", "thermal"}),
    default_justification="Enabled by default for thermal-IR accuracy.",
)

# ---------------------------------------------------------------------------
# Stray light
# ---------------------------------------------------------------------------

STRAY_INPUT_MODE = ParameterDef(
    name="optics.stray.input_mode",
    description=(
        "Stray light input mode: veiling_glare, absolute_irradiance, spectral_file, or pst_file."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="veiling_glare",
    tags=frozenset({"optics", "stray_light"}),
)

STRAY_VEILING_GLARE_FRACTION = ParameterDef(
    name="optics.stray.veiling_glare_fraction",
    description=(
        "Veiling glare fraction: fraction of in-FOV scene irradiance "
        "that becomes stray light [0, 1]."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"optics", "stray_light"}),
    default_justification="0.0 = no stray light by default.",
)

STRAY_ABSOLUTE_IRRADIANCE = ParameterDef(
    name="optics.stray.absolute_irradiance_W_m2",
    description=(
        "Absolute in-band stray irradiance at the FPA [W/m^2]. "
        "Distributed flat across the wavelength grid."
    ),
    dtype=float,
    canonical_unit="W/m^2",
    input_unit="W/m^2",
    default=0.0,
    bounds=(0.0, 1e6),
    tags=frozenset({"optics", "stray_light"}),
    default_justification="0.0 = no stray light by default.",
)

STRAY_INCLUDES_THERMAL = ParameterDef(
    name="optics.stray.includes_thermal",
    description=(
        "If 1, the stray light measurement already includes warm-optics "
        "scatter; nearfield is suppressed to avoid double-counting. "
        "(int: 1=True, 0=False)."
    ),
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=0,
    bounds=(0, 1),
    tags=frozenset({"optics", "stray_light"}),
    default_justification="False by default — nearfield computed separately.",
)

# ---------------------------------------------------------------------------
# PSF wavelength sampling
# ---------------------------------------------------------------------------

FIELD_POSITION_X = ParameterDef(
    name="optics.field_position_x",
    description=(
        "Normalized cross-track field coordinate for field-dependent WFE "
        "evaluation. 0.0 = on-axis. Maps to field_x_deg via the field table."
    ),
    dtype=float,
    canonical_unit="deg",
    input_unit="deg",
    default=0.0,
    bounds=(-10.0, 10.0),
    tags=frozenset({"optics", "wavefront"}),
    default_justification="0.0 = on-axis (center of field).",
)

FIELD_POSITION_Y = ParameterDef(
    name="optics.field_position_y",
    description=(
        "Normalized along-track field coordinate for field-dependent WFE "
        "evaluation. 0.0 = on-axis. Maps to field_y_deg via the field table."
    ),
    dtype=float,
    canonical_unit="deg",
    input_unit="deg",
    default=0.0,
    bounds=(-10.0, 10.0),
    tags=frozenset({"optics", "wavefront"}),
    default_justification="0.0 = on-axis (center of field).",
)

PSF_N_WAVELENGTHS = ParameterDef(
    name="optics.psf_n_wavelengths",
    description=(
        "Number of wavelengths for polychromatic PSF computation. "
        "1 = monochromatic at band center (default). Values > 1 compute "
        "a photon-flux-weighted average of monochromatic PSFs across the "
        "spectral band."
    ),
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=1,
    bounds=(1, 101),
    tags=frozenset({"optics", "psf"}),
    default_justification=(
        "1 = monochromatic (backward compatible). Polychromatic broadening "
        "is typically 5-10% for MWIR; user opts in by setting > 1."
    ),
)


ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    APERTURE_DIAMETER_M,
    OBSCURATION_RATIO,
    FOCAL_LENGTH_M,
    F_NUMBER,
    TRANSMISSION_SCALAR,
    TRANSMISSION_INPUT_MODE,
    OPTICS_TEMPERATURE_K,
    OPTICS_DISTANCE_TO_FPA_M,
    DEFOCUS_UM,
    WFE_MODE,
    WFE_RMS_WAVES,
    WFE_REFERENCE_WAVELENGTH_UM,
    FIELD_POSITION_X,
    FIELD_POSITION_Y,
    COLD_STOP_EFFICIENCY,
    NEARFIELD_ENABLED,
    STRAY_INPUT_MODE,
    STRAY_VEILING_GLARE_FRACTION,
    STRAY_ABSOLUTE_IRRADIANCE,
    STRAY_INCLUDES_THERMAL,
    PSF_N_WAVELENGTHS,
)
