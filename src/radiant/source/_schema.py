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
    tags=frozenset({"thermal", "source", "target"}),
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
    tags=frozenset({"thermal", "source", "target"}),
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

# ---------------------------------------------------------------------------
# Geometry parameters for regime classification
# ---------------------------------------------------------------------------

TARGET_PROJECTED_AREA = ParameterDef(
    name="source.target.projected_area_m2",
    description=(
        "Projected area of target facing the observer [m²]. "
        "0.0 = not specified (extended-scene default)."
    ),
    dtype=float,
    canonical_unit="m2",
    input_unit="m2",
    default=0.0,
    bounds=(0.0, 1e12),
    tags=frozenset({"source", "target", "geometry"}),
    default_justification=(
        "0.0 signals 'geometry not provided' — regime classification defaults to extended scene."
    ),
)

TARGET_RANGE = ParameterDef(
    name="source.target.range_m",
    description=(
        "Observer-to-target slant range [m]. 0.0 = not specified (extended-scene default)."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 1e12),
    tags=frozenset({"source", "target", "geometry"}),
    default_justification=(
        "0.0 signals 'range not provided' — regime classification defaults to extended scene."
    ),
)

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
    tags=frozenset({"source", "target", "sub_pixel"}),
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
    tags=frozenset({"source", "background"}),
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
    tags=frozenset({"source", "background"}),
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
    tags=frozenset({"source", "contrast_reference"}),
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
    tags=frozenset({"source", "contrast_reference"}),
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

# ---------------------------------------------------------------------------
# Shape selection parameters (Target Definition Matrix §3 — Q3 resolution)
# ---------------------------------------------------------------------------
#
# Step 1.1 of the Target Definition Matrix Implementation Plan registers the
# shape-selection surface so YAML loaders / ``params.set`` accept it.  Wiring
# into ``_inferrer`` (construction of ``TargetShape`` instances, precedence
# over ``projected_area_m2``, view-direction-dependent projection) is Step
# 1.2 and deliberately not performed here.
#
# Design note — why flattened scalar params instead of a ``shape_params``
# dict:
#   The original task prompt proposed ``source.target.shape_params`` as a
#   free-form ``dict``.  ``ParameterDef`` (core) restricts dtype to
#   ``(float, int, str, bool)`` and Rule 16 forbids passing raw dicts from
#   user input into physics; so the plan resolves (owner-approved
#   2026-04-21) to flatten shape parameters into individual scalar
#   ParameterDefs.  The resolver in Step 1.2 picks the subset relevant to
#   the selected ``shape`` and ignores the rest.
#
# Bounds policy: each dimensional scalar uses ``bounds=(0.0, 1e6)`` so that
# the default sentinel ``0.0`` is accepted.  Step 1.2's ``build_shape``
# raises :class:`ParameterBoundsError` when a value is at the sentinel but
# the shape requires it to be strictly positive.  Canonical unit for all
# lengths is metres (Rule 2).

SHAPE = ParameterDef(
    name="source.target.shape",
    description=(
        "Geometric primitive for sub-pixel / point-source projected-area "
        "computation. 'none' = not specified (back-compat: use "
        "source.target.projected_area_m2).  Explicit values select a "
        "concrete shape; dimensional parameters are read from the "
        "source.target.shape_* scalars per the matrix §3 catalog."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="none",
    enum_values=("none", "sphere", "cylinder", "flat_plate", "box", "cone"),
    tags=frozenset({"source", "target", "geometry", "shape"}),
    default_justification=(
        "'none' is the Rule-12 sentinel for 'shape not provided'; the "
        "descriptor falls back to source.target.projected_area_m2.  Users "
        "opt into shape-driven projection by naming a concrete shape."
    ),
)

SHAPE_RADIUS = ParameterDef(
    name="source.target.shape_radius_m",
    description=(
        "Radius [m] for shapes with a single radius parameter "
        "(sphere, cylinder).  Must be > 0 when the selected shape "
        "requires it; validation is enforced by the Step 1.2 shape "
        "factory, not here.  Ignored for shapes that do not take a "
        "radius (flat_plate, box)."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 1e6),
    tags=frozenset({"source", "target", "geometry", "shape"}),
    default_justification=(
        "0.0 is the 'not set' sentinel; the Step 1.2 factory raises "
        "ParameterBoundsError if the chosen shape needs radius_m > 0."
    ),
)

SHAPE_LENGTH = ParameterDef(
    name="source.target.shape_length_m",
    description=(
        "Length [m] for shapes with a length axis (cylinder axial "
        "extent, flat_plate body-X extent, box body-X extent).  "
        "Ignored for sphere and cone."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 1e6),
    tags=frozenset({"source", "target", "geometry", "shape"}),
    default_justification="0.0 = not set; see SHAPE_RADIUS.",
)

SHAPE_WIDTH = ParameterDef(
    name="source.target.shape_width_m",
    description=(
        "Width [m] for rectangular shapes (flat_plate body-Y extent, "
        "box body-Y extent).  Ignored for sphere, cylinder, cone."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 1e6),
    tags=frozenset({"source", "target", "geometry", "shape"}),
    default_justification="0.0 = not set; see SHAPE_RADIUS.",
)

SHAPE_HEIGHT = ParameterDef(
    name="source.target.shape_height_m",
    description=(
        "Height [m] for shapes with a body-Z extent (box height, cone "
        "apex-to-base height).  Ignored for sphere, cylinder, "
        "flat_plate."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 1e6),
    tags=frozenset({"source", "target", "geometry", "shape"}),
    default_justification="0.0 = not set; see SHAPE_RADIUS.",
)

SHAPE_BASE_RADIUS = ParameterDef(
    name="source.target.shape_base_radius_m",
    description=(
        "Base-circle radius [m] for the cone shape.  Separate from "
        "source.target.shape_radius_m because the cone class names the "
        "parameter base_radius_m (see shapes/cone.py).  Ignored for "
        "non-cone shapes."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 1e6),
    tags=frozenset({"source", "target", "geometry", "shape"}),
    default_justification="0.0 = not set; see SHAPE_RADIUS.",
)

# Orientation (body-frame yaw/pitch/roll in radians, ZYX Euler per Rule 3).
# Default (0, 0, 0) aligns the shape's body axes with the scene frame so
# that sphere / cone / cylinder / flat_plate / box hit their canonical
# projected-area identities (π r², 2rL side-on, WH normal-on, etc.) out
# of the box.  Step 1.2 passes the tuple into the concrete TargetShape's
# ``orientation_rad`` field.

SHAPE_YAW = ParameterDef(
    name="source.target.shape_yaw_rad",
    description=(
        "Target body yaw [rad] about scene +Z (ZYX Euler, Rule 3).  "
        "Applied to the selected TargetShape's ``orientation_rad`` "
        "tuple in Step 1.2."
    ),
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=0.0,
    bounds=(-6.283185307179586, 6.283185307179586),  # [-2π, 2π]
    tags=frozenset({"source", "target", "geometry", "shape", "orientation"}),
    default_justification=("0.0 = body +X aligned with scene +X (canonical alignment)."),
)

SHAPE_PITCH = ParameterDef(
    name="source.target.shape_pitch_rad",
    description=("Target body pitch [rad] about scene +Y (ZYX Euler, Rule 3)."),
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=0.0,
    bounds=(-6.283185307179586, 6.283185307179586),
    tags=frozenset({"source", "target", "geometry", "shape", "orientation"}),
    default_justification="0.0 = canonical alignment; see SHAPE_YAW.",
)

SHAPE_ROLL = ParameterDef(
    name="source.target.shape_roll_rad",
    description=("Target body roll [rad] about scene +X (ZYX Euler, Rule 3)."),
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=0.0,
    bounds=(-6.283185307179586, 6.283185307179586),
    tags=frozenset({"source", "target", "geometry", "shape", "orientation"}),
    default_justification="0.0 = canonical alignment; see SHAPE_YAW.",
)

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
        "S11, mirroring source.target.projected_area_m2 / shape_radius_m."
    ),
)

BRIGHTNESS_TEMPERATURE_PATH = ParameterDef(
    name="source.target.brightness_temperature_path",
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

USER_RADIANCE_PATH = ParameterDef(
    name="source.target.user_radiance_path",
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
    TARGET_PROJECTED_AREA,
    TARGET_RANGE,
    FILL_FRACTION,
    BACKGROUND_TEMPERATURE,
    BACKGROUND_EMISSIVITY,
    CONTRAST_REFERENCE_TEMPERATURE,
    CONTRAST_REFERENCE_EMISSIVITY,
    REGIME_OVERRIDE,
    SCENE_TYPE,
    TARGET_LOCATION,
    NO_ATMOSPHERE_SUBCASE,
    SHAPE,
    SHAPE_RADIUS,
    SHAPE_LENGTH,
    SHAPE_WIDTH,
    SHAPE_HEIGHT,
    SHAPE_BASE_RADIUS,
    SHAPE_YAW,
    SHAPE_PITCH,
    SHAPE_ROLL,
    BRIGHTNESS_TEMPERATURE_K,
    BRIGHTNESS_TEMPERATURE_PATH,
    RADIANCE_TEMPERATURE_K,
    RADIANCE_TEMPERATURE_BAND_LO,
    RADIANCE_TEMPERATURE_BAND_HI,
    REFLECTANCE,
    ALBEDO,
    REFLECTANCE_PATH,
    ALBEDO_PATH,
    USER_RADIANCE_PATH,
    USER_INTENSITY_PATH,
)
