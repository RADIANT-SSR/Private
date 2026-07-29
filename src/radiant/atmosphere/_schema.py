"""Parameter definitions for the atmosphere stage.

Covers all four atmosphere models (simple, exo, tabulated, modtran)
plus the interpolated model and viewing geometry parameters.
"""

from __future__ import annotations

from radiant.atmosphere._modtran_paths import default_modtran_binary_str
from radiant.core.parameters import ParameterDef

# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

ATMOSPHERE_MODEL = ParameterDef(
    name="atmosphere.model",
    description=(
        "Atmosphere model selector. 'simple' uses a closed-form Beer-Lambert; "
        "'exo' uses a vacuum; 'tabulated' loads from files; 'modtran' wraps "
        "the MODTRAN binary; 'interpolated' interpolates between pre-computed "
        "runs at discrete geometry points."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="simple",
    enum_values=("simple", "exo", "tabulated", "modtran", "interpolated"),
    tags=frozenset({"atmosphere", "selection"}),
    default_justification=(
        "'simple' is the v1 default for terrestrial scenarios; the parameter "
        "resolver promotes the choice to 'exo' automatically when both "
        "endpoints are space-based."
    ),
)

# ---------------------------------------------------------------------------
# Simple parametric model
# ---------------------------------------------------------------------------

VISIBILITY_KM = ParameterDef(
    name="atmosphere.visibility_km",
    description=(
        "Meteorological visibility at 550 nm in kilometres. Drives the "
        "Koschmieder aerosol extinction σ_aer(550 nm) = 3.912 / V_km."
    ),
    dtype=float,
    canonical_unit="km",
    input_unit="km",
    default=23.0,
    bounds=(0.1, 500.0),
    tags=frozenset({"atmosphere", "simple", "aerosol"}),
    default_justification=(
        "23 km is the 'clear' Koschmieder reference value used as the default "
        "throughout RADIANT_Atmosphere.md §3.1."
    ),
)

AEROSOL_TYPE = ParameterDef(
    name="atmosphere.aerosol_type",
    description=(
        "Aerosol type label. Selects an Ångström exponent and single-scatter "
        "albedo: rural (α=1.3), urban (α=1.5), maritime (α=0.7)."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="rural",
    enum_values=("rural", "urban", "maritime"),
    tags=frozenset({"atmosphere", "simple", "aerosol"}),
    default_justification=(
        "Rural is the most common terrestrial use case and matches MODTRAN IHAZE=1."
    ),
)

PRECIPITABLE_WATER_CM = ParameterDef(
    name="atmosphere.precipitable_water_cm",
    description=(
        "Total column precipitable water in centimetres of liquid-equivalent "
        "water vapour. Drives the 5-band water-vapor extinction fit."
    ),
    dtype=float,
    canonical_unit="cm",
    input_unit="cm",
    default=1.4,
    bounds=(0.0, 10.0),
    tags=frozenset({"atmosphere", "simple", "h2o"}),
    default_justification=(
        "1.4 cm is the US Standard mid-latitude annual mean — RADIANT_Atmosphere.md §6.2."
    ),
)

STANDARD_ATMOSPHERE = ParameterDef(
    name="atmosphere.standard_atmosphere",
    description=(
        "Standard atmosphere profile selector. Used by the simple model for "
        "the path-mean temperature lookup and aerosol/H2O scale heights."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="us_standard",
    enum_values=(
        "tropical",
        "midlat_summer",
        "midlat_winter",
        "subarctic_summer",
        "subarctic_winter",
        "us_standard",
    ),
    tags=frozenset({"atmosphere", "simple", "profile"}),
    default_justification=(
        "US Standard 1976 is the canonical neutral default and matches MODTRAN MODEL=6."
    ),
)


# ---------------------------------------------------------------------------
# Viewing geometry: the geometry.* namespace moved to
# radiant/geometry/_schema.py (ADR-0006 — GeometryStage owns it).
# This schema is atmosphere-model parameters only.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tabulated model
# ---------------------------------------------------------------------------

TABULATED_TRANSMITTANCE_FILE = ParameterDef(
    name="atmosphere.tabulated_transmittance_file",
    is_file_path=True,
    description=(
        "Path to CSV or NPZ file containing tabulated atmospheric "
        "transmittance. CSV: two columns (wavelength_um, value). "
        "NPZ: key 'transmittance' with matching 'wavelength_um'. "
        "Required when atmosphere.model='tabulated'."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"atmosphere", "tabulated"}),
    default_justification="Empty string = not set; only required for tabulated model.",
)

TABULATED_PATH_RADIANCE_FILE = ParameterDef(
    name="atmosphere.tabulated_path_radiance_file",
    is_file_path=True,
    description=(
        "Path to CSV or NPZ file containing tabulated path radiance "
        "[W/m^2/sr/um]. Required when atmosphere.model='tabulated'."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"atmosphere", "tabulated"}),
    default_justification="Empty string = not set; only required for tabulated model.",
)

TABULATED_DOWNWELLING_FILE = ParameterDef(
    name="atmosphere.tabulated_downwelling_file",
    is_file_path=True,
    description=(
        "Path to CSV file containing tabulated downwelling atmospheric "
        "emission [W/m^2/sr/um]. Optional; defaults to zeros if not provided."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"atmosphere", "tabulated"}),
    default_justification="Empty string = not set; optional even for tabulated model.",
)

# ---------------------------------------------------------------------------
# MODTRAN model
# ---------------------------------------------------------------------------

MODTRAN_TAPE7_PATH = ParameterDef(
    name="atmosphere.modtran.tape7_path",
    description=(
        "Path to a MODTRAN tape7 output file produced elsewhere. When set "
        "(with atmosphere.model='modtran'), the atmospheric state is built "
        "from this file — parsed before chain execution (Rule 6) — and the "
        "MODTRAN binary, cache, and fallback are never consulted. Unset "
        "(empty) leaves the binary/cache/fallback behavior unchanged. Like "
        "tabulated files, an imported tape7 is geometry-agnostic: the "
        "arrays are served as-is for any query geometry. Airborne targets "
        "(h_tgt > 0) additionally require the target→sensor leg via "
        "atmosphere.modtran.tape7_up_path; with only this single "
        "(ground→sensor) file they are rejected."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"atmosphere", "modtran"}),
    default_justification=("Empty string = not set; the binary-invocation flavor is the default."),
)

MODTRAN_TAPE7_SUN_PATH = ParameterDef(
    name="atmosphere.modtran.tape7_sun_path",
    description=(
        "Optional sun-leg tape7 file for the two-leg split (CU-011, file "
        "flavor). Requires atmosphere.modtran.tape7_path. When set, tau_sun "
        "(the sun→target down-leg transmittance) comes from this file's "
        "TOT TRANS column — a MODTRAN run along the solar-zenith slant "
        "path — instead of aliasing the up-leg transmittance, and the "
        "single-tau collapse warning is not emitted. Unset, tau_sun "
        "aliases tau_up with a UserWarning, as before."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"atmosphere", "modtran"}),
    default_justification=(
        "Empty string = not set; single-file imports collapse the two-leg split with a warning."
    ),
)

MODTRAN_TAPE7_UP_PATH = ParameterDef(
    name="atmosphere.modtran.tape7_up_path",
    description=(
        "Optional target→sensor up-leg tape7 file for airborne targets "
        "(Gap 94, file flavor). Requires atmosphere.modtran.tape7_path "
        "(which then supplies the ground→sensor full column the "
        "background branch needs). When set, tau_up and L_path_up (the "
        "target→sensor partial column) come from this file — a MODTRAN "
        "run with H2 = the target altitude — enabling h_tgt > 0 on the "
        "file-import path. The user owns geometry consistency: nothing "
        "in the file records H2, so this file must actually be the run "
        "matching the scenario's target altitude and LOS zenith. Unset, "
        "airborne targets are rejected on the file-import path."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"atmosphere", "modtran"}),
    default_justification=(
        "Empty string = not set; single-file imports serve surface targets only."
    ),
)

MODTRAN_FLUX_PATH = ParameterDef(
    name="atmosphere.modtran.flux_path",
    description=(
        "Optional MODTRAN spectral flux CSV (a Block E irradiance run's "
        "*_flux.csv sidecar) supplying the downwelling sky irradiance for "
        "the tape7-import path (CU-157, Gap 38). Requires "
        "atmosphere.modtran.tape7_path. When set, the ground-level DOWN "
        "column (thermal emission + scattered solar) feeds the sky-"
        "reflection terms: E_sky_scattered from the reflective-solar band "
        "and E_sky_thermal from the thermal band — superseding the Gap 81 "
        "zero for flux-equipped imports. Unset, a standard IEMSCT=2 tape7 "
        "carries no downwelling column, so both terms stay zero (Gap 81)."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"atmosphere", "modtran"}),
    default_justification=(
        "Empty string = not set; a tape7 import without a flux file keeps the "
        "Gap 81 zero downwelling."
    ),
)

MODTRAN_BINARY_PATH = ParameterDef(
    name="atmosphere.modtran.binary_path",
    description="Path to the MODTRAN executable.",
    dtype=str,
    canonical_unit="",
    input_unit="",
    default=default_modtran_binary_str(),
    tags=frozenset({"atmosphere", "modtran"}),
    default_justification=(
        "MODTRAN on PATH if present, else the conventional per-platform install "
        "location (POSIX /usr/local/bin/modtran; Windows Program Files). Availability "
        "is authoritatively checked at run time (CU-151, Rule 30)."
    ),
)

MODTRAN_CACHE_DIR = ParameterDef(
    name="atmosphere.modtran.cache_dir",
    description=(
        "Directory for caching MODTRAN tape7 results. Keyed by SHA-256 "
        "hash of the rendered tape5 deck."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="~/.radiant/modtran_cache",
    tags=frozenset({"atmosphere", "modtran"}),
    default_justification="User-local cache directory.",
)

MODTRAN_ALLOW_FALLBACK = ParameterDef(
    name="atmosphere.modtran.allow_fallback",
    description=(
        "If True and MODTRAN binary is unavailable, fall back to "
        "SimpleAtmosphere with translated parameters."
    ),
    dtype=bool,
    canonical_unit="",
    input_unit="",
    default=False,
    tags=frozenset({"atmosphere", "modtran"}),
    default_justification="Fail explicitly by default; user must opt in to fallback.",
)

MODTRAN_ATMOSPHERE_PROFILE = ParameterDef(
    name="atmosphere.modtran.atmosphere_profile",
    description=(
        "Standard atmosphere profile for MODTRAN (maps to MODEL card). "
        "Same enum as atmosphere.standard_atmosphere."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="us_standard",
    enum_values=(
        "tropical",
        "midlat_summer",
        "midlat_winter",
        "subarctic_summer",
        "subarctic_winter",
        "us_standard",
    ),
    tags=frozenset({"atmosphere", "modtran"}),
    default_justification="US Standard 1976 = MODEL 6 in MODTRAN.",
)

MODTRAN_AEROSOL_MODEL = ParameterDef(
    name="atmosphere.modtran.aerosol_model",
    description="Aerosol model for MODTRAN (maps to IHAZE card).",
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="rural",
    enum_values=("none", "rural", "maritime", "urban", "tropospheric"),
    tags=frozenset({"atmosphere", "modtran"}),
    default_justification="Rural (IHAZE=1) is the standard default.",
)

MODTRAN_H2O_SCALE = ParameterDef(
    name="atmosphere.modtran.h2o_scale",
    description="Water vapor column scaling factor for MODTRAN.",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=1.0,
    bounds=(0.01, 10.0),
    tags=frozenset({"atmosphere", "modtran"}),
    default_justification="1.0 = no scaling from the selected atmosphere profile.",
)

MODTRAN_O3_SCALE = ParameterDef(
    name="atmosphere.modtran.o3_scale",
    description="Ozone column scaling factor for MODTRAN.",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=1.0,
    bounds=(0.01, 10.0),
    tags=frozenset({"atmosphere", "modtran"}),
    default_justification="1.0 = no scaling from the selected atmosphere profile.",
)

MODTRAN_SPECTRAL_RESOLUTION_CM1 = ParameterDef(
    name="atmosphere.modtran.spectral_resolution_cm1",
    description="Spectral resolution [cm-1] for the MODTRAN computation.",
    dtype=float,
    canonical_unit="cm-1",
    input_unit="cm-1",
    default=1.0,
    bounds=(0.1, 100.0),
    tags=frozenset({"atmosphere", "modtran"}),
    default_justification="1 cm-1 is a common moderate-resolution setting.",
)

# ---------------------------------------------------------------------------
# Interpolated model
# ---------------------------------------------------------------------------

INTERPOLATED_DATA_DIR = ParameterDef(
    name="atmosphere.interpolated_data_dir",
    description=(
        "Directory containing pre-computed atmosphere runs (NPZ files) "
        "at discrete geometry points for the interpolated model. Empty "
        "(the default) uses the bundled atmosphere library family "
        "matching atmosphere.interpolation_axes: 'path_zenith_rad' → "
        "us_standard_zenith_fan (LOS zenith 0–60°), "
        "'sensor_altitude_m,target_altitude_m' → midlat_summer_ladders "
        "(35 km–GEO × 0–29 km). Other axes combinations require an "
        "explicit directory."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"atmosphere", "interpolated"}),
    default_justification=(
        "Empty string = use the shipped library family matching interpolation_axes."
    ),
)

INTERPOLATION_AXES = ParameterDef(
    name="atmosphere.interpolation_axes",
    description=(
        "Comma-separated list of geometry fields to interpolate over, "
        "e.g. 'path_zenith_rad' or 'path_zenith_rad,sensor_altitude_m'."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="path_zenith_rad",
    tags=frozenset({"atmosphere", "interpolated"}),
    default_justification="Zenith angle is the most common single-axis sweep.",
)

INTERPOLATION_METHOD = ParameterDef(
    name="atmosphere.interpolation_method",
    description="Interpolation method: 'linear' or 'nearest'.",
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="linear",
    enum_values=("linear", "nearest"),
    tags=frozenset({"atmosphere", "interpolated"}),
    default_justification="Linear is the standard default for smooth fields.",
)


# ---------------------------------------------------------------------------
# Turbulence
# ---------------------------------------------------------------------------

FRIED_PARAMETER_M = ParameterDef(
    name="atmosphere.r0_m",
    description=(
        "Fried coherence diameter r₀ [m] at the operating wavelength. "
        "Controls long-exposure Kolmogorov turbulence MTF. "
        "Set to 0 to disable turbulence effects."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 10.0),
    tags=frozenset({"atmosphere", "turbulence"}),
    default_justification=(
        "0.0 disables turbulence by default; users must opt-in by setting "
        "a positive r₀ value for their specific scenario."
    ),
)

R0_REFERENCE_WAVELENGTH_UM = ParameterDef(
    name="atmosphere.r0_reference_wavelength_um",
    description=(
        "Wavelength [µm] that atmosphere.r0_m is quoted at (CU-228). Seeing is "
        "habitually reported at 0.5 µm, but r₀ is strongly wavelength-dependent "
        "(r₀ ∝ λ^(6/5)), so an r₀ entered at 500 nm and applied at 4 µm is ~8x "
        "too small — a silent order-of-magnitude error in the turbulence MTF. "
        "When set, r0_resolution rescales the entered value to the band centre "
        "by (λ_band / λ_ref)^(6/5). The default 0.0 means 'the value I entered "
        "is already at the operating wavelength' and preserves the pre-CU-228 "
        "behaviour bit-identically. Ignored unless atmosphere.r0_m is set "
        "directly (a Cn² profile derives r₀ at the band centre already)."
    ),
    dtype=float,
    canonical_unit="um",
    input_unit="um",
    default=0.0,
    bounds=(0.0, 100.0),
    tags=frozenset({"atmosphere", "turbulence"}),
    default_justification=(
        "0.0 is the Rule-12 'not set' sentinel: it keeps every existing config "
        "bit-identical, because rescaling by an undeclared reference would "
        "silently change results for scenes that never opted in."
    ),
)

CN2_PROFILE = ParameterDef(
    name="atmosphere.cn2_profile",
    description=(
        "Optical-turbulence profile Cn²(h) used to derive the Fried parameter "
        "(Gap 110). 'direct' (default) uses atmosphere.r0_m as given — the "
        "pre-Gap-110 behaviour. 'hufnagel_valley' integrates the analytic HV "
        "profile along the line of sight (parameters cn2_hv_wind_rms_m_s and "
        "cn2_hv_ground_strength; the defaults are HV-5/7). 'tabulated' uses the "
        "two-column CSV named by atmosphere.cn2_tabulated_file."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="direct",
    enum_values=("direct", "hufnagel_valley", "tabulated"),
    tags=frozenset({"atmosphere", "turbulence"}),
    default_justification=(
        "'direct' reproduces the pre-Gap-110 r₀ input exactly; the "
        "profile-driven path activates only when the user selects it."
    ),
)

CN2_HV_WIND_RMS_M_S = ParameterDef(
    name="atmosphere.cn2_hv_wind_rms_m_s",
    description=(
        "Hufnagel-Valley RMS upper-atmosphere (5–20 km) wind speed w [m/s]. "
        "Scales the jet-stream term of Cn²(h). Used only when "
        "atmosphere.cn2_profile = 'hufnagel_valley'."
    ),
    dtype=float,
    canonical_unit="m/s",
    input_unit="m/s",
    default=21.0,
    bounds=(0.0, 100.0),
    tags=frozenset({"atmosphere", "turbulence"}),
    default_justification=(
        "21 m/s is the HV-5/7 value (Andrews & Phillips 2005 §12.2.2), which "
        "with the default ground strength yields r₀ = 5 cm and θ₀ = 7 µrad at "
        "0.5 µm for a vertical path."
    ),
)

CN2_HV_GROUND_STRENGTH = ParameterDef(
    name="atmosphere.cn2_hv_ground_strength",
    description=(
        "Hufnagel-Valley ground-level structure constant A [m^(-2/3)]. Scales "
        "the 100 m-scale-height surface layer of Cn²(h). Used only when "
        "atmosphere.cn2_profile = 'hufnagel_valley'."
    ),
    dtype=float,
    canonical_unit="m^(-2/3)",
    input_unit="m^(-2/3)",
    default=1.7e-14,
    bounds=(0.0, 1.0e-10),
    tags=frozenset({"atmosphere", "turbulence"}),
    default_justification=(
        "1.7e-14 m^(-2/3) is the HV-5/7 value (Andrews & Phillips 2005 "
        "§12.2.2) — a typical daytime near-surface value at a good site."
    ),
)

CN2_TABULATED_FILE = ParameterDef(
    name="atmosphere.cn2_tabulated_file",
    description=(
        "Two-column CSV 'altitude_m,cn2_m^-2/3' (ascending altitude, '#' "
        "comments allowed) defining a measured or externally-modelled Cn²(h) "
        "profile. Required when atmosphere.cn2_profile = 'tabulated'. Read "
        "before chain execution (Rule 6) and injected at "
        "stage_outputs['atmosphere_config']['cn2_profile']."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    is_file_path=True,
    tags=frozenset({"atmosphere", "turbulence"}),
    default_justification="Empty = no tabulated profile (the 'tabulated' selector then raises).",
)

TURBULENCE_WAVE_TYPE = ParameterDef(
    name="atmosphere.turbulence_wave_type",
    description=(
        "Path weighting for the profile-driven Fried parameter. 'plane' "
        "(default) weights every slab equally — the source is effectively at "
        "infinity, which is the imaging case and the convention published r₀ "
        "values use. 'spherical' weights each slab by (fractional distance "
        "from the target)^(5/3), peaking at the aperture — the finite-range "
        "point-source case. Ignored when atmosphere.cn2_profile = 'direct'."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="plane",
    enum_values=("plane", "spherical"),
    tags=frozenset({"atmosphere", "turbulence"}),
    default_justification=(
        "Plane-wave is the imaging convention and reproduces the literature "
        "r₀ values for a given Cn² profile."
    ),
)


ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    ATMOSPHERE_MODEL,
    # Simple parametric
    VISIBILITY_KM,
    AEROSOL_TYPE,
    PRECIPITABLE_WATER_CM,
    STANDARD_ATMOSPHERE,
    # Tabulated
    TABULATED_TRANSMITTANCE_FILE,
    TABULATED_PATH_RADIANCE_FILE,
    TABULATED_DOWNWELLING_FILE,
    # MODTRAN
    MODTRAN_TAPE7_PATH,
    MODTRAN_TAPE7_SUN_PATH,
    MODTRAN_TAPE7_UP_PATH,
    MODTRAN_FLUX_PATH,
    MODTRAN_BINARY_PATH,
    MODTRAN_CACHE_DIR,
    MODTRAN_ALLOW_FALLBACK,
    MODTRAN_ATMOSPHERE_PROFILE,
    MODTRAN_AEROSOL_MODEL,
    MODTRAN_H2O_SCALE,
    MODTRAN_O3_SCALE,
    MODTRAN_SPECTRAL_RESOLUTION_CM1,
    # Interpolated
    INTERPOLATED_DATA_DIR,
    INTERPOLATION_AXES,
    INTERPOLATION_METHOD,
    # Turbulence
    FRIED_PARAMETER_M,
    R0_REFERENCE_WAVELENGTH_UM,
    CN2_PROFILE,
    CN2_HV_WIND_RMS_M_S,
    CN2_HV_GROUND_STRENGTH,
    CN2_TABULATED_FILE,
    TURBULENCE_WAVE_TYPE,
)
