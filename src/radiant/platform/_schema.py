"""Parameter definitions for the platform stage.

Covers jitter (random pointing errors) and smear (linear motion blur)
from platform dynamics. See ``docs/architecture/RADIANT_Spatial_Complete.md`` §7, §10.2.

Stop-gap — ``platform.h_sensor``
--------------------------------
:data:`H_SENSOR_M` is a narrowly-scoped ParameterDef introduced in
Stage 7 of the Option C Implementation Plan to support the
``no_atmosphere`` sub-case ``space`` Earth-intercept precondition
(matrix §7).  It carries the sensor altitude [m] above MSL.

The SensorDescriptor follow-on ADR (referenced in matrix §4.4) will
subsume this parameter into a first-class ``SensorDescriptor`` with
full sensor geometry; until that lands, ``platform.h_sensor`` is the
minimum viable carrier.  Do **not** retrofit this parameter into
unrelated schemas or lean on it for anything except the Stage-7
``space`` sub-case Earth-intercept check.

The default is ``0.0`` (ground); the Stage-7 space arm explicitly
raises a ``ParameterBoundsError`` if the user sets
``source.no_atmosphere_subcase == "space"`` without supplying a
positive ``platform.h_sensor`` — a wrong default at the assembly
boundary would produce a silent non-physical result (Rule 17).
"""

from __future__ import annotations

from radiant.core.parameters import ParameterDef

# ---------------------------------------------------------------------------
# Jitter — random angular pointing error during integration
# ---------------------------------------------------------------------------

JITTER_RMS_URAD = ParameterDef(
    name="platform.jitter_rms_urad",
    description=(
        "Isotropic jitter RMS [µrad]. Applied equally to both axes. Set to 0 to disable jitter."
    ),
    dtype=float,
    canonical_unit="rad",
    input_unit="urad",
    default=0.0,
    bounds=(0.0, 1e6),
    tags=frozenset({"platform", "jitter"}),
    default_justification="Zero means no jitter (perfect pointing).",
)

JITTER_AXES = ParameterDef(
    name="platform.jitter_axes",
    description=(
        "Jitter mode: 'isotropic' uses jitter_rms_urad for both axes, "
        "'anisotropic' uses separate x/y values."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="isotropic",
    tags=frozenset({"platform", "jitter"}),
)

JITTER_RMS_X_URAD = ParameterDef(
    name="platform.jitter_rms_x_urad",
    description=("Cross-track jitter RMS [µrad]. Only used when jitter_axes='anisotropic'."),
    dtype=float,
    canonical_unit="rad",
    input_unit="urad",
    default=0.0,
    bounds=(0.0, 1e6),
    tags=frozenset({"platform", "jitter"}),
    default_justification="Zero means no cross-track jitter.",
)

JITTER_RMS_Y_URAD = ParameterDef(
    name="platform.jitter_rms_y_urad",
    description=("Along-track jitter RMS [µrad]. Only used when jitter_axes='anisotropic'."),
    dtype=float,
    canonical_unit="rad",
    input_unit="urad",
    default=0.0,
    bounds=(0.0, 1e6),
    tags=frozenset({"platform", "jitter"}),
    default_justification="Zero means no along-track jitter.",
)

# ---------------------------------------------------------------------------
# Smear — platform linear motion blur during integration
# ---------------------------------------------------------------------------

GROUND_VELOCITY_M_S = ParameterDef(
    name="platform.ground_velocity_m_s",
    description=(
        "Platform along-track ground velocity [m/s]. "
        "For LEO at 600 km altitude: ~6900 m/s. "
        "Set to 0 to disable velocity-based smear."
    ),
    dtype=float,
    canonical_unit="m/s",
    input_unit="m/s",
    default=0.0,
    bounds=(0.0, 50_000.0),
    tags=frozenset({"platform", "smear"}),
    default_justification="0 = no platform motion (backward compatible).",
)

SMEAR_LENGTH_UM = ParameterDef(
    name="platform.smear_length_um",
    description=(
        "Direct focal-plane smear input [µm]. "
        "Bypasses the velocity/altitude computation. "
        "If set (> 0), takes precedence over ground_velocity_m_s. "
        "Set to 0 to use velocity-based computation instead."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="um",
    default=0.0,
    bounds=(0.0, 1000.0),
    tags=frozenset({"platform", "smear"}),
    default_justification="0 = use velocity-based smear (or no smear).",
)

# ---------------------------------------------------------------------------
# Sensor altitude — Stage-7 stop-gap (subsumed by future SensorDescriptor ADR)
# ---------------------------------------------------------------------------

H_SENSOR_M = ParameterDef(
    name="platform.h_sensor",
    description=(
        "Sensor altitude above mean sea level [m].  Stage-7 stop-gap: used "
        "only by the atmosphere assembly when "
        "source.no_atmosphere_subcase == 'space' to verify the LOS clears "
        "the Earth limb via LineOfSightGeometry.intercepts_earth().  "
        "A future SensorDescriptor ADR (matrix §4.4) will subsume this "
        "parameter; see the module docstring.  Default = 0.0 (ground); "
        "the assembly arm raises if the space sub-case runs with h_sensor "
        "left at the default."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 1e9),
    tags=frozenset({"platform", "geometry", "stopgap"}),
    default_justification=(
        "0.0 = ground sensor.  The Stage-7 space-sub-case arm rejects this "
        "default explicitly rather than silently using a wrong value; "
        "users running the space sub-case must supply a positive altitude."
    ),
)


ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    JITTER_RMS_URAD,
    JITTER_AXES,
    JITTER_RMS_X_URAD,
    JITTER_RMS_Y_URAD,
    GROUND_VELOCITY_M_S,
    SMEAR_LENGTH_UM,
    H_SENSOR_M,
)
