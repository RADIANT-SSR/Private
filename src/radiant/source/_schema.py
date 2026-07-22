"""Parameter definitions for the source stage.

Covers thermal, point-source, sub-pixel, and regime-related parameters.
"""

from __future__ import annotations

from typing import Any

from radiant.core.parameters import ParameterDef

# ---------------------------------------------------------------------------
# Target thermal parameters
# ---------------------------------------------------------------------------

TARGET_TEMPERATURE = ParameterDef(
    name="source.target.temperature",
    description="Target surface kinetic temperature (blackbody / graybody).",
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=300.0,
    bounds=(0.0, 5000.0),
    tags=frozenset({"thermal", "source", "target", "regime:extended", "regime:sub_pixel"}),
    default_justification=(
        "300 K is Earth ambient — a neutral default for terrestrial thermal "
        "imaging scenarios. User overrides for specific scenes."
    ),
)

TARGET_EMISSIVITY = ParameterDef(
    name="source.target.emissivity",
    description=(
        "Scalar target emissivity used when no spectral emissivity table is "
        "supplied. Graybody approximation: ε(λ) = const."
    ),
    dtype=float,
    canonical_unit="",  # dimensionless
    input_unit="",
    default=0.95,
    bounds=(0.0, 1.0),
    tags=frozenset({"thermal", "source", "target", "regime:extended", "regime:sub_pixel"}),
    default_justification=(
        "0.95 is typical for painted / oxidized natural surfaces in the LWIR "
        "and a conservative non-unity default."
    ),
)

TARGET_IS_HOT_TARGET = ParameterDef(
    name="source.target.is_hot_target",
    description=(
        "Hot-target opt-out for MWIR routing.  Per matrix §3.2 the legacy "
        "scalar-ε surface defaults MWIR scenes to T3Mixed (Kirchhoff "
        "emit+reflect) because ambient MWIR scenes are reflective-relevant.  "
        "Set true for ρ ≈ 0 hot-target scenes (engine plumes, missile "
        "signatures, calibration sources) where self-emission dominates "
        "and the legacy T1Thermal pure-emit treatment is the correct "
        "physics.  Ignored for non-MWIR wavelength grids."
    ),
    dtype=bool,
    canonical_unit="",
    input_unit="",
    default=False,
    tags=frozenset({"thermal", "source", "target", "routing"}),
    default_justification=(
        "Matrix §3.2: ambient MWIR scenes route to T3Mixed by default; "
        "hot-target sub-case is the explicit opt-out, not the default."
    ),
)

# Target spatial-extent parameters (projected area, shape, dimensions,
# orientation) moved to radiant/geometry/_schema.py as geometry.target.*
# (ADR-0008); the old source.target.* names survive as deprecated aliases
# on those definitions.  Target slant range likewise moved to
# geometry.target_range_m (ADR-0006), aliasing source.target.range_m.

# ---------------------------------------------------------------------------
# Sub-pixel parameters
# ---------------------------------------------------------------------------

FILL_FRACTION = ParameterDef(
    name="source.target.fill_fraction",
    description=(
        "Target fill fraction within the pixel. 1.0 = extended scene "
        "(default). Values in (0, 1) activate the sub-pixel regime."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=1.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"source", "target", "sub_pixel", "regime:sub_pixel"}),
    default_justification="1.0 = extended scene (most common case).",
)

BACKGROUND_TEMPERATURE = ParameterDef(
    name="source.background.temperature",
    description="Background surface temperature [K] for sub-pixel regime.",
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=290.0,
    bounds=(0.0, 5000.0),
    tags=frozenset({"source", "background", "regime:sub_pixel"}),
    default_justification="290 K is Earth-ambient background.",
)

BACKGROUND_EMISSIVITY = ParameterDef(
    name="source.background.emissivity",
    description="Background surface emissivity for sub-pixel regime.",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.95,
    bounds=(0.0, 1.0),
    tags=frozenset({"source", "background", "regime:sub_pixel"}),
    default_justification="0.95 is typical for natural terrain in LWIR.",
)

# ADR-0005 (Gap 52): the extended target-vs-background contrast reference.
# This is the uniform scene in the *neighbouring* extended pixel — a
# metric-only concept, explicitly NOT the deprecated source.background.*
# (adjacent-scene-behind-a-sub-pixel-target, Decision #15) and NOT the
# BackgroundDescriptor (absent for extended, Decision #13). It drives the
# extended contrast_snr differential ONLY; it never enters the noise budget,
# so Decision #13's SNR architecture is preserved. Opt-in: temperature = 0
# disables it (default), leaving all results unchanged.
CONTRAST_REFERENCE_TEMPERATURE = ParameterDef(
    name="source.contrast_reference.temperature",
    description=(
        "Temperature [K] of the reference (background) scene in the "
        "neighbouring extended pixel, used only for the extended "
        "contrast_snr differential (ADR-0005). 0 = no contrast reference "
        "(default). Never enters the noise budget."
    ),
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=0.0,
    bounds=(0.0, 5000.0),
    tags=frozenset({"source", "contrast_reference", "regime:extended"}),
    default_justification="0 K = disabled; the extended contrast_snr is not emitted.",
)

CONTRAST_REFERENCE_EMISSIVITY = ParameterDef(
    name="source.contrast_reference.emissivity",
    description=(
        "Emissivity of the extended contrast-reference scene (ADR-0005). "
        "Only used when source.contrast_reference.temperature > 0."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.95,
    bounds=(0.0, 1.0),
    tags=frozenset({"source", "contrast_reference", "regime:extended"}),
    default_justification="0.95 is typical for natural terrain in LWIR.",
)

# ---------------------------------------------------------------------------
# Regime override
# ---------------------------------------------------------------------------

REGIME_OVERRIDE = ParameterDef(
    name="source.regime_override",
    description=(
        "Force regime classification. 'auto' = use detection rule. "
        "'extended', 'point_source', 'sub_pixel' = force that regime."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="auto",
    bounds=None,
    tags=frozenset({"source", "regime"}),
    default_justification="'auto' detects regime from target geometry.",
)

# ---------------------------------------------------------------------------
# Option C descriptor-surface parameters (ADR-0002, Stage 2)
# ---------------------------------------------------------------------------
#
# These three parameters expose the matrix §3.2 axes at the YAML surface so
# users can explicitly choose the cell they want to run.  When any of them
# is at its schema default, the Stage-2 back-compat inferrer
# (`radiant.source._inferrer`) infers the descriptor from the existing
# parameters (fill_fraction, atmosphere.model, geometry, etc.).  When set
# explicitly by the user, the explicit value wins over inference.
#
# The ``auto`` default on ``source.scene_type`` and ``source.target_location``
# is a distinct sentinel value (rather than "extended" / "terrestrial")
# because Stage 2 needs to distinguish "user did not set this" from "user
# set this to the same value as the default".  Without the sentinel the
# inferrer could not tell the difference via ``get_resolved().provenance``
# alone when a YAML loader reuses the default string.  The allowed values
# include ``auto`` so the resolver accepts it cleanly.

SCENE_TYPE = ParameterDef(
    name="source.scene_type",
    description=(
        "Matrix §3.2 scene-type axis. 'auto' = infer from fill_fraction / "
        "geometry (default). 'extended' = fills the pixel; 'sub_pixel' = "
        "partial fill; 'point_source' = angular size ≪ IFOV."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="auto",
    enum_values=("auto", "extended", "sub_pixel", "point_source"),
    tags=frozenset({"source", "descriptor", "matrix_axis"}),
    default_justification=(
        "'auto' triggers the back-compat inferrer in Stage 2 of the Option C "
        "plan: scene_type is derived from fill_fraction plus IFOV-based "
        "regime classification.  Users set this explicitly to lock a matrix "
        "cell."
    ),
)

TARGET_LOCATION = ParameterDef(
    name="source.target_location",
    description=(
        "Matrix §3.2 target-location axis. 'auto' = infer from "
        "atmosphere.model (default). Allowed explicit values: 'at_aperture', "
        "'terrestrial', 'airborne', 'no_atmosphere'."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="auto",
    enum_values=(
        "auto",
        "at_aperture",
        "terrestrial",
        "airborne",
        "no_atmosphere",
    ),
    tags=frozenset({"source", "descriptor", "matrix_axis"}),
    default_justification=(
        "'auto' triggers the back-compat inferrer: terrestrial for the "
        "atmospheric backends, no_atmosphere(space) for 'exo'.  Users set "
        "this explicitly for airborne / at_aperture / lab cases."
    ),
)

NO_ATMOSPHERE_SUBCASE = ParameterDef(
    name="source.no_atmosphere_subcase",
    description=(
        "Matrix §3.3 sub-case selector for target_location='no_atmosphere'. "
        "Empty string = not set (paired with target_location != "
        "'no_atmosphere'). Allowed explicit values: 'space', 'ground_test', "
        "'lab_test'."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    enum_values=("", "space", "ground_test", "lab_test"),
    tags=frozenset({"source", "descriptor", "matrix_axis"}),
    default_justification=(
        "Empty string is the Rule-12 sentinel for 'not set'.  The inferrer "
        "promotes it to 'space' when atmosphere.model == 'exo'; explicit "
        "ground_test / lab_test require user action in a Stage 7 preset."
    ),
)

LAB_TEST_MODE = ParameterDef(
    name="source.lab_test_mode",
    description=(
        "Positive dark/lit assertion for the ground_test / lab_test "
        "sub-cases (Gap 40). 'dark' declares a no-external-illumination "
        "configuration (no lamp, no solar — thermal self-emission only, "
        "the D-lab dark-cal sub-mode) and is VALIDATED: a user-set "
        "source.target.reflectance contradicts it and is rejected. 'lit' "
        "positively asserts an externally illuminated lab scene (recorded "
        "for readability; unvalidated until a lamp surface exists). Empty "
        "string = unasserted (back-compat)."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    enum_values=("", "dark", "lit"),
    tags=frozenset({"source", "descriptor", "lab"}),
    default_justification=(
        "Empty string preserves every existing lab/ground-test config "
        "byte-for-byte; the flag is a readability/validation assertion, "
        "not a radiometric input."
    ),
)

BACKGROUND_MATERIAL = ParameterDef(
    name="source.background.material",
    description=(
        "Named spectral-library material for the sub-pixel/point-source "
        "GroundBackground emissivity ε_g(λ) (CU-008). 'grey' (default) uses "
        "the scalar source.background.emissivity as a flat spectrum — the "
        "back-compat path. Any other name is resolved against "
        "radiant.data.SpectralLibrary (vegetation_green, snow, soil_dry, "
        "asphalt, ...) by the API layer before chain execution (Rule 6); "
        "unknown names are rejected with the legal vocabulary. "
        "source.background.emissivity_path overrides this when set."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="grey",
    tags=frozenset({"source", "background", "spectral", "regime:sub_pixel"}),
    default_justification=(
        "'grey' reproduces the pre-CU-008 scalar behavior exactly, so "
        "every existing sub-pixel configuration is unchanged."
    ),
)

BACKGROUND_EMISSIVITY_PATH = ParameterDef(
    name="source.background.emissivity_path",
    is_file_path=True,
    description=(
        "Two-column CSV (wavelength_um, emissivity) giving a measured "
        "background emissivity spectrum ε_g(λ) for the sub-pixel/"
        "point-source GroundBackground (CU-008). Loaded by the API layer "
        "before chain execution (Rule 6) and resampled onto the chain "
        "grid. Takes precedence over source.background.material."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"source", "background", "spectral", "regime:sub_pixel"}),
    default_justification="Empty string = no override (use material).",
)

# Shape-selection and orientation parameters (shape, shape_*_m,
# shape_{yaw,pitch,roll}_rad) moved to radiant/geometry/_schema.py as
# geometry.target.* (ADR-0008 — spatial extent belongs to Geometry).  The
# old source.target.shape* names survive as deprecated aliases on those
# definitions; the shape factory and inferrer now read the geometry.target.*
# canonical names.

# ---------------------------------------------------------------------------
# S11 — brightness temperature T_B (Target Definition Matrix §1, Plan 2.1)
# ---------------------------------------------------------------------------
#
# Brightness temperature is the equivalent-blackbody temperature that produces
# the same spectral radiance as the source at wavelength λ.  ``T_B`` is a
# legitimate user specification for IR / microwave remote-sensing targets
# where the physical (ε, T_phys) pair is unknown.
#
# The converter in ``source.converters.brightness_temperature`` maps user
# input to a canonical TargetDescriptor:
#   - (near-)constant T_B → T1Thermal(T_t=T_B, ε≡1)
#   - λ-varying T_B(λ)   → T6TabulatedAtSource(L_source=B(λ, T_B(λ))) per
#                          ADR-0003
#
# Design note — why two scalar params instead of a single SpectralData
# field: ``ParameterDef.dtype`` is restricted to ``{float, int, str, bool}``
# (core constraint); SpectralData is transported via a file-path sentinel,
# consistent with ``detector.qe_table_path`` and
# ``atmosphere.tabulated_path_radiance_file``.  The file, when supplied,
# is a 2-column CSV ``wavelength_um, T_B_K`` (header optional).

BRIGHTNESS_TEMPERATURE_K = ParameterDef(
    name="source.target.brightness_temperature_K",
    description=(
        "Scalar brightness temperature T_B [K] — the equivalent-blackbody "
        "temperature that produces the same spectral radiance as the source. "
        "When user-set (provenance != DEFAULT), routes through the S11 "
        "converter to a T1Thermal descriptor with ε≡1.  Mutually exclusive "
        "with source.target.brightness_temperature_path."
    ),
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=0.0,
    bounds=(0.0, 10000.0),
    tags=frozenset({"source", "target", "thermal", "S11"}),
    default_justification=(
        "0.0 K is the Rule-12 'not set' sentinel; the inferrer checks "
        "provenance (not value) to decide whether the user opted into "
        "S11, mirroring geometry.target.projected_area_m2 / shape_radius_m."
    ),
)

BRIGHTNESS_TEMPERATURE_PATH = ParameterDef(
    name="source.target.brightness_temperature_path",
    is_file_path=True,
    description=(
        "Path to a 2-column CSV (wavelength_um, T_B_K) carrying a "
        "wavelength-dependent brightness temperature.  When set, routes "
        "through the S11 converter; λ-varying T_B emits "
        "T6TabulatedAtSource with L_source = B(λ, T_B(λ)) per ADR-0003. "
        "Mutually exclusive with source.target.brightness_temperature_K."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"source", "target", "thermal", "S11"}),
    default_justification=(
        "Empty string = not set.  Pattern mirrors "
        "detector.qe_table_path / atmosphere.tabulated_path_radiance_file "
        "for SpectralData transport through the ParameterSet surface."
    ),
)

# ---------------------------------------------------------------------------
# S12 — band-averaged radiance temperature (T_R + band)
# ---------------------------------------------------------------------------
# T_R is a scalar K value paired with a (λ_lo, λ_hi) band.  The S12 converter
# treats the target as a blackbody at T_R and emits T1Thermal(T_t=T_R, ε≡1).
# A separate inversion helper (``source.converters.invert_band_radiance``)
# is provided for future forward-compat use cases in which a user supplies
# an in-band integrated radiance and needs T_equiv recovered.

RADIANCE_TEMPERATURE_K = ParameterDef(
    name="source.target.radiance_temperature_K",
    description=(
        "Band-averaged radiance temperature T_R [K] — the scalar "
        "equivalent-blackbody temperature that matches the in-band integrated "
        "radiance of the target over [λ_lo, λ_hi].  Must be paired with "
        "source.target.radiance_temperature_band_lo_um and "
        "source.target.radiance_temperature_band_hi_um when user-set.  "
        "Mutually exclusive with S11 brightness_temperature parameters."
    ),
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=0.0,
    bounds=(0.0, 10000.0),
    tags=frozenset({"source", "target", "thermal", "S12"}),
    default_justification=(
        "0.0 K is the Rule-12 'not set' sentinel; the inferrer checks "
        "provenance (not value) to decide whether the user opted into S12."
    ),
)

RADIANCE_TEMPERATURE_BAND_LO = ParameterDef(
    name="source.target.radiance_temperature_band_lo_um",
    description=(
        "Lower band edge [µm] for the S12 radiance-temperature specification. "
        "Required when source.target.radiance_temperature_K is user-set; must "
        "satisfy λ_lo < λ_hi."
    ),
    dtype=float,
    canonical_unit="um",
    input_unit="um",
    default=0.0,
    bounds=(0.0, 1000.0),
    tags=frozenset({"source", "target", "thermal", "S12"}),
    default_justification=("0.0 µm is the 'not set' sentinel; inferrer checks provenance."),
)

RADIANCE_TEMPERATURE_BAND_HI = ParameterDef(
    name="source.target.radiance_temperature_band_hi_um",
    description=(
        "Upper band edge [µm] for the S12 radiance-temperature specification. "
        "Required when source.target.radiance_temperature_K is user-set; must "
        "satisfy λ_lo < λ_hi."
    ),
    dtype=float,
    canonical_unit="um",
    input_unit="um",
    default=0.0,
    bounds=(0.0, 1000.0),
    tags=frozenset({"source", "target", "thermal", "S12"}),
    default_justification=("0.0 µm is the 'not set' sentinel; inferrer checks provenance."),
)


# ---------------------------------------------------------------------------
# S4 / S5 / S6 — spectral reflectance / albedo (reflective user inputs)
# ---------------------------------------------------------------------------
# Reflective targets (T2Reflective) are specified by ρ(λ) — either a scalar
# ρ lifted to a constant spectrum (S4) or a tabulated ρ(λ) CSV (S5/S6).
# ``albedo`` is the user-facing alias for ``reflectance`` (both map to the
# same T2Reflective surface); exposing both keeps the YAML surface natural
# ("I want to set albedo") while preserving a single physics path.  The
# inferrer (Step 3.2) treats the two as mutually exclusive — supplying both
# over-specifies the reflectance and raises.  Same path-sentinel pattern as
# S11: SpectralData can't be a ParameterDef dtype, so tabulated input flows
# in via a CSV path string.

REFLECTANCE = ParameterDef(
    name="source.target.reflectance",
    description=(
        "Scalar target reflectance ρ [dimensionless, 0–1] — the fraction "
        "of incident radiance that is reflected from the target.  When "
        "user-set (provenance != DEFAULT), routes through the Step 3.2 "
        "inferrer to a T2Reflective descriptor with ρ(λ) ≡ this scalar. "
        "Mutually exclusive with source.target.albedo, "
        "source.target.reflectance_path, and the legacy (ε, T) surface."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"source", "target", "reflective", "S4"}),
    default_justification=(
        "0.0 is the Rule-12 'not set' sentinel; the inferrer checks "
        "provenance (not value) to decide whether the user opted into S4. "
        "A physically zero reflectance is still user-set and routes through."
    ),
)

ALBEDO = ParameterDef(
    name="source.target.albedo",
    description=(
        "User-facing alias for source.target.reflectance with identical "
        "semantics (Lambertian ρ, 0–1).  Accepted for scenarios where "
        "'albedo' is the natural label; the inferrer rejects pairing with "
        "source.target.reflectance (pick one)."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"source", "target", "reflective", "S4"}),
    default_justification=("0.0 is the Rule-12 'not set' sentinel (same pattern as reflectance)."),
)

REFLECTANCE_PATH = ParameterDef(
    name="source.target.reflectance_path",
    is_file_path=True,
    description=(
        "Path to a 2-column CSV (wavelength_um, rho) carrying a "
        "λ-dependent reflectance ρ(λ).  When set, routes through the "
        "Step 3.2 inferrer to a T2Reflective descriptor (S5/S6).  Mutually "
        "exclusive with the scalar reflectance / albedo surfaces."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"source", "target", "reflective", "S5", "S6"}),
    default_justification=(
        "Empty string = not set; pattern mirrors source.target.brightness_temperature_path."
    ),
)

ALBEDO_PATH = ParameterDef(
    name="source.target.albedo_path",
    is_file_path=True,
    description=(
        "Alias of source.target.reflectance_path with identical CSV "
        "format.  Rejected when paired with the reflectance_path surface."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"source", "target", "reflective", "S5", "S6"}),
    default_justification=("Empty string = not set."),
)

EMISSIVITY_PATH = ParameterDef(
    name="source.target.emissivity_path",
    is_file_path=True,
    description=(
        "Path to a 2-column CSV (wavelength_um, emissivity) carrying a "
        "λ-dependent emissivity ε(λ) for a thermal target (Gap 47). When "
        "set, the inferrer builds the thermal descriptor with L_t(λ) = "
        "ε(λ)·B(λ, source.target.temperature) instead of a grey ε. "
        "Mutually exclusive with the scalar source.target.emissivity and "
        "with every reflective / radiance / brightness-temperature surface."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"source", "target", "thermal", "S1"}),
    default_justification=(
        "Empty string = not set; pattern mirrors source.target.reflectance_path."
    ),
)

USER_RADIANCE_PATH = ParameterDef(
    name="source.target.user_radiance_path",
    is_file_path=True,
    description=(
        "Path to a 2-column CSV (wavelength_um, L_t_source [W/m²/sr/µm]) "
        "carrying a user-supplied spectral radiance at the target plane.  "
        "When set, routes through the Phase 4 inferrer to a "
        "T6TabulatedAtSource descriptor (S8 — no physical model applied; "
        "the user owns the physics).  Mutually exclusive with every "
        "other target spec form ((ε, T), reflectance/albedo, "
        "brightness_temperature, radiance_temperature)."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"source", "target", "user_radiance", "S8"}),
    default_justification=(
        "Empty string = not set.  Path is a plain string; the CSV "
        "payload values are W/m²/sr/µm but the ParameterDef itself "
        "describes the path string only (pattern mirrors "
        "source.target.brightness_temperature_path)."
    ),
)

USER_INTENSITY_PATH = ParameterDef(
    name="source.target.user_intensity_path",
    is_file_path=True,
    description=(
        "Path to a 2-column CSV (wavelength_um, I_t_source [W/sr/µm]) "
        "carrying a user-supplied spectral intensity at the target "
        "plane, for unresolved (point-source) targets.  When set, "
        "routes through the Phase 5 inferrer to a T7IntensityAtSource "
        "descriptor (S10 — ADR-0004; no physical model applied, the "
        "user owns the physics).  Mutually exclusive with every other "
        "target spec form ((ε, T), reflectance/albedo, "
        "brightness_temperature, radiance_temperature, user_radiance).  "
        "Requires scene_type='point_source'."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"source", "target", "user_intensity", "S10"}),
    default_justification=(
        "Empty string = not set.  Path is a plain string; the CSV "
        "payload values are W/sr/µm but the ParameterDef itself "
        "describes the path string only (pattern mirrors "
        "source.target.user_radiance_path)."
    ),
)

# --- Point-source intensity from a blackbody emitter (Gap B / S10 convenience) ---
# I(λ) = ε · A_emit · B(λ, T) [W/sr/µm], routed to the same T7IntensityAtSource as the
# CSV path — so an SDA / star-tracker analyst gives (T, A, ε) instead of hand-authoring a
# CSV. Set-detection is provenance-based (a value at its default is "not set"); requires
# scene_type='point_source' and is mutually exclusive with the surface-radiance (ε, T)
# path, the CSV intensity path, and the scalar band intensity below.
POINT_INTENSITY_TEMPERATURE_K = ParameterDef(
    name="source.target.point_intensity_temperature_K",
    description=(
        "Point-source emitter temperature [K]. With point_intensity_area_m2 (and "
        "point_intensity_emissivity) defines a blackbody radiant intensity "
        "I(λ) = ε·A·B(λ,T) [W/sr/µm] for an unresolved target (SDA thermal object, "
        "S10 convenience — no surface radiance × area needed). Requires "
        "scene_type='point_source'."
    ),
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=0.0,
    bounds=(0.0, 5000.0),
    tags=frozenset({"source", "target", "point_intensity", "S10", "regime:point_source"}),
    default_justification=(
        "0 K = not set (provenance-detected); the blackbody point-source path is opt-in."
    ),
)

POINT_INTENSITY_AREA_M2 = ParameterDef(
    name="source.target.point_intensity_area_m2",
    description=(
        "Projected emitting area [m²] of a blackbody point source — the A in "
        "I(λ) = ε·A·B(λ,T). Distinct from geometry.target.projected_area_m2 (which sizes "
        "a resolved/sub-pixel target); this one only scales the point-source intensity."
    ),
    dtype=float,
    canonical_unit="m^2",
    input_unit="m^2",
    default=0.0,
    bounds=(0.0, 1.0e12),
    tags=frozenset({"source", "target", "point_intensity", "S10", "regime:point_source"}),
    default_justification=(
        "0 m² = not set; the emitting area is required only for the blackbody point-source path."
    ),
)

POINT_INTENSITY_EMISSIVITY = ParameterDef(
    name="source.target.point_intensity_emissivity",
    description=(
        "Scalar emissivity ε ∈ [0, 1] of a blackbody point source (the ε in "
        "I(λ) = ε·A·B(λ,T)). Independent material property (Rule 5 applies to optical "
        "elements, not scene targets)."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=1.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"source", "target", "point_intensity", "S10", "regime:point_source"}),
    default_justification=(
        "ε = 1.0 (ideal blackbody) is the neutral default when only T and A are given."
    ),
)

POINT_INTENSITY_BAND_W_PER_SR = ParameterDef(
    name="source.target.point_intensity_band_W_per_sr",
    description=(
        "Scalar band-integrated radiant intensity [W/sr] of a point source — the "
        "in-band integral ∫ I(λ) dλ over the filter band "
        "[spectral_integration.filter_min_um, filter_max_um]. Modeled as a spectrally "
        "flat intensity I(λ) = value/(filter_max−filter_min) inside the band, zero "
        "outside, so the band integral recovers the specified value. The simplest "
        "point-source input (star-tracker / SDA when only a band flux is known); requires "
        "scene_type='point_source'. Mutually exclusive with the blackbody point-intensity "
        "params and the CSV intensity path."
    ),
    dtype=float,
    canonical_unit="W/sr",
    input_unit="W/sr",
    default=0.0,
    bounds=(0.0, 1.0e12),
    tags=frozenset({"source", "target", "point_intensity", "S10", "regime:point_source"}),
    default_justification=(
        "0 W/sr = not set (provenance-detected); the scalar band-intensity path is opt-in."
    ),
)


def validate_reflectance_albedo_exclusive(params: Any) -> None:
    """Raise if both ``reflectance`` and ``albedo`` surfaces are user-set.

    ``albedo`` is a naming alias for ``reflectance``; supplying both over-
    specifies the same physical quantity.  The same rule applies to the
    tabulated ``_path`` siblings.  Called by the Step 3.2 inferrer
    (unit-tested in :mod:`source.tests.test_schema`).

    Parameters
    ----------
    params:
        A :class:`radiant.core.parameters.ParameterSet`.  Typed as ``Any``
        here to keep :mod:`radiant.source._schema` free of the core/
        parameters import cycle (Rule 11 — schema is user-data only).
    """
    from radiant.core.parameters import (  # local import: avoid cycle
        ParameterBoundsError,
        Provenance,
    )

    rho_rv = params.get_resolved("source.target.reflectance")
    alb_rv = params.get_resolved("source.target.albedo")
    rho_path_rv = params.get_resolved("source.target.reflectance_path")
    alb_path_rv = params.get_resolved("source.target.albedo_path")

    rho_user = rho_rv.provenance is not Provenance.DEFAULT
    alb_user = alb_rv.provenance is not Provenance.DEFAULT
    rho_path_user = rho_path_rv.provenance is not Provenance.DEFAULT and bool(rho_path_rv.value)
    alb_path_user = alb_path_rv.provenance is not Provenance.DEFAULT and bool(alb_path_rv.value)

    set_surfaces = []
    if rho_user:
        set_surfaces.append("source.target.reflectance")
    if alb_user:
        set_surfaces.append("source.target.albedo")
    if rho_path_user:
        set_surfaces.append("source.target.reflectance_path")
    if alb_path_user:
        set_surfaces.append("source.target.albedo_path")

    if len(set_surfaces) > 1:
        raise ParameterBoundsError(
            what=(
                "source._schema: reflectance / albedo over-specified — "
                f"{len(set_surfaces)} surfaces user-set: {set_surfaces}"
            ),
            why=(
                "reflectance and albedo are aliases for the same "
                "Lambertian ρ; tabulated (_path) and scalar siblings are "
                "mutually exclusive.  Supplying more than one is always "
                "ambiguous — the inferrer cannot pick a canonical ρ(λ)."
            ),
            action=(
                "Leave exactly one surface set: scalar reflectance *or* "
                "albedo *or* reflectance_path *or* albedo_path."
            ),
            context={"set_surfaces": set_surfaces},
        )


ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    TARGET_TEMPERATURE,
    TARGET_EMISSIVITY,
    TARGET_IS_HOT_TARGET,
    FILL_FRACTION,
    BACKGROUND_TEMPERATURE,
    BACKGROUND_EMISSIVITY,
    CONTRAST_REFERENCE_TEMPERATURE,
    CONTRAST_REFERENCE_EMISSIVITY,
    REGIME_OVERRIDE,
    SCENE_TYPE,
    TARGET_LOCATION,
    NO_ATMOSPHERE_SUBCASE,
    LAB_TEST_MODE,
    BACKGROUND_MATERIAL,
    BACKGROUND_EMISSIVITY_PATH,
    BRIGHTNESS_TEMPERATURE_K,
    BRIGHTNESS_TEMPERATURE_PATH,
    RADIANCE_TEMPERATURE_K,
    RADIANCE_TEMPERATURE_BAND_LO,
    RADIANCE_TEMPERATURE_BAND_HI,
    REFLECTANCE,
    ALBEDO,
    REFLECTANCE_PATH,
    ALBEDO_PATH,
    EMISSIVITY_PATH,
    USER_RADIANCE_PATH,
    USER_INTENSITY_PATH,
    POINT_INTENSITY_TEMPERATURE_K,
    POINT_INTENSITY_AREA_M2,
    POINT_INTENSITY_EMISSIVITY,
    POINT_INTENSITY_BAND_W_PER_SR,
)
