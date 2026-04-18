"""Parameter definitions for the platform stage.

Covers jitter (random pointing errors) and smear (linear motion blur)
from platform dynamics. See ``docs/RADIANT_Spatial_Complete.md`` §7, §10.2.
"""

from __future__ import annotations

from radiant.core.parameters import ParameterDef

# ---------------------------------------------------------------------------
# Jitter — random angular pointing error during integration
# ---------------------------------------------------------------------------

JITTER_RMS_URAD = ParameterDef(
    name="platform.jitter_rms_urad",
    description=(
        "Isotropic jitter RMS [µrad]. Applied equally to both axes. "
        "Set to 0 to disable jitter."
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
    description=(
        "Cross-track jitter RMS [µrad]. Only used when jitter_axes='anisotropic'."
    ),
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
    description=(
        "Along-track jitter RMS [µrad]. Only used when jitter_axes='anisotropic'."
    ),
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

ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    JITTER_RMS_URAD,
    JITTER_AXES,
    JITTER_RMS_X_URAD,
    JITTER_RMS_Y_URAD,
    GROUND_VELOCITY_M_S,
    SMEAR_LENGTH_UM,
)
