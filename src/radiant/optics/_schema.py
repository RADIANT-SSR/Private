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

N_SPIDERS = ParameterDef(
    name="optics.n_spiders",
    description=(
        "Number of secondary-support spider arms (radial struts). Default 0 "
        "(no struts). A 4-arm spider produces the familiar four-point "
        "diffraction spike. See RADIANT_Optics.md §3.3."
    ),
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=0,
    bounds=(0, 12),
    tags=frozenset({"optics", "aperture"}),
    default_justification="Apertures without modelled struts (most cases) have none.",
)

SPIDER_WIDTH_M = ParameterDef(
    name="optics.spider_width_m",
    description=(
        "Width of each spider arm [m]. Converted to a fraction of the pupil "
        "diameter for the mask; also subtracted from the radiometric clear "
        "area (RADIANT_Optics.md §3.3). Default 0. Active only when "
        "n_spiders > 0."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"optics", "aperture"}),
    default_justification="No struts modelled by default.",
)

SPIDER_ANGLE_DEG = ParameterDef(
    name="optics.spider_angle_deg",
    description=(
        "Orientation of the first spider arm about the optical axis [deg]; "
        "remaining arms equally spaced. Default 0 (first arm along +x)."
    ),
    dtype=float,
    canonical_unit="deg",
    input_unit="deg",
    default=0.0,
    bounds=(0.0, 360.0),
    tags=frozenset({"optics", "aperture"}),
    default_justification="Pattern orientation is arbitrary; 0 is the conventional reference.",
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
        "key_elements, full_prescription. Non-scalar modes read their "
        "curves/elements from pre-chain injections under "
        "stage_outputs['optics_config'] (transmission_spectral; "
        "telescope_transmission + filter_specs; key_elements + "
        "residual_transmission; element_list) — e.g. via "
        "Sensor.evaluate(extra_stage_outputs=...)."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="scalar",
    enum_values=(
        "scalar",
        "spectral_file",
        "telescope_plus_filters",
        "key_elements",
        "full_prescription",
    ),
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
    description=(
        "Wavefront error input mode: scalar_rms (parameter-driven), or "
        "zernike / field_dependent (WavefrontError object injected via "
        "stage_outputs['optics_config']['wavefront_error']). opd_map is "
        "not offered: OPD maps have no pupil-phase representation in v1 "
        "(Gap 68 un-advertised the always-raising mode)."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="scalar_rms",
    enum_values=("scalar_rms", "zernike", "field_dependent"),
    tags=frozenset({"optics", "wavefront"}),
)

ZERNIKE_FILE = ParameterDef(
    name="optics.zernike_file",
    is_file_path=True,
    description=(
        "Path to a Zemax 'Zernike Standard Coefficients' text export. When set, the "
        "API layer loads it pre-chain (Rule 6) and injects the resulting ZERNIKE-mode "
        "WavefrontError via stage_outputs['optics_config']['wavefront_error'], which "
        "supersedes wfe_mode/wfe_rms_waves. The report's own reference wavelength is "
        "honored; optics.wfe_reference_wavelength_um is the fallback when the export "
        "has no Wavelength header. Empty = disabled (scalar/parameter-driven WFE)."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"optics", "wavefront", "file"}),
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

SURFACE_ROUGHNESS_NM = ParameterDef(
    name="optics.surface_roughness_nm",
    description=(
        "Effective RMS surface micro-roughness of the optical train [nm] "
        "for the TIS scatter model: TIS = 1 - exp(-(4πσ/λ)²) at band "
        "center. Zero (default) = no scatter. Smooth-surface limit — a "
        "warning fires when TIS > 0.3. Scattered energy lands in a "
        "Gaussian halo of width optics.scatter_halo_sigma_um (Rule 4: "
        "kernel on the PSF path + analytic MTF term, exact Fourier pair)."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="nm",
    default=0.0,
    bounds=(0.0, 10000.0),
    tags=frozenset({"optics", "scatter"}),
    default_justification="0.0 = ideally smooth surfaces (backward compatible).",
)

SCATTER_HALO_SIGMA_UM = ParameterDef(
    name="optics.scatter_halo_sigma_um",
    description=(
        "Focal-plane sigma of the Gaussian scatter halo [µm] used by the "
        "TIS model. Sets where the scattered fraction lands; tune to a "
        "measured halo when available. Only meaningful when "
        "optics.surface_roughness_nm > 0."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="um",
    default=100.0,
    bounds=(0.1, 10000.0),
    tags=frozenset({"optics", "scatter"}),
    default_justification=(
        "100 µm — wide against typical PSF cores (several pixels), narrow "
        "against the PSF grid, so the halo is resolved on both paths."
    ),
)

SCALAR_EMISSIVITY = ParameterDef(
    name="optics.scalar_emissivity",
    description=(
        "Declared effective emissivity of the lumped optical train in scalar "
        "transmission mode [0, 1]. Zero (default) keeps the refractive-lump "
        "assumption (no warm-optics nearfield emission). Set nonzero for "
        "warm reflective trains — e.g. eps ≈ 1 - tau for an all-mirror train. "
        "Permitted only because the scalar lump is not a physical surface; "
        "Rule 5 (Kirchhoff-derived emissivity) still binds real elements. "
        "Requires eps + tau <= 1. Ignored in non-scalar transmission modes."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"optics", "thermal"}),
    default_justification="0.0 preserves the historical eps=0 refractive-lump assumption.",
)

NEARFIELD_FRACTION = ParameterDef(
    name="optics.nearfield_fraction",
    description=(
        "Nearfield fraction: fraction of the FPA hemisphere filled by "
        "warm (nearfield-emitting) elements. 0 = perfect cold stop "
        "(no warm-optics emission reaches the FPA); 1 = no cold stop "
        "(uncooled instrument). NOTE this is INVERTED from the vendor "
        "'cold stop efficiency' convention, where 100% efficient means "
        "complete blocking: nearfield_fraction = 1 - vendor_efficiency. "
        "Formerly named optics.cold_stop_efficiency (deprecated alias "
        "still accepted, Gap 12)."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=1.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"optics", "thermal"}),
    default_justification="1.0 = uncooled (no cold stop).",
    deprecated_aliases=frozenset({"optics.cold_stop_efficiency"}),
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
        "Stray light input mode: veiling_glare, absolute_irradiance, or "
        "spectral_file (curve injected via stage_outputs['optics_config']"
        "['stray_light_spectral']). pst_file is not offered: PST-based "
        "stray light needs a scene radiance distribution RADIANT v1 does "
        "not model (Gap 68 un-advertised the always-raising mode)."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="veiling_glare",
    enum_values=("veiling_glare", "absolute_irradiance", "spectral_file"),
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

STRAY_VEILING_GLARE_MTF = ParameterDef(
    name="optics.stray.veiling_glare_mtf",
    description=(
        "Enable the SPATIAL veiling-glare model (Gap 60): the veiling-glare "
        "fraction is re-imaged as a Gaussian halo, entering the PSF path as "
        "a kernel (1−vgf)·δ + vgf·G(σ_halo) and the MTF product path as its "
        "exact Fourier pair (1−vgf) + vgf·exp(−2π²σ²f²) — the low-frequency "
        "contrast-modulation loss the radiometric pedestal cannot express. "
        "0 (default) = pedestal-only (historical behavior); 1 = halo model "
        "active when veiling_glare_fraction > 0. (int: 1=True, 0=False)."
    ),
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=0,
    bounds=(0, 1),
    tags=frozenset({"optics", "stray_light"}),
    default_justification=(
        "Off by default: the spatial halo is a v1 approximation and turning "
        "it on changes MTF/RER/NIIRS for veiling-glare users; the "
        "radiometric pedestal remains the always-on baseline."
    ),
)

STRAY_HALO_SIGMA_UM = ParameterDef(
    name="optics.stray.halo_sigma_um",
    description=(
        "Gaussian half-width of the veiling-glare halo on the focal plane "
        "[µm] (Gap 60). Must be small enough to fit the PSF grid for the "
        "kernel and analytic MTF term to stay exact Fourier pairs (the "
        "kernel is truncated at the grid edge)."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="um",
    default=50.0,
    bounds=(0.1, 1000.0),
    tags=frozenset({"optics", "stray_light"}),
    default_justification=(
        "50 µm — a few pixels of halo, wide enough to kill high-frequency "
        "contrast while remaining representable on the PSF grid."
    ),
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
    ZERNIKE_FILE,
    APERTURE_DIAMETER_M,
    OBSCURATION_RATIO,
    N_SPIDERS,
    SPIDER_WIDTH_M,
    SPIDER_ANGLE_DEG,
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
    SURFACE_ROUGHNESS_NM,
    SCATTER_HALO_SIGMA_UM,
    SCALAR_EMISSIVITY,
    NEARFIELD_FRACTION,
    NEARFIELD_ENABLED,
    STRAY_INPUT_MODE,
    STRAY_VEILING_GLARE_FRACTION,
    STRAY_ABSOLUTE_IRRADIANCE,
    STRAY_INCLUDES_THERMAL,
    STRAY_VEILING_GLARE_MTF,
    STRAY_HALO_SIGMA_UM,
    PSF_N_WAVELENGTHS,
)
