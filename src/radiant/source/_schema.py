"""Parameter definitions for the source stage.

Covers thermal, point-source, sub-pixel, and regime-related parameters.
"""

from __future__ import annotations

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
        "0.0 signals 'geometry not provided' — regime classification "
        "defaults to extended scene."
    ),
)

TARGET_RANGE = ParameterDef(
    name="source.target.range_m",
    description=(
        "Observer-to-target slant range [m]. "
        "0.0 = not specified (extended-scene default)."
    ),
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=0.0,
    bounds=(0.0, 1e12),
    tags=frozenset({"source", "target", "geometry"}),
    default_justification=(
        "0.0 signals 'range not provided' — regime classification "
        "defaults to extended scene."
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

ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    TARGET_TEMPERATURE,
    TARGET_EMISSIVITY,
    TARGET_PROJECTED_AREA,
    TARGET_RANGE,
    FILL_FRACTION,
    BACKGROUND_TEMPERATURE,
    BACKGROUND_EMISSIVITY,
    REGIME_OVERRIDE,
)
