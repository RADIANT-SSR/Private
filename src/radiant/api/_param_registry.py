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
from radiant.performance._schema import ALL_PARAMETERS as PERF_PARAMS
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

# Ground-speed collapse (Gap 75): platform.ground_velocity_m_s (smear) and
# geometry.ground_speed_m_s (access rate) are the SAME physical quantity — the
# along-track ground velocity. Linking them as an identity consistency group
# collapses the duplicate: setting either derives the other (so smear and
# access rate read one number), and setting both to disagreeing values raises
# an actionable over-specification error instead of silently using two
# different velocities. Both default to 0.0, so an unset pair stays 0.
_GROUND_SPEED_GROUP = ConsistencyGroup(
    name="ground_speed",
    parameters=(
        "platform.ground_velocity_m_s",
        "geometry.ground_speed_m_s",
    ),
    constraint="platform.ground_velocity_m_s == geometry.ground_speed_m_s",
    derivations={
        "platform.ground_velocity_m_s": lambda kv: kv["geometry.ground_speed_m_s"],
        "geometry.ground_speed_m_s": lambda kv: kv["platform.ground_velocity_m_s"],
    },
    tolerance=1e-6,
)


def build_parameter_set() -> ParameterSet:
    """Return a :class:`ParameterSet` with the full 2B.5 schema."""
    schema = list(
        SRC_PARAMS
        + ATMO_PARAMS
        + OPT_PARAMS
        + PLAT_PARAMS
        + SI_PARAMS
        + DET_PARAMS
        + RO_PARAMS
        + PERF_PARAMS
    )
    groups = [_FNUMBER_GROUP, _GROUND_SPEED_GROUP]
    return ParameterSet(schema, groups)
