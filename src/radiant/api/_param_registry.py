"""Central parameter schema registry.

Collects all ``ParameterDef`` objects from per-stage ``_schema.py``
modules and builds a :class:`ParameterSet` with the full schema.
Only ``radiant.api`` may import from all stages (import-linter rule).
"""

from __future__ import annotations

from radiant.atmosphere._schema import ALL_PARAMETERS as ATMO_PARAMS
from radiant.core.parameters import ConsistencyGroup, ParameterSet
from radiant.detector._schema import ALL_PARAMETERS as DET_PARAMS
from radiant.optics._schema import ALL_PARAMETERS as OPT_PARAMS
from radiant.platform._schema import ALL_PARAMETERS as PLAT_PARAMS
from radiant.readout._schema import ALL_PARAMETERS as RO_PARAMS
from radiant.source._schema import ALL_PARAMETERS as SRC_PARAMS
from radiant.spectral_integration._schema import ALL_PARAMETERS as SI_PARAMS

# f/# consistency group: f_number = focal_length_m / aperture_diameter_m
_FNUMBER_GROUP = ConsistencyGroup(
    name="fnumber",
    parameters=(
        "optics.aperture_diameter_m",
        "optics.focal_length_m",
        "optics.f_number",
    ),
    constraint="f_number = focal_length_m / aperture_diameter_m",
    derivations={
        "optics.f_number": lambda kv: (
            kv["optics.focal_length_m"] / kv["optics.aperture_diameter_m"]
        ),
        "optics.focal_length_m": lambda kv: (
            kv["optics.aperture_diameter_m"] * kv["optics.f_number"]
        ),
        "optics.aperture_diameter_m": lambda kv: (
            kv["optics.focal_length_m"] / kv["optics.f_number"]
        ),
    },
    tolerance=1e-3,
)


def build_parameter_set() -> ParameterSet:
    """Return a :class:`ParameterSet` with the full 2B.5 schema."""
    schema = list(
        SRC_PARAMS + ATMO_PARAMS + OPT_PARAMS + PLAT_PARAMS + SI_PARAMS + DET_PARAMS + RO_PARAMS
    )
    groups = [_FNUMBER_GROUP]
    return ParameterSet(schema, groups)
