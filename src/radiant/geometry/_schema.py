"""Parameter schema for GeometryStage (stage 0) — the geometry.* namespace.

Owns every scene-geometry parameter: where the sensor, target, and sun
are, and how the user chooses to express that (input modes V0–V4/V6,
S0–S3 — see docs/architecture/RADIANT_Geometry.md and ADR-0006).

History: the seven core ``geometry.*`` definitions moved here verbatim
from ``atmosphere/_schema.py`` (which owned the namespace by historical
accident); ``geometry.target_range_m`` moved from
``source/_schema.py``'s ``source.target.range_m`` with a deprecated
alias.  Values, bounds, and defaults are unchanged — the move is
ownership-only (zero drift).

Mode-entry parameters (``sensor_off_nadir_rad``, ``ground_range_m``,
``elevation_angle_rad``, ``solar_elevation_rad``, the site/time solar
inputs, ``circular_orbit``) are alternate doors into the canonical
representation.  Their defaults are inert: mode detection is by
provenance (a parameter left at DEFAULT provenance is "not provided"),
so the default values below are never read as user intent.
"""

from __future__ import annotations

from radiant.core.parameters import ParameterDef

# ---------------------------------------------------------------------------
# Canonical viewing geometry (moved verbatim from atmosphere/_schema.py)
# ---------------------------------------------------------------------------

SENSOR_ALTITUDE_M = ParameterDef(
    name="geometry.sensor_altitude_m",
    description=(
        "Sensor altitude above mean sea level [m]. Also the altitude the "
        "no_atmosphere 'space' sub-case uses for the Earth-limb intercept "
        "check (formerly the separate platform.h_sensor stop-gap — folded "
        "as a deprecated alias per CU-090/ADR-0006)."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=None,
    bounds=(0.0, 1e8),
    tags=frozenset({"geometry"}),
    deprecated_aliases=frozenset({"platform.h_sensor"}),
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
    description=(
        "Line-of-sight zenith angle at the TARGET (theta_o) [rad]. "
        "0 = sensor at the target's zenith (nadir view). This is the "
        "target-side angle consumed by the atmospheric path; the "
        "sensor-side off-nadir angle is geometry.sensor_off_nadir_rad."
    ),
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
# Target slant range (moved from source/_schema.py source.target.range_m)
# ---------------------------------------------------------------------------

TARGET_RANGE_M = ParameterDef(
    name="geometry.target_range_m",
    description=(
        "Observer-to-target slant range [m]. 0.0 = not specified (extended-scene default)."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 1e12),
    tags=frozenset({"geometry", "target"}),
    default_justification=(
        "0.0 signals 'range not provided' — regime classification defaults to extended scene."
    ),
    deprecated_aliases=frozenset({"source.target.range_m"}),
)

# ---------------------------------------------------------------------------
# Viewing input modes — alternate doors into theta_o (V2, V3, V4)
# Defaults are inert; mode detection is by provenance.
# ---------------------------------------------------------------------------

SENSOR_OFF_NADIR_RAD = ParameterDef(
    name="geometry.sensor_off_nadir_rad",
    description=(
        "Sensor off-nadir look angle eta [rad] — mode V2 entry. The "
        "target-side path zenith is derived via the spherical-Earth sine "
        "rule (core.los_geometry.theta_o_from_eta). Unused unless "
        "explicitly set; do not also set geometry.path_zenith_rad unless "
        "the two agree."
    ),
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=0.0,
    bounds=(0.0, 1.5707),
    tags=frozenset({"geometry", "mode_entry"}),
    default_justification="Inert — provenance-based mode detection ignores defaults.",
)

GROUND_RANGE_M = ParameterDef(
    name="geometry.ground_range_m",
    description=(
        "Surface arc distance from the sensor nadir point to the target "
        "[m] — mode V3 entry. The target-side path zenith is derived via "
        "the spherical viewing triangle. Unused unless explicitly set."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 2e7),  # half Earth circumference
    tags=frozenset({"geometry", "mode_entry"}),
    default_justification="Inert — provenance-based mode detection ignores defaults.",
)

ELEVATION_ANGLE_RAD = ParameterDef(
    name="geometry.elevation_angle_rad",
    description=(
        "Sensor elevation above the target's local horizon [rad] — mode "
        "V4 entry (grazing-angle framing). path zenith = pi/2 − elevation. "
        "Unused unless explicitly set."
    ),
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=1.5707963,
    bounds=(0.0088, 1.5708),  # 0.5° grazing floor to zenith
    tags=frozenset({"geometry", "mode_entry"}),
    default_justification=(
        "Inert (pi/2 = sensor at zenith, the nadir-view complement) — "
        "provenance-based mode detection ignores defaults."
    ),
)

# ---------------------------------------------------------------------------
# Solar input modes — alternate doors into theta_s (S2, S3)
# ---------------------------------------------------------------------------

SOLAR_ELEVATION_RAD = ParameterDef(
    name="geometry.solar_elevation_rad",
    description=(
        "Sun elevation above the target's local horizon [rad] — mode S2 "
        "entry. solar zenith = pi/2 − elevation. Unused unless explicitly set."
    ),
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=1.0707963,
    bounds=(0.0, 1.5708),
    tags=frozenset({"geometry", "mode_entry"}),
    default_justification=(
        "Inert (complement of the 0.5 rad solar-zenith default) — "
        "provenance-based mode detection ignores defaults."
    ),
)

SITE_LATITUDE_RAD = ParameterDef(
    name="geometry.site_latitude_rad",
    description=(
        "Target geodetic latitude [rad], north positive — mode S3 entry "
        "(site + time solar geometry). Combined with "
        "geometry.day_of_year and geometry.local_solar_time_h (or "
        "geometry.ltan_h) to derive the solar zenith angle. Unused "
        "unless an S3 parameter is explicitly set."
    ),
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=0.0,
    bounds=(-1.5708, 1.5708),
    tags=frozenset({"geometry", "mode_entry", "solar_site"}),
    default_justification="Inert (equator) — provenance-based mode detection ignores defaults.",
)

DAY_OF_YEAR = ParameterDef(
    name="geometry.day_of_year",
    description=("Day of year, 1–366 — mode S3 entry (site + time solar geometry)."),
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=80,
    bounds=(1, 366),
    tags=frozenset({"geometry", "mode_entry", "solar_site"}),
    default_justification=(
        "Inert (day 80 ≈ March equinox, declination ≈ 0) — "
        "provenance-based mode detection ignores defaults."
    ),
)

LOCAL_SOLAR_TIME_H = ParameterDef(
    name="geometry.local_solar_time_h",
    description=(
        "Local solar time at the target [hours, 0–24; 12.0 = solar noon] "
        "— mode S3 entry. Mutually exclusive with geometry.ltan_h."
    ),
    dtype=float,
    canonical_unit="h",
    input_unit="h",
    default=12.0,
    bounds=(0.0, 24.0),
    tags=frozenset({"geometry", "mode_entry", "solar_site"}),
    default_justification=(
        "Inert (solar noon) — provenance-based mode detection ignores defaults."
    ),
)

LTAN_H = ParameterDef(
    name="geometry.ltan_h",
    description=(
        "Local time of ascending node [hours] for a sun-synchronous "
        "orbit — mode S3 entry; the local solar time is derived via "
        "core.solar_geometry.local_solar_time_from_ltan. Mutually "
        "exclusive with geometry.local_solar_time_h."
    ),
    dtype=float,
    canonical_unit="h",
    input_unit="h",
    default=12.0,
    bounds=(0.0, 24.0),
    tags=frozenset({"geometry", "mode_entry", "solar_site"}),
    default_justification=("Inert (noon LTAN) — provenance-based mode detection ignores defaults."),
)

# ---------------------------------------------------------------------------
# Platform kinematics mode — circular orbit (V6)
# ---------------------------------------------------------------------------

CIRCULAR_ORBIT = ParameterDef(
    name="geometry.circular_orbit",
    description=(
        "Declare the platform a circular orbit at "
        "geometry.sensor_altitude_m — mode V6 entry. When true, the "
        "ground-track speed (and orbital period) are derived from the "
        "altitude via core.orbit; do not also set "
        "geometry.ground_speed_m_s unless it agrees. False = generic "
        "platform (airborne or static); ground speed is taken from "
        "geometry.ground_speed_m_s as before."
    ),
    dtype=bool,
    canonical_unit="",
    input_unit="",
    default=False,
    tags=frozenset({"geometry", "mode_entry"}),
    default_justification=("False preserves existing behavior — orbital derivation is opt-in."),
)

ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    SENSOR_ALTITUDE_M,
    TARGET_ALTITUDE_M,
    PATH_ZENITH_RAD,
    SOLAR_ZENITH_RAD,
    SOLAR_AZIMUTH_RAD,
    SOLAR_ILLUMINATION,
    GROUND_SPEED_M_S,
    TARGET_RANGE_M,
    SENSOR_OFF_NADIR_RAD,
    GROUND_RANGE_M,
    ELEVATION_ANGLE_RAD,
    SOLAR_ELEVATION_RAD,
    SITE_LATITUDE_RAD,
    DAY_OF_YEAR,
    LOCAL_SOLAR_TIME_H,
    LTAN_H,
    CIRCULAR_ORBIT,
)
