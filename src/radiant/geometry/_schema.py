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

Mode-entry parameters (``sensor_off_boresight_rad``, ``ground_range_m``,
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
        "Sensor altitude above mean sea level [m]. 0 = a ground-based "
        "sensor (legal; the LOS direction is derived from this altitude "
        "against geometry.target_altitude_m, never declared). Also the "
        "altitude the "
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

SITE_ELEVATION_M = ParameterDef(
    name="geometry.site_elevation_m",
    description=(
        "Terrain elevation of the scene's ground site above mean sea level "
        "[m] — the altitude of the SURFACE beneath the line of sight, which "
        "is NOT the same thing as the lowest point of the line of sight "
        "(CU-262). It is the reference the surface boundary layer sits on: "
        "the Hufnagel-Valley Cn2 surface term is evaluated at (h - "
        "site_elevation_m) so that a mountain-top observatory keeps its own "
        "boundary layer, while the tropopause and middle-atmosphere terms "
        "stay on mean sea level. Whose site it is follows the topology: "
        "down-looking = the terrain under the TARGET; up-looking = the "
        "terrain under the SENSOR; level = the terrain under the arm (shared "
        "- both endpoints are at the same altitude). An endpoint that is "
        "airborne over that terrain needs no special case: the 100 m scale "
        "height suppresses the surface term on its own, so a level air-to-air "
        "path more than a few hundred metres above the site carries no "
        "surface term at all. Consumed today ONLY by "
        "atmosphere.cn2_profile = 'hufnagel_valley'; a 'tabulated' Cn2 "
        "profile is taken as given against MSL and is not shifted. The "
        "default 0 reproduces every pre-CU-262 result bit-identically."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 1.0e4),
    tags=frozenset({"geometry"}),
    default_justification=(
        "Sea level — the reference every RADIANT altitude already uses, so the "
        "default changes no existing result."
    ),
)

PATH_ZENITH_RAD = ParameterDef(
    name="geometry.path_zenith_rad",
    description=(
        "Line-of-sight zenith angle at the path's LOWER endpoint [rad] — "
        "mode V1 entry (ADR-0011 decision 3). When the sensor is above the "
        "target (every classic scene) the target IS the lower endpoint, so "
        "this is the canonical target-side zenith theta_o and 0 = sensor at "
        "the target's zenith (nadir view). When the sensor is below the "
        "target it is the sensor's own zenith angle, and theta_o = pi - "
        "zeta_up is derived from it (0 = target directly overhead). The "
        "sensor-side off-boresight angle is geometry.sensor_off_boresight_rad."
    ),
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=0.0,
    # Closed [0, pi] since ADR-0011: pi is the vertical up-looking case
    # (ground sensor with the target at its zenith, LEO under GEO). Values
    # near pi/2 are rejected by the HORIZON GUARD (core.viewing_triangle),
    # not by this bound — the guard keys on the path's tangent topology,
    # which the schema cannot see.
    bounds=(0.0, 3.141592653589793),
    tags=frozenset({"geometry"}),
    default_justification="Nadir (0 rad) is the standard staring geometry.",
)

SOLAR_ZENITH_RAD = ParameterDef(
    name="geometry.solar_zenith_rad",
    description=(
        "Solar zenith angle [rad]. Domain is the full closed interval [0, π] "
        "since Geometry-Flexibility Phase 2 (ADR-0011 decision 10 / ratified "
        "decision 21): θ_s > π/2 puts the sun below the *local* horizontal, "
        "which a target high enough to clear the terminator shadow can still "
        "see. Whether a given point is lit is decided per-altitude by the "
        "shadow-height test in radiant.atmosphere.solar_shadow, not by this "
        "bound. The pre-Phase-2 bound was 1.5707 rad (a hard sun-above-horizon "
        "rule that made sunlit-target-over-dark-ground inexpressible); "
        "widening it changes no down-looking result, because every scene that "
        "was legal before keeps the same solar column."
    ),
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=0.5,
    bounds=(0.0, 3.141592653589793),
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
# Target spatial extent — projected area, shape, dimensions, orientation
# (moved verbatim from source/_schema.py per ADR-0008; the old
# source.target.* names survive as deprecated aliases).  These feed the
# projected-area computation that determines theta_target and hence the
# tentative regime — a geometry computation that previously lived in Source.
# ---------------------------------------------------------------------------

TARGET_PROJECTED_AREA = ParameterDef(
    name="geometry.target.projected_area_m2",
    description=(
        "Projected area of target facing the observer [m²]. "
        "0.0 = not specified (extended-scene default)."
    ),
    dtype=float,
    canonical_unit="m2",
    input_unit="m2",
    default=0.0,
    bounds=(0.0, 1e12),
    tags=frozenset({"source", "target", "geometry", "regime:sub_pixel", "regime:point_source"}),
    default_justification=(
        "0.0 signals 'geometry not provided' — regime classification defaults to extended scene."
    ),
    deprecated_aliases=frozenset({"source.target.projected_area_m2"}),
)

SHAPE = ParameterDef(
    name="geometry.target.shape",
    description=(
        "Geometric primitive for sub-pixel / point-source projected-area "
        "computation. 'none' = not specified (back-compat: use "
        "geometry.target.projected_area_m2).  Explicit values select a "
        "concrete shape; dimensional parameters are read from the "
        "geometry.target.shape_* scalars per the matrix §3 catalog."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="none",
    enum_values=("none", "sphere", "cylinder", "flat_plate", "box", "cone"),
    tags=frozenset(
        {"source", "target", "geometry", "shape", "regime:sub_pixel", "regime:point_source"}
    ),
    default_justification=(
        "'none' is the Rule-12 sentinel for 'shape not provided'; the "
        "descriptor falls back to geometry.target.projected_area_m2.  Users "
        "opt into shape-driven projection by naming a concrete shape."
    ),
    deprecated_aliases=frozenset({"source.target.shape"}),
)

SHAPE_RADIUS = ParameterDef(
    name="geometry.target.shape_radius_m",
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
    tags=frozenset(
        {"source", "target", "geometry", "shape", "regime:sub_pixel", "regime:point_source"}
    ),
    default_justification=(
        "0.0 is the 'not set' sentinel; the Step 1.2 factory raises "
        "ParameterBoundsError if the chosen shape needs radius_m > 0."
    ),
    deprecated_aliases=frozenset({"source.target.shape_radius_m"}),
)

SHAPE_LENGTH = ParameterDef(
    name="geometry.target.shape_length_m",
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
    tags=frozenset(
        {"source", "target", "geometry", "shape", "regime:sub_pixel", "regime:point_source"}
    ),
    default_justification="0.0 = not set; see SHAPE_RADIUS.",
    deprecated_aliases=frozenset({"source.target.shape_length_m"}),
)

SHAPE_WIDTH = ParameterDef(
    name="geometry.target.shape_width_m",
    description=(
        "Width [m] for rectangular shapes (flat_plate body-Y extent, "
        "box body-Y extent).  Ignored for sphere, cylinder, cone."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 1e6),
    tags=frozenset(
        {"source", "target", "geometry", "shape", "regime:sub_pixel", "regime:point_source"}
    ),
    default_justification="0.0 = not set; see SHAPE_RADIUS.",
    deprecated_aliases=frozenset({"source.target.shape_width_m"}),
)

SHAPE_HEIGHT = ParameterDef(
    name="geometry.target.shape_height_m",
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
    tags=frozenset(
        {"source", "target", "geometry", "shape", "regime:sub_pixel", "regime:point_source"}
    ),
    default_justification="0.0 = not set; see SHAPE_RADIUS.",
    deprecated_aliases=frozenset({"source.target.shape_height_m"}),
)

SHAPE_BASE_RADIUS = ParameterDef(
    name="geometry.target.shape_base_radius_m",
    description=(
        "Base-circle radius [m] for the cone shape.  Separate from "
        "geometry.target.shape_radius_m because the cone class names the "
        "parameter base_radius_m (see shapes/cone.py).  Ignored for "
        "non-cone shapes."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 1e6),
    tags=frozenset(
        {"source", "target", "geometry", "shape", "regime:sub_pixel", "regime:point_source"}
    ),
    default_justification="0.0 = not set; see SHAPE_RADIUS.",
    deprecated_aliases=frozenset({"source.target.shape_base_radius_m"}),
)

SHAPE_YAW = ParameterDef(
    name="geometry.target.shape_yaw_rad",
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
    tags=frozenset(
        {
            "source",
            "target",
            "geometry",
            "shape",
            "orientation",
            "regime:sub_pixel",
            "regime:point_source",
        }
    ),
    default_justification=("0.0 = body +X aligned with scene +X (canonical alignment)."),
    deprecated_aliases=frozenset({"source.target.shape_yaw_rad"}),
)

SHAPE_PITCH = ParameterDef(
    name="geometry.target.shape_pitch_rad",
    description=("Target body pitch [rad] about scene +Y (ZYX Euler, Rule 3)."),
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=0.0,
    bounds=(-6.283185307179586, 6.283185307179586),
    tags=frozenset(
        {
            "source",
            "target",
            "geometry",
            "shape",
            "orientation",
            "regime:sub_pixel",
            "regime:point_source",
        }
    ),
    default_justification="0.0 = canonical alignment; see SHAPE_YAW.",
    deprecated_aliases=frozenset({"source.target.shape_pitch_rad"}),
)

SHAPE_ROLL = ParameterDef(
    name="geometry.target.shape_roll_rad",
    description=("Target body roll [rad] about scene +X (ZYX Euler, Rule 3)."),
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=0.0,
    bounds=(-6.283185307179586, 6.283185307179586),
    tags=frozenset(
        {
            "source",
            "target",
            "geometry",
            "shape",
            "orientation",
            "regime:sub_pixel",
            "regime:point_source",
        }
    ),
    default_justification="0.0 = canonical alignment; see SHAPE_YAW.",
    deprecated_aliases=frozenset({"source.target.shape_roll_rad"}),
)

# ---------------------------------------------------------------------------
# Viewing input modes — alternate doors into theta_o (V2, V3, V4)
# Defaults are inert; mode detection is by provenance.
# ---------------------------------------------------------------------------

SENSOR_OFF_NADIR_RAD = ParameterDef(
    name="geometry.sensor_off_boresight_rad",
    description=(
        "Sensor off-BORESIGHT angle [rad] — mode V2 entry. The reference "
        "axis is resolved from the altitudes (ADR-0011), never declared: "
        "the sensor's NADIR when the sensor is above the target (the "
        "classic off-nadir look angle eta, converted to the target-side "
        "path zenith by the spherical-Earth sine rule, "
        "core.los_geometry.theta_o_from_eta), and the sensor's ZENITH when "
        "the sensor is at or below the target — where the sensor is the "
        "path's lower endpoint, so the entered angle already is the "
        "lower-endpoint zenith and theta_o is derived from it. Unused "
        "unless explicitly set; do not also set geometry.path_zenith_rad "
        "unless the two agree."
    ),
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=0.0,
    bounds=(0.0, 1.5707),
    tags=frozenset({"geometry", "mode_entry"}),
    # CU-231's sibling: the old name said off_NADIR while the parameter has meant
    # off-BORESIGHT since ADR-0011 resolved the reference axis from the altitudes.
    # A name that contradicts its own description invites precisely the
    # wrong-hemisphere entry ADR-0011's agreement checks exist to catch. The old
    # dot-path keeps working (warn-and-redirect), so existing YAML and scripts load
    # unchanged — the `source.target.range_m` precedent.
    deprecated_aliases=frozenset({"geometry.sensor_off_nadir_rad"}),
    default_justification="Inert — provenance-based mode detection ignores defaults.",
)

GROUND_RANGE_M = ParameterDef(
    name="geometry.ground_range_m",
    description=(
        "Surface arc distance between the sensor's ground point and the "
        "target's ground point [m] — mode V3 entry. Direction-free: the "
        "arc fixes the central angle Delta = arc / R_E whichever endpoint "
        "is higher, and the spherical viewing triangle is solved for that "
        "ordering. Unused unless explicitly set."
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
        "Elevation of the line of sight above the local horizontal AT THE "
        "PATH'S LOWER ENDPOINT [rad] — mode V4 entry (grazing-angle "
        "framing). lower-endpoint zenith = pi/2 - elevation; for the "
        "classic sensor-above-target scene the lower endpoint is the "
        "target, so this is the sensor's elevation seen from the target "
        "and path zenith = pi/2 - elevation exactly as before. NEGATIVE "
        "elevation is legal since ADR-0011 — the path leaves its lower "
        "endpoint on a descending shoulder (a level or near-level arm sags "
        "below the horizontal). Unused unless explicitly set."
    ),
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=1.5707963,
    # [-pi/2, pi/2]: the full elevation range in both hemispheres. The old
    # 0.0088 rad (0.5°) grazing floor is superseded by the horizon guard,
    # which judges the path's tangent topology rather than the raw angle.
    bounds=(-1.5708, 1.5708),
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

# ---------------------------------------------------------------------------
# Optional scene-class assertion (ADR-0011 decision 8)
# NOT an input mode: it is a *validated assertion* against the derivation, not
# a door onto a canonical quantity, so it carries no ``mode_entry`` tag and
# does not appear in the mode manifest.
# ---------------------------------------------------------------------------

SCENE_CLASS = ParameterDef(
    name="geometry.scene_class",
    description=(
        "OPTIONAL assertion of the scene class — the observer x target "
        "altitude-band label of the ADR-0011 taxonomy "
        "(ground: h < 1 km; air: 1-100 km; space: h > 100 km, the h_atm_top "
        "convention). The class is ALWAYS derived from "
        "geometry.sensor_altitude_m and geometry.target_altitude_m and "
        "published as stage_outputs['geometry']['scene_class']; setting this "
        "parameter does not select anything, it ASSERTS what the altitudes "
        "should derive. If the assertion disagrees with the derivation the "
        "stage raises GeometrySpecificationError naming both — which is how a "
        "wrong-magnitude altitude typo (600 m where 600 km was meant) is "
        "caught, since pure derivation renders it as a self-consistent scene "
        "of the wrong class. Physics NEVER branches on the class (ADR-0011 "
        "decision 8): it drives defaults, metric relevance, validation, and "
        "GUI composition only. 'auto' = unset (no assertion, the default)."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="auto",
    enum_values=(
        "auto",
        "ground_to_ground",
        "ground_to_air",
        "ground_to_space",
        "air_to_ground",
        "air_to_air",
        "air_to_space",
        "space_to_ground",
        "space_to_air",
        "space_to_space",
    ),
    tags=frozenset({"geometry", "scene_class"}),
    default_justification=(
        "'auto' is the Rule-12 sentinel for 'not asserted' — the assertion is "
        "never required (ADR-0011 decision 8 rejects a mandatory declaration), "
        "so every existing configuration is unaffected."
    ),
)

# ---------------------------------------------------------------------------
# Target kinematics — the two doors onto the LOS angular rate (Gap 111)
# Defaults are inert; mode detection is by provenance.
# ---------------------------------------------------------------------------

LOS_ANGULAR_RATE_RAD_S = ParameterDef(
    name="geometry.los_angular_rate_rad_s",
    description=(
        "Line-of-sight angular rate [rad/s] entered DIRECTLY — mode K1, the "
        "first of the two Gap 111 doors. This is the rate at which the "
        "sensor-target LOS direction rotates, |v_rel,perp| / slant_range, "
        "including both platform and target motion. Use it when the rate is "
        "known (a tracker's measured slew) rather than the velocities. The "
        "alternative door is the target-velocity triple "
        "(geometry.target_speed_m_s / target_heading_rad / target_climb_rad), "
        "from which the same rate is derived; setting both is legal only if "
        "they agree within 1% (ADR-0006 rule 2). Unused unless explicitly "
        "set: with neither door set the published rate is the platform-only "
        "value derived from geometry.ground_speed_m_s."
    ),
    dtype=float,
    canonical_unit="rad/s",
    input_unit="rad/s",
    default=0.0,
    bounds=(0.0, 1.0e4),
    tags=frozenset({"geometry", "mode_entry", "kinematics"}),
    default_justification="Inert — provenance-based mode detection ignores defaults.",
)

TARGET_SPEED_M_S = ParameterDef(
    name="geometry.target_speed_m_s",
    description=(
        "Target speed [m/s] — mode K2 entry (target-velocity door, Gap 111). "
        "Magnitude only; direction is geometry.target_heading_rad (azimuth) "
        "and geometry.target_climb_rad (elevation). 0 = a stationary target, "
        "which is the default and reduces the published LOS rate exactly to "
        "the platform-only value. Combined with the platform ground-track "
        "velocity into the relative LOS rate by "
        "radiant.geometry.los_rate."
    ),
    dtype=float,
    canonical_unit="m/s",
    input_unit="m/s",
    default=0.0,
    bounds=(0.0, 1.0e6),
    tags=frozenset({"geometry", "mode_entry", "kinematics", "target"}),
    default_justification=(
        "0 = stationary target — the pre-Gap-111 behaviour of every existing "
        "configuration, and inert for provenance-based mode detection."
    ),
)

TARGET_HEADING_RAD = ParameterDef(
    name="geometry.target_heading_rad",
    description=(
        "Target heading [rad] — mode K2 entry. Azimuth of the target's "
        "horizontal velocity in the TARGET'S local horizontal plane, measured "
        "from the observer's ground azimuth: the same zero "
        "geometry.solar_azimuth_rad / delta_phi is measured from "
        "(delta_phi = phi_s - phi_o with phi_o = 0), and the same rotational "
        "sense (counter-clockwise seen from above). 0 = the target moves "
        "horizontally TOWARD the sensor's ground point; pi = directly away; "
        "+pi/2 = crossing, in the platform's ground-track direction (RADIANT "
        "models the platform track as cross-track to the LOS azimuth plane — "
        "see radiant.geometry.los_rate for that simplification). DEGENERATE "
        "for a radial line of sight (path_zenith_rad = 0 or pi, i.e. the "
        "sensor or the target straight overhead): the zero azimuth is the "
        "sensor's ground point, which does not exist at zero ground range, "
        "and every heading then gives the same LOS rate. Any value is "
        "equally correct there (0 is conventional) — see "
        "radiant.geometry.los_rate 'Degenerate azimuth at a radial LOS'. "
        "Unused unless explicitly set."
    ),
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=0.0,
    bounds=(-6.283185307179586, 6.283185307179586),  # [-2π, 2π]
    tags=frozenset({"geometry", "mode_entry", "kinematics", "target"}),
    default_justification="Inert — provenance-based mode detection ignores defaults.",
)

TARGET_CLIMB_RAD = ParameterDef(
    name="geometry.target_climb_rad",
    description=(
        "Target climb angle [rad] — mode K2 entry. Elevation of the target's "
        "velocity above its own local horizontal plane, positive up: 0 = level "
        "flight, +pi/2 = vertical ascent, -pi/2 = vertical descent. Combined "
        "with geometry.target_speed_m_s and geometry.target_heading_rad into "
        "the target velocity vector. Unused unless explicitly set."
    ),
    dtype=float,
    canonical_unit="rad",
    input_unit="rad",
    default=0.0,
    bounds=(-1.5707963267948966, 1.5707963267948966),  # [-π/2, π/2]
    tags=frozenset({"geometry", "mode_entry", "kinematics", "target"}),
    default_justification="Inert (level flight) — provenance-based detection ignores defaults.",
)

ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    SENSOR_ALTITUDE_M,
    TARGET_ALTITUDE_M,
    SITE_ELEVATION_M,
    PATH_ZENITH_RAD,
    SOLAR_ZENITH_RAD,
    SOLAR_AZIMUTH_RAD,
    SOLAR_ILLUMINATION,
    GROUND_SPEED_M_S,
    TARGET_RANGE_M,
    TARGET_PROJECTED_AREA,
    SHAPE,
    SHAPE_RADIUS,
    SHAPE_LENGTH,
    SHAPE_WIDTH,
    SHAPE_HEIGHT,
    SHAPE_BASE_RADIUS,
    SHAPE_YAW,
    SHAPE_PITCH,
    SHAPE_ROLL,
    SENSOR_OFF_NADIR_RAD,
    GROUND_RANGE_M,
    ELEVATION_ANGLE_RAD,
    SOLAR_ELEVATION_RAD,
    SITE_LATITUDE_RAD,
    DAY_OF_YEAR,
    LOCAL_SOLAR_TIME_H,
    LTAN_H,
    CIRCULAR_ORBIT,
    SCENE_CLASS,
    LOS_ANGULAR_RATE_RAD_S,
    TARGET_SPEED_M_S,
    TARGET_HEADING_RAD,
    TARGET_CLIMB_RAD,
)
