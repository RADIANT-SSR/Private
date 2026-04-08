"""Parameter definitions for the atmosphere stage.

Only the subset needed by :mod:`radiant.atmosphere.simple` and
:mod:`radiant.atmosphere.exo` (task 2B.2) is defined here. The full
RADIANT_Atmosphere.md §6 inventory (MODTRAN deck options, tabulated
file paths, turbulence) will be added by later tasks.
"""

from __future__ import annotations

from radiant.core.parameters import ParameterDef

# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

ATMOSPHERE_MODEL = ParameterDef(
    name="atmosphere.model",
    description=(
        "Atmosphere model selector. 'simple' uses a closed-form Beer-Lambert "
        "(Rayleigh + Koschmieder aerosol + 5-band water vapor); 'exo' uses a "
        "vacuum (τ≡1, L_path≡0). 'tabulated' and 'modtran' are reserved for "
        "later tasks."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="simple",
    enum_values=("simple", "exo", "tabulated", "modtran"),
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


ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    ATMOSPHERE_MODEL,
    VISIBILITY_KM,
    AEROSOL_TYPE,
    PRECIPITABLE_WATER_CM,
    STANDARD_ATMOSPHERE,
)
