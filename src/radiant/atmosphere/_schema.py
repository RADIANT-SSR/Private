"""Parameter definitions for the atmosphere stage.

Covers all four atmosphere models (simple, exo, tabulated, modtran)
plus the interpolated model and viewing geometry parameters.
"""

from __future__ import annotations

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
# Viewing geometry (consumed by AtmosphereStage; namespace = geometry.*)
# ---------------------------------------------------------------------------

SENSOR_ALTITUDE_M = ParameterDef(
    name="geometry.sensor_altitude_m",
    description="Sensor altitude above mean sea level [m].",
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=None,
    bounds=(0.0, 1e8),
    tags=frozenset({"geometry"}),
)

TARGET_ALTITUDE_M = ParameterDef(
    name="geometry.target_altitude_m",
    description="Target altitude above mean sea level [m].",
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 1e8),
    tags=frozenset({"geometry"}),
    default_justification="Ground-level target is the common case.",
)

PATH_ZENITH_RAD = ParameterDef(
    name="geometry.path_zenith_rad",
    description="Line-of-sight zenith angle [rad].",
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=0.0,
    bounds=(0.0, 1.562),  # ~89.5 deg
    tags=frozenset({"geometry"}),
    default_justification="Nadir (0 rad) is the standard staring geometry.",
)

SOLAR_ZENITH_RAD = ParameterDef(
    name="geometry.solar_zenith_rad",
    description="Solar zenith angle [rad].",
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=0.5,
    bounds=(0.0, 1.5707),
    tags=frozenset({"geometry"}),
    default_justification="~28.6° — moderate solar elevation.",
)

SOLAR_AZIMUTH_RAD = ParameterDef(
    name="geometry.solar_azimuth_rad",
    description="Sun-to-sensor relative azimuth [rad].",
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=0.0,
    bounds=(-6.2832, 6.2832),
    tags=frozenset({"geometry"}),
    default_justification="Same meridional plane.",
)

SOLAR_ILLUMINATION = ParameterDef(
    name="geometry.solar_illumination",
    description=(
        "Day/night solar toggle (Gap 59). 'day' (default) illuminates "
        "reflective and mixed (T2/T3) targets with the sun at "
        "geometry.solar_zenith_rad — the historical behavior, in which the "
        "0.5 rad zenith default meant every T2/T3 scene carried a daytime "
        "sun. 'night' removes the solar terms entirely (theta_s = None: no "
        "direct-solar reflection, no single-scatter solar sky) while "
        "thermal self-emission and reflected THERMAL downwelling remain — "
        "the physically correct nighttime mixed scene. Pure-thermal "
        "targets (T1) never carry a solar term either way."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="day",
    enum_values=("day", "night"),
    tags=frozenset({"geometry"}),
    default_justification=(
        "'day' preserves every existing configuration bit-for-bit; night "
        "was previously inexpressible for T2/T3 targets."
    ),
)

GROUND_SPEED_M_S = ParameterDef(
    name="geometry.ground_speed_m_s",
    description="Ground-track speed [m/s]. For LEO at 600 km: ~6900 m/s.",
    dtype=float,
    canonical_unit="m/s",
    input_unit="m/s",
    default=0.0,
    bounds=(0.0, 50_000.0),
    tags=frozenset({"geometry"}),
    default_justification="0 = not set; access rate skipped.",
)


# ---------------------------------------------------------------------------
# Tabulated model
# ---------------------------------------------------------------------------

TABULATED_TRANSMITTANCE_FILE = ParameterDef(
    name="atmosphere.tabulated_transmittance_file",
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
        "arrays are served as-is for any query geometry, and airborne "
        "targets (h_tgt > 0) are rejected."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"atmosphere", "modtran"}),
    default_justification=("Empty string = not set; the binary-invocation flavor is the default."),
)

MODTRAN_BINARY_PATH = ParameterDef(
    name="atmosphere.modtran.binary_path",
    description="Path to the MODTRAN executable.",
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="/usr/local/bin/modtran",
    tags=frozenset({"atmosphere", "modtran"}),
    default_justification="Common install location for MODTRAN.",
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
        "at discrete geometry points for the interpolated model. "
        "Required when atmosphere.model='interpolated'."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="",
    tags=frozenset({"atmosphere", "interpolated"}),
    default_justification="Empty string = not set; only required for interpolated model.",
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
    # Geometry
    SENSOR_ALTITUDE_M,
    TARGET_ALTITUDE_M,
    PATH_ZENITH_RAD,
    SOLAR_ZENITH_RAD,
    SOLAR_AZIMUTH_RAD,
    SOLAR_ILLUMINATION,
    GROUND_SPEED_M_S,
)
