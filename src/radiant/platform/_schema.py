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

ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    JITTER_RMS_URAD,
    JITTER_AXES,
    JITTER_RMS_X_URAD,
    JITTER_RMS_Y_URAD,
)
